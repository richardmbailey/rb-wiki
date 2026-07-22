from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import wiki_cron  # noqa: E402
from wiki_test_support import add_authority, make_git_wiki, run  # noqa: E402


class CronExceptionSafetyTests(unittest.TestCase):
    def make_cron(self, parent: Path, with_file: bool) -> Path:
        root = make_git_wiki(parent)
        add_authority(
            root,
            "cron-ingest",
            mode="scheduled-propose",
            lane="ingest",
            action="ingest-sources",
            input_roots=["inbox"],
            writable_paths=[
                "sources/raw/**", "sources/derived/**", "sources/_source_registry.yml",
                "wiki/references/**", "wiki/index.md", ".wiki_cache/graph.json",
                "reports/ingest/**", "reports/runs/**", "reports/latest.json",
            ],
            page_types=["Reference"],
            commit_policy="scoped-auto",
        )
        if with_file:
            (root / "inbox" / "fault.txt").write_text("preserve this evidence\n", encoding="utf-8")
        return root

    def assert_coherent_failure(self, root: Path) -> dict[str, object]:
        journals = list((root / ".wiki_state" / "runs").glob("*.json"))
        self.assertEqual(len(journals), 1)
        record = json.loads(journals[0].read_text(encoding="utf-8"))
        self.assertIn(record["state"], {"failed", "completed", "committed-recovery-required"})
        if record["state"] == "committed-recovery-required":
            self.assertTrue((root / ".wiki_state" / "mutation.lock").exists())
            self.assertIsNotNone(record["commit_hash"])
        else:
            self.assertFalse((root / ".wiki_state" / "mutation.lock").exists())
        return record

    def test_faults_after_start_leave_one_explained_outcome(self) -> None:
        cases = [
            ("after-session-start", False),
            ("policy-load", False),
            ("inbox-enumeration", False),
            ("empty-inbox-finish", False),
            ("per-file-ingest", True),
            ("report-write", True),
            ("controller-lint", True),
            ("finish", True),
            ("terminal-report-rendering", False),
            ("per-file-ingest,after-terminate", True),
        ]
        for stage, with_file in cases:
            with self.subTest(stage=stage), tempfile.TemporaryDirectory() as temporary:
                root = self.make_cron(Path(temporary), with_file)
                completed = run(
                    [sys.executable, "tools/wiki_cron.py", "inbox", "--authority", "cron-ingest"],
                    root,
                    check=False,
                    env_overrides={"RB_WIKI_CRON_FAULT_STAGE": stage},
                )
                self.assert_coherent_failure(root)
                if with_file and stage in {"report-write", "controller-lint", "finish"}:
                    self.assertTrue(list((root / "sources" / "raw").glob("*-fault.txt")))
                    self.assertTrue(list((root / ".wiki_state" / "sources").glob("*.json")))

    def test_controller_environment_is_restored_after_exception(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = self.make_cron(Path(temporary), False)
            original_root = wiki_cron.ROOT
            original_fault = os.environ.get("RB_WIKI_CRON_FAULT_STAGE")
            original_controller = os.environ.get("RB_WIKI_RUN_CONTROLLER")
            try:
                wiki_cron.ROOT = root
                os.environ["RB_WIKI_CRON_FAULT_STAGE"] = "after-session-start"
                os.environ["RB_WIKI_RUN_CONTROLLER"] = "sentinel"
                self.assertEqual(wiki_cron.inbox_sweep("cron-ingest"), 1)
                self.assertEqual(os.environ.get("RB_WIKI_RUN_CONTROLLER"), "sentinel")
            finally:
                wiki_cron.ROOT = original_root
                if original_fault is None:
                    os.environ.pop("RB_WIKI_CRON_FAULT_STAGE", None)
                else:
                    os.environ["RB_WIKI_CRON_FAULT_STAGE"] = original_fault
                if original_controller is None:
                    os.environ.pop("RB_WIKI_RUN_CONTROLLER", None)
                else:
                    os.environ["RB_WIKI_RUN_CONTROLLER"] = original_controller

    def test_acquisition_fault_before_start_creates_no_session_or_lock(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = self.make_cron(Path(temporary), False)
            completed = run(
                [sys.executable, "tools/wiki_cron.py", "inbox", "--authority", "cron-ingest"],
                root,
                check=False,
                env_overrides={"RB_WIKI_CRON_FAULT_STAGE": "acquisition-handoff-load"},
            )
            self.assertNotEqual(completed.returncode, 0)
            self.assertEqual(list((root / ".wiki_state" / "runs").glob("*.json")), [])
            self.assertFalse((root / ".wiki_state" / "mutation.lock").exists())

    def test_cron_preserves_post_commit_recovery_outcome(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = self.make_cron(Path(temporary), True)
            completed = run(
                [sys.executable, "tools/wiki_cron.py", "inbox", "--authority", "cron-ingest"],
                root,
                check=False,
                env_overrides={"RB_WIKI_FAULT_STAGE": "after-cas"},
            )
            self.assertEqual(completed.returncode, 5, completed.stdout + completed.stderr)
            record = self.assert_coherent_failure(root)
            self.assertEqual(record["state"], "committed-recovery-required")


if __name__ == "__main__":
    unittest.main()
