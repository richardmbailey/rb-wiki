from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from wiki_test_support import add_authority, latest_record, make_git_wiki, run, run_controller


class WalkingSkeletonTests(unittest.TestCase):
    def test_clean_noop_run_closes_without_tracked_report_churn(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = make_git_wiki(Path(temporary))
            reports_before = sorted((root / "reports" / "lint").glob("*.md"))
            completed = run_controller(root)
            self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
            record = latest_record(root)
            self.assertEqual(record["state"], "completed")
            self.assertEqual(record["result"], "no-op")
            self.assertEqual(record["changed_paths"], [])
            self.assertFalse((root / ".wiki_state" / "mutation.lock").exists())
            self.assertEqual(reports_before, sorted((root / "reports" / "lint").glob("*.md")))
            self.assertEqual(run(["git", "status", "--porcelain"], root).stdout, "")

            again = run_controller(root)
            self.assertEqual(again.returncode, 0, again.stdout + again.stderr)
            self.assertFalse((root / "reports" / "latest.json").exists())
            self.assertEqual(list((root / "reports" / "runs").glob("*.json")), [])

    def test_dirty_base_blocks_before_mutation_and_releases_lock(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = make_git_wiki(Path(temporary))
            (root / "dirty.txt").write_text("unrelated\n", encoding="utf-8")
            completed = run_controller(root)
            self.assertEqual(completed.returncode, 2)
            record = latest_record(root)
            self.assertEqual(record["state"], "blocked")
            self.assertIn("dirty.txt", record["error"])
            self.assertFalse((root / ".wiki_state" / "mutation.lock").exists())
            self.assertEqual(list((root / "reports" / "runs").glob("*.json")), [])

    def test_existing_lock_produces_structured_blocked_attempt(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = make_git_wiki(Path(temporary))
            lock_dir = root / ".wiki_state" / "mutation.lock"
            lock_dir.mkdir(parents=True)
            (lock_dir / "owner.json").write_text(
                json.dumps({"run_id": "other", "pid": 123}), encoding="utf-8"
            )
            completed = run_controller(root)
            self.assertEqual(completed.returncode, 2)
            record = latest_record(root)
            self.assertEqual(record["state"], "blocked")
            self.assertIn("owner", record["error"])
            self.assertTrue(lock_dir.exists())

    def test_incomplete_lock_produces_explicit_structured_diagnostic(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = make_git_wiki(Path(temporary))
            (root / ".wiki_state" / "mutation.lock").mkdir(parents=True)
            completed = run_controller(root)
            self.assertEqual(completed.returncode, 2)
            record = latest_record(root)
            self.assertEqual(record["state"], "blocked")
            self.assertIn("incomplete", record["error"])

    def test_competing_process_gets_structured_blocked_result(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = make_git_wiki(Path(temporary))
            holder_code = (
                "import sys; sys.path.insert(0, 'tools'); "
                "from run_lib import MutationLock; "
                "lock=MutationLock(__import__('pathlib').Path('.'), 'holder', 'maintain', 'scheduled-propose'); "
                "lock.acquire(); print('READY', flush=True); input(); lock.release()"
            )
            env = os.environ.copy()
            env["PYTHONDONTWRITEBYTECODE"] = "1"
            holder = subprocess.Popen(
                [sys.executable, "-c", holder_code],
                cwd=root,
                env=env,
                text=True,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            try:
                self.assertEqual(holder.stdout.readline().strip(), "READY")
                completed = run_controller(root)
                self.assertEqual(completed.returncode, 2)
                self.assertEqual(latest_record(root)["state"], "blocked")
            finally:
                if holder.stdin:
                    holder.stdin.write("\n")
                    holder.stdin.flush()
                holder.communicate(timeout=5)

    def test_fresh_copy_preserves_baseline_ingest_behavior(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = make_git_wiki(Path(temporary))
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
            inbox = root / "inbox" / "baseline.txt"
            inbox.write_text("Baseline ingest source.\n", encoding="utf-8")
            completed = run(
                [sys.executable, "tools/wiki_cron.py", "inbox", "--authority", "cron-ingest"],
                root,
                check=False,
            )
            self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
            self.assertTrue(any((root / "sources" / "raw").glob("*-baseline.txt")))
            self.assertTrue(any((root / "wiki" / "references").glob("*-baseline.md")))

    def test_lane_failure_releases_lock_and_preserves_journal(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = make_git_wiki(Path(temporary))
            broken = root / "wiki" / "concepts" / "broken.md"
            broken.write_text("# Missing frontmatter\n", encoding="utf-8")
            run(["git", "add", "wiki/concepts/broken.md"], root)
            run(["git", "commit", "-q", "-m", "add invalid fixture"], root)

            completed = run_controller(root)
            self.assertEqual(completed.returncode, 1)
            record = latest_record(root)
            self.assertEqual(record["state"], "failed")
            self.assertEqual(record["checks"][0]["status"], "fail")
            self.assertFalse((root / ".wiki_state" / "mutation.lock").exists())
            self.assertTrue((root / ".wiki_state" / "runs" / f"{record['run_id']}.json").exists())
            self.assertTrue((root / "reports" / "runs" / f"{record['run_id']}.json").exists())
            self.assertTrue((root / "reports" / "runs" / f"{record['run_id']}.md").exists())

    def test_unexpected_lane_path_prevents_successful_closure(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = make_git_wiki(Path(temporary))
            script = root / "tools" / "build_graph.py"
            script.write_text(
                "from pathlib import Path\nPath('unexpected.txt').write_text('x', encoding='utf-8')\nprint('PASS')\n",
                encoding="utf-8",
            )
            run(["git", "add", "tools/build_graph.py"], root)
            run(["git", "commit", "-q", "-m", "test unexpected output"], root)
            completed = run_controller(root)
            self.assertEqual(completed.returncode, 1)
            record = latest_record(root)
            self.assertEqual(record["state"], "failed")
            self.assertIn("lane contract", record["error"])
            self.assertIn("unexpected.txt", record["changed_paths"])
            self.assertFalse((root / ".wiki_state" / "mutation.lock").exists())


if __name__ == "__main__":
    unittest.main()
