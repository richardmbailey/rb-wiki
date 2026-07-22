from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from run_lib import RunError  # noqa: E402
from wiki_run import finish_session, start_session, terminate_session  # noqa: E402
from wiki_test_support import add_authority, make_git_wiki, run
from fake_agent_harness import commit_artifact, proposal, write_apply_run


class ScopedAutoCommitTests(unittest.TestCase):
    def make_auto(self, parent: Path) -> tuple[Path, dict[str, object]]:
        root = make_git_wiki(parent)
        add_authority(
            root,
            "auto-editor",
            mode="authorised-autonomous-apply",
            lane="synthesize",
            action="edit-wiki-pages",
            writable_paths=[
                "wiki/concepts/**", "reports/semantic/**",
                "reports/runs/**", "reports/latest.json",
            ],
            page_types=["Concept"],
            commit_policy="scoped-auto",
        )
        page = root / "wiki" / "concepts" / "frontmatter.md"
        proposed = proposal(
            "prior-proposal-run",
            path="wiki/concepts/frontmatter.md",
            content=page.read_text(encoding="utf-8") + "\nManaged clarification.\n",
            action_class="semantic-maintenance",
        )
        commit_artifact(root, "reports/proposals/test-proposal.json", proposed, "add exact commit test proposal")
        return root, proposed

    def test_scoped_auto_commits_exact_paths_with_report_and_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root, proposed = self.make_auto(Path(temporary))
            hook_marker = root / "hook-ran"
            hook = root / ".git" / "hooks" / "pre-commit"
            hook.write_text(f"#!/bin/sh\ntouch '{hook_marker}'\nexit 1\n", encoding="utf-8")
            hook.chmod(0o755)
            base = run(["git", "rev-parse", "HEAD"], root).stdout.strip()
            envelope = start_session(root, "synthesize", "authorised-autonomous-apply", "auto-editor", "test-proposal")
            write_apply_run(root, envelope["run_id"], proposed)
            code, record = finish_session(root, envelope["run_id"], envelope["run_token"], [])
            self.assertEqual(code, 0)
            self.assertEqual(record["state"], "completed")
            self.assertNotEqual(record["commit_hash"], base)
            self.assertFalse(hook_marker.exists(), "commit-tree must not execute repository hooks")
            self.assertEqual(run(["git", "status", "--porcelain"], root).stdout, "")
            message = run(["git", "show", "-s", "--format=%B", "HEAD"], root).stdout
            self.assertIn(f"RB-Wiki-Run: {record['run_id']}", message)
            committed = run(["git", "diff-tree", "--no-commit-id", "--name-only", "-r", "HEAD"], root).stdout.splitlines()
            self.assertEqual(sorted(committed), sorted(record["changed_paths"]))
            durable = json.loads(
                run(["git", "show", f"HEAD:reports/runs/{record['run_id']}.json"], root).stdout
            )
            self.assertEqual(durable["content_manifest"], record["content_manifest"])
            self.assertIsNone(durable["commit_hash"])
            receipt = json.loads(
                (root / ".wiki_state" / "receipts" / f"{record['run_id']}.json").read_text(encoding="utf-8")
            )
            self.assertEqual(receipt["commit_hash"], record["commit_hash"])

    def test_dirty_real_index_prevents_scoped_auto_and_does_not_move_branch(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root, proposed = self.make_auto(Path(temporary))
            base = run(["git", "rev-parse", "HEAD"], root).stdout.strip()
            envelope = start_session(root, "synthesize", "authorised-autonomous-apply", "auto-editor", "test-proposal")
            page = root / "wiki" / "concepts" / "frontmatter.md"
            write_apply_run(root, envelope["run_id"], proposed)
            run(["git", "add", page.relative_to(root).as_posix()], root)
            with self.assertRaisesRegex(RunError, "clean real index"):
                finish_session(root, envelope["run_id"], envelope["run_token"], [])
            self.assertEqual(run(["git", "rev-parse", "HEAD"], root).stdout.strip(), base)
            terminate_session(root, envelope["run_id"], envelope["run_token"], "failed", "test cleanup")

    def test_changed_head_prevents_closure(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root, _proposed = self.make_auto(Path(temporary))
            envelope = start_session(root, "synthesize", "authorised-autonomous-apply", "auto-editor", "test-proposal")
            run(["git", "commit", "--allow-empty", "-q", "-m", "concurrent human commit"], root)
            concurrent = run(["git", "rev-parse", "HEAD"], root).stdout.strip()
            with self.assertRaisesRegex(RunError, "HEAD changed"):
                finish_session(root, envelope["run_id"], envelope["run_token"], [])
            self.assertEqual(run(["git", "rev-parse", "HEAD"], root).stdout.strip(), concurrent)
            terminate_session(root, envelope["run_id"], envelope["run_token"], "failed", "test cleanup")


if __name__ == "__main__":
    unittest.main()
