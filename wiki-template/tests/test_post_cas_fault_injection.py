from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from run_lib import RunError  # noqa: E402
from wiki_run import execute_run, finish_session, recover_run, recover_session, start_session, terminate_session  # noqa: E402
from fake_agent_harness import commit_artifact, proposal, write_apply_run  # noqa: E402
from wiki_test_support import add_authority, make_git_wiki, run  # noqa: E402


class PostCasFaultInjectionTests(unittest.TestCase):
    def make_run(self, parent: Path) -> tuple[Path, dict[str, object], dict[str, object]]:
        root = make_git_wiki(parent)
        add_authority(
            root,
            "auto-editor",
            mode="authorised-autonomous-apply",
            lane="synthesize",
            action="edit-wiki-pages",
            writable_paths=[
                "wiki/concepts/**", "reports/semantic/**", "reports/runs/**", "reports/latest.json",
            ],
            page_types=["Concept"],
            commit_policy="scoped-auto",
        )
        page = root / "wiki" / "concepts" / "frontmatter.md"
        proposed = proposal(
            "prior-proposal-run",
            path="wiki/concepts/frontmatter.md",
            content=page.read_text(encoding="utf-8") + "\nRecoverable clarification.\n",
            action_class="semantic-maintenance",
        )
        commit_artifact(root, "reports/proposals/test-proposal.json", proposed, "add recovery proposal")
        envelope = start_session(
            root, "synthesize", "authorised-autonomous-apply", "auto-editor", "test-proposal"
        )
        write_apply_run(root, envelope["run_id"], proposed)
        return root, proposed, envelope

    def tearDown(self) -> None:
        os.environ.pop("RB_WIKI_FAULT_STAGE", None)

    def test_every_post_cas_fault_records_commit_and_recovers_without_duplicate(self) -> None:
        stages = [
            "after-cas",
            "after-index-refresh",
            "after-run-record-update",
            "after-receipt-write",
            "after-session-save",
            "before-lock-release",
        ]
        for stage in stages:
            with self.subTest(stage=stage), tempfile.TemporaryDirectory() as temporary:
                root, _proposed, envelope = self.make_run(Path(temporary))
                base = run(["git", "rev-parse", "HEAD"], root).stdout.strip()
                os.environ["RB_WIKI_FAULT_STAGE"] = stage
                code, record = finish_session(
                    root, envelope["run_id"], envelope["run_token"], []
                )
                self.assertEqual(code, 5)
                self.assertEqual(record["state"], "committed-recovery-required")
                self.assertIsNotNone(record["commit_hash"])
                self.assertNotEqual(record["commit_hash"], base)
                self.assertEqual(run(["git", "rev-parse", "HEAD"], root).stdout.strip(), record["commit_hash"])
                self.assertTrue((root / ".wiki_state" / "mutation.lock").exists())
                transaction = json.loads(
                    (root / ".wiki_state" / "transactions" / f"{record['run_id']}.json").read_text()
                )
                self.assertEqual(transaction["commit_hash"], record["commit_hash"])
                os.environ.pop("RB_WIKI_FAULT_STAGE", None)
                recovered_code, recovered = recover_session(
                    root, envelope["run_id"], envelope["run_token"]
                )
                self.assertEqual(recovered_code, 0)
                self.assertEqual(recovered["state"], "completed")
                self.assertEqual(run(["git", "rev-parse", "HEAD"], root).stdout.strip(), record["commit_hash"])
                self.assertFalse((root / ".wiki_state" / "mutation.lock").exists())
                retry_code, retry = recover_session(root, envelope["run_id"], envelope["run_token"])
                self.assertEqual(retry_code, 0)
                self.assertEqual(retry["commit_hash"], record["commit_hash"])

    def test_pre_cas_faults_never_move_branch(self) -> None:
        stages = [
            "before-index-create", "after-index-create", "after-staging", "after-tree-write", "after-commit-create",
        ]
        for stage in stages:
            with self.subTest(stage=stage), tempfile.TemporaryDirectory() as temporary:
                root, _proposed, envelope = self.make_run(Path(temporary))
                base = run(["git", "rev-parse", "HEAD"], root).stdout.strip()
                os.environ["RB_WIKI_FAULT_STAGE"] = stage
                with self.assertRaises((OSError, RunError)):
                    finish_session(root, envelope["run_id"], envelope["run_token"], [])
                self.assertEqual(run(["git", "rev-parse", "HEAD"], root).stdout.strip(), base)
                os.environ.pop("RB_WIKI_FAULT_STAGE", None)
                terminate_session(root, envelope["run_id"], envelope["run_token"], "failed", "test cleanup")

    def test_controller_owned_run_recovers_with_original_authority(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = make_git_wiki(Path(temporary))
            add_authority(
                root,
                "cron-maintain",
                mode="scheduled-propose",
                lane="maintain",
                action="deterministic-maintenance",
                writable_paths=[
                    "wiki/index.md", ".wiki_cache/graph.json", "reports/lint/**",
                    "reports/runs/**", "reports/latest.json",
                ],
                commit_policy="scoped-auto",
            )
            os.environ["RB_WIKI_FAULT_STAGE"] = "after-cas"
            code, record = execute_run(
                root, "maintain", "scheduled-propose", "cron-maintain", full=True
            )
            self.assertEqual(code, 5)
            self.assertEqual(record["state"], "committed-recovery-required")
            self.assertFalse((root / ".wiki_state" / "sessions" / f"{record['run_id']}.json").exists())
            os.environ.pop("RB_WIKI_FAULT_STAGE", None)
            recovered_code, recovered = recover_run(
                root, record["run_id"], authority_id="cron-maintain"
            )
            self.assertEqual(recovered_code, 0)
            self.assertEqual(recovered["state"], "completed")
            self.assertFalse((root / ".wiki_state" / "mutation.lock").exists())

    def test_recovery_discovers_cas_when_branch_stage_write_was_lost(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root, _proposed, envelope = self.make_run(Path(temporary))
            os.environ["RB_WIKI_FAULT_STAGE"] = "after-cas"
            code, record = finish_session(
                root, envelope["run_id"], envelope["run_token"], []
            )
            self.assertEqual(code, 5)
            transaction_path = root / ".wiki_state" / "transactions" / f"{record['run_id']}.json"
            transaction = json.loads(transaction_path.read_text(encoding="utf-8"))
            transaction["stage"] = "commit-created"
            transaction["branch_head"] = None
            transaction_path.write_text(json.dumps(transaction), encoding="utf-8")
            os.environ.pop("RB_WIKI_FAULT_STAGE", None)
            recovered_code, recovered = recover_session(
                root, envelope["run_id"], envelope["run_token"]
            )
            self.assertEqual(recovered_code, 0)
            self.assertEqual(recovered["commit_hash"], record["commit_hash"])

    def test_recovery_rejects_divergent_branch_and_retains_lock(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root, _proposed, envelope = self.make_run(Path(temporary))
            base = run(["git", "rev-parse", "HEAD"], root).stdout.strip()
            os.environ["RB_WIKI_FAULT_STAGE"] = "after-cas"
            code, record = finish_session(
                root, envelope["run_id"], envelope["run_token"], []
            )
            self.assertEqual(code, 5)
            transaction = json.loads(
                (root / ".wiki_state" / "transactions" / f"{record['run_id']}.json").read_text()
            )
            run(["git", "update-ref", transaction["branch_ref"], base, record["commit_hash"]], root)
            os.environ.pop("RB_WIKI_FAULT_STAGE", None)
            with self.assertRaisesRegex(RunError, "no longer points"):
                recover_session(root, envelope["run_id"], envelope["run_token"])
            self.assertTrue((root / ".wiki_state" / "mutation.lock").exists())


if __name__ == "__main__":
    unittest.main()
