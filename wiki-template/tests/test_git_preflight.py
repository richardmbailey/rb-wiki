from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from run_lib import ContractError, RunError  # noqa: E402
from wiki_run import finish_session, start_session, terminate_session  # noqa: E402
from wiki_test_support import add_authority, make_git_wiki, run
from fake_agent_harness import commit_artifact, proposal, write_apply_run


class GitPreflightTests(unittest.TestCase):
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
            content=page.read_text(encoding="utf-8") + "\nGit state test.\n",
            action_class="semantic-maintenance",
        )
        commit_artifact(root, "reports/proposals/test-proposal.json", proposed, "add Git state proposal")
        return root, proposed

    def edit(self, root: Path, run_id: str, proposed: dict[str, object]) -> None:
        write_apply_run(root, run_id, proposed)

    def test_detached_head_blocks_scoped_auto(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root, proposed = self.make_auto(Path(temporary))
            run(["git", "checkout", "--detach", "-q"], root)
            envelope = start_session(root, "synthesize", "authorised-autonomous-apply", "auto-editor", "test-proposal")
            self.edit(root, envelope["run_id"], proposed)
            with self.assertRaisesRegex(RunError, "detached HEAD"):
                finish_session(root, envelope["run_id"], envelope["run_token"], [])
            terminate_session(root, envelope["run_id"], envelope["run_token"], "failed", "test cleanup")

    def test_merge_and_sparse_states_block_scoped_auto(self) -> None:
        for state in ("merge", "sparse"):
            with self.subTest(state=state), tempfile.TemporaryDirectory() as temporary:
                root, proposed = self.make_auto(Path(temporary))
                envelope = start_session(root, "synthesize", "authorised-autonomous-apply", "auto-editor", "test-proposal")
                self.edit(root, envelope["run_id"], proposed)
                if state == "merge":
                    head = run(["git", "rev-parse", "HEAD"], root).stdout.strip()
                    (root / ".git" / "MERGE_HEAD").write_text(head + "\n", encoding="utf-8")
                    expected = "unresolved merge"
                else:
                    run(["git", "config", "core.sparseCheckout", "true"], root)
                    expected = "sparse checkout"
                with self.assertRaisesRegex(RunError, expected):
                    finish_session(root, envelope["run_id"], envelope["run_token"], [])
                terminate_session(root, envelope["run_id"], envelope["run_token"], "failed", "test cleanup")

    def test_governance_paths_need_explicit_scope(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = make_git_wiki(Path(temporary))
            add_authority(
                root,
                "tool-editor",
                mode="manual-assist",
                lane="semantic",
                action="edit-wiki-pages",
                writable_paths=["tools/**", "reports/runs/**", "reports/latest.json"],
                page_types=["Concept"],
            )
            with self.assertRaisesRegex(ContractError, "output scope"):
                start_session(root, "semantic", "manual-assist", "tool-editor")


if __name__ == "__main__":
    unittest.main()
