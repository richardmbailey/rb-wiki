from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

from wiki_test_support import add_authority, make_git_wiki, run


class CronRunIntegrationTests(unittest.TestCase):
    def make_cron(self, parent: Path) -> Path:
        root = make_git_wiki(parent)
        add_authority(
            root,
            "cron-ingest",
            mode="scheduled-propose",
            lane="ingest",
            action="ingest-sources",
            input_roots=["inbox"],
            writable_paths=[
                "sources/raw/**",
                "sources/derived/**",
                "sources/_source_registry.yml",
                "wiki/references/**",
                "wiki/index.md",
                ".wiki_cache/graph.json",
                "reports/ingest/**",
                "reports/runs/**",
                "reports/latest.json",
            ],
            page_types=["Reference"],
            commit_policy="scoped-auto",
        )
        return root

    def test_cron_uses_one_controller_run_and_no_nested_lint_report(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = self.make_cron(Path(temporary))
            before_lint = sorted((root / "reports" / "lint").glob("*.md"))
            (root / "inbox" / "cron.txt").write_text("cron evidence\n", encoding="utf-8")
            completed = run(
                [sys.executable, "tools/wiki_cron.py", "inbox", "--authority", "cron-ingest"],
                root,
                check=False,
            )
            self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
            self.assertEqual(before_lint, sorted((root / "reports" / "lint").glob("*.md")))
            ingest_reports = list((root / "reports" / "ingest").glob("*.json"))
            run_reports = list((root / "reports" / "runs").glob("*.json"))
            self.assertEqual(len(ingest_reports), 1)
            self.assertEqual(len(run_reports), 1)
            self.assertEqual(ingest_reports[0].stem, run_reports[0].stem)

    def test_concurrent_cron_cannot_acquire_second_writer(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = self.make_cron(Path(temporary))
            (root / "inbox" / "cron.txt").write_text("cron evidence\n", encoding="utf-8")
            lock = root / ".wiki_state" / "mutation.lock"
            lock.mkdir(parents=True)
            (lock / "owner.json").write_text('{"run_id":"other","pid":1}', encoding="utf-8")
            completed = run(
                [sys.executable, "tools/wiki_cron.py", "inbox", "--authority", "cron-ingest"],
                root,
                check=False,
            )
            self.assertNotEqual(completed.returncode, 0)
            self.assertEqual(list((root / "sources" / "raw").glob("*-cron.txt")), [])

    def test_file_count_budget_fails_before_preservation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = self.make_cron(Path(temporary))
            for index in range(21):
                (root / "inbox" / f"source-{index}.txt").write_text(f"{index}\n", encoding="utf-8")
            completed = run(
                [sys.executable, "tools/wiki_cron.py", "inbox", "--authority", "cron-ingest"],
                root,
                check=False,
            )
            self.assertNotEqual(completed.returncode, 0)
            self.assertEqual(len(list((root / "sources" / "raw").glob("*-source-*.txt"))), 0)

    def test_preservation_only_requires_explicit_authority_action(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = make_git_wiki(Path(temporary))
            add_authority(
                root,
                "preserver",
                mode="scheduled-propose",
                lane="ingest",
                action=["ingest-sources", "preserve-unsupported"],
                input_roots=["inbox"],
                writable_paths=[
                    "sources/raw/**",
                    "sources/derived/**",
                    "sources/_source_registry.yml",
                    "wiki/references/**",
                    "wiki/index.md",
                    ".wiki_cache/graph.json",
                    "reports/ingest/**",
                    "reports/runs/**",
                    "reports/latest.json",
                ],
                page_types=["Reference"],
                commit_policy="scoped-auto",
            )
            (root / "inbox" / "archive.xyz").write_text("preserve only\n", encoding="utf-8")
            completed = run(
                [sys.executable, "tools/wiki_cron.py", "inbox", "--authority", "preserver"],
                root,
                check=False,
            )
            self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
            self.assertEqual(len(list((root / "sources" / "raw").glob("*-archive.xyz"))), 1)

    def test_empty_inbox_is_ephemeral_noop_without_tracked_report_churn(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = self.make_cron(Path(temporary))
            completed = run(
                [sys.executable, "tools/wiki_cron.py", "inbox", "--authority", "cron-ingest"],
                root,
                check=False,
            )
            self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
            self.assertEqual(list((root / "reports" / "ingest").glob("*.json")), [])
            self.assertEqual(list((root / "reports" / "runs").glob("*.json")), [])
            self.assertEqual(run(["git", "status", "--porcelain"], root).stdout, "")

    def test_nightly_and_weekly_maintenance_require_and_use_controller_authority(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = make_git_wiki(Path(temporary))
            add_authority(
                root,
                "cron-maintain",
                mode="scheduled-propose",
                lane="maintain",
                action="deterministic-maintenance",
                writable_paths=[
                    "wiki/index.md",
                    ".wiki_cache/graph.json",
                    "reports/lint/**",
                    "reports/runs/**",
                    "reports/latest.json",
                ],
                commit_policy="scoped-auto",
            )
            missing = run([sys.executable, "tools/wiki_cron.py", "nightly"], root, check=False)
            self.assertNotEqual(missing.returncode, 0)
            nightly = run(
                [sys.executable, "tools/wiki_cron.py", "nightly", "--authority", "cron-maintain"],
                root,
                check=False,
            )
            self.assertEqual(nightly.returncode, 0, nightly.stdout + nightly.stderr)
            weekly = run(
                [sys.executable, "tools/wiki_cron.py", "weekly", "--authority", "cron-maintain"],
                root,
                check=False,
            )
            self.assertEqual(weekly.returncode, 0, weekly.stdout + weekly.stderr)
            self.assertTrue(list((root / "reports" / "lint").glob("*.json")))
            self.assertEqual(run(["git", "status", "--porcelain"], root).stdout, "")

    def test_weekly_scope_is_rejected_before_report_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = make_git_wiki(Path(temporary))
            add_authority(
                root,
                "narrow-maintain",
                mode="scheduled-propose",
                lane="maintain",
                action="deterministic-maintenance",
                writable_paths=[
                    "wiki/index.md",
                    ".wiki_cache/graph.json",
                    "reports/runs/**",
                    "reports/latest.json",
                ],
            )
            before = list((root / "reports" / "lint").glob("*.json"))
            weekly = run(
                [sys.executable, "tools/wiki_cron.py", "weekly", "--authority", "narrow-maintain"],
                root,
                check=False,
            )
            self.assertNotEqual(weekly.returncode, 0)
            self.assertIn("must allow reports/lint/**", weekly.stderr)
            self.assertEqual(before, list((root / "reports" / "lint").glob("*.json")))

    def test_forbidden_commit_policy_ends_as_manual_commit_required(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = make_git_wiki(Path(temporary))
            add_authority(
                root,
                "review-maintain",
                mode="scheduled-propose",
                lane="maintain",
                action="deterministic-maintenance",
                writable_paths=[
                    "wiki/index.md",
                    ".wiki_cache/graph.json",
                    "reports/lint/**",
                    "reports/runs/**",
                    "reports/latest.json",
                ],
            )
            weekly = run(
                [sys.executable, "tools/wiki_cron.py", "weekly", "--authority", "review-maintain"],
                root,
                check=False,
            )
            self.assertEqual(weekly.returncode, 3, weekly.stdout + weekly.stderr)
            self.assertIn("manual-commit-required", weekly.stdout)
            self.assertNotEqual(run(["git", "status", "--porcelain"], root).stdout, "")


if __name__ == "__main__":
    unittest.main()
