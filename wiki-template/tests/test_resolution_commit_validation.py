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
from wiki_run import finish_session, record_resolution, start_session  # noqa: E402
from wiki_test_support import add_authority, make_git_wiki, run  # noqa: E402
from fake_agent_harness import commit_artifact, proposal, write_apply_run  # noqa: E402


class ResolutionCommitValidationTests(unittest.TestCase):
    def make_manual(self, parent: Path):
        root = make_git_wiki(parent)
        add_authority(
            root, "manual-editor", mode="manual-assist", lane="semantic",
            action="edit-wiki-pages", writable_paths=["wiki/concepts/**", "reports/runs/**", "reports/latest.json"],
            page_types=["Concept"],
        )
        add_authority(
            root, "manual-resolver", mode="manual-assist", lane="semantic",
            action="edit-wiki-pages", writable_paths=["reports/resolutions/**", "reports/runs/**", "reports/latest.json"],
            page_types=[],
        )
        envelope = start_session(root, "semantic", "manual-assist", "manual-editor")
        page = root / "wiki" / "concepts" / "frontmatter.md"
        page.write_text(page.read_text(encoding="utf-8") + "\nManual resolution content.\n", encoding="utf-8")
        _code, record = finish_session(root, envelope["run_id"], envelope["run_token"], [])
        return root, record

    def test_nonexistent_tree_and_blob_ids_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root, record = self.make_manual(Path(temporary))
            blob = run(["git", "rev-parse", "HEAD:wiki/index.md"], root).stdout.strip()
            tree = run(["git", "rev-parse", "HEAD^{tree}"], root).stdout.strip()
            for value in ["f" * 40, blob, tree]:
                with self.subTest(value=value), self.assertRaisesRegex(RunError, "commit object"):
                    record_resolution(root, record["run_id"], "manual-resolver", "reviewer", "checked", value)
            for malformed in ["abc1234", "g" * 40, "a" * 39, "a" * 41]:
                with self.subTest(malformed=malformed), self.assertRaisesRegex(RunError, "invalid resolution"):
                    record_resolution(
                        root, record["run_id"], "manual-resolver", "reviewer", "checked", malformed
                    )

    def test_unrelated_and_wrong_run_commits_are_rejected_and_human_commit_is_accepted(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root, record = self.make_manual(Path(temporary))
            tree = run(["git", "rev-parse", "HEAD^{tree}"], root).stdout.strip()
            unrelated = run(["git", "commit-tree", tree, "-m", "unrelated"], root).stdout.strip()
            with self.assertRaisesRegex(RunError, "unrelated"):
                record_resolution(
                    root, record["run_id"], "manual-resolver", "reviewer", "checked", unrelated
                )
            run(["git", "add", "-A"], root)
            run(["git", "commit", "-m", "manual commit\n\nRB-Wiki-Run: another-run"], root)
            wrong = run(["git", "rev-parse", "HEAD"], root).stdout.strip()
            with self.assertRaisesRegex(RunError, "another or ambiguous"):
                record_resolution(root, record["run_id"], "manual-resolver", "reviewer", "checked", wrong)
            run(["git", "commit", "--amend", "-m", "human reviewed commit"], root)
            human = run(["git", "rev-parse", "HEAD"], root).stdout.strip()
            resolution = record_resolution(
                root, record["run_id"], "manual-resolver", "reviewer", "checked", human
            )
            self.assertEqual(resolution["commit_classification"], "human-acknowledgement")

    def test_exact_recorded_managed_commit_is_classified_as_reconciled_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = make_git_wiki(Path(temporary))
            add_authority(
                root, "auto-editor", mode="authorised-autonomous-apply", lane="synthesize",
                action="edit-wiki-pages",
                writable_paths=["wiki/concepts/**", "reports/semantic/**", "reports/runs/**", "reports/latest.json"],
                page_types=["Concept"], commit_policy="scoped-auto",
            )
            add_authority(
                root, "manual-resolver", mode="manual-assist", lane="semantic",
                action="edit-wiki-pages",
                writable_paths=["reports/resolutions/**", "reports/runs/**", "reports/latest.json"],
                page_types=[],
            )
            page = root / "wiki" / "concepts" / "frontmatter.md"
            proposed = proposal(
                "prior-proposal-run", path="wiki/concepts/frontmatter.md",
                content=page.read_text(encoding="utf-8") + "\nManaged resolution evidence.\n",
                action_class="semantic-maintenance",
            )
            commit_artifact(root, "reports/proposals/test-proposal.json", proposed, "add resolution proposal")
            envelope = start_session(
                root, "synthesize", "authorised-autonomous-apply", "auto-editor", "test-proposal"
            )
            write_apply_run(root, envelope["run_id"], proposed)
            os.environ["RB_WIKI_FAULT_STAGE"] = "after-cas"
            try:
                code, record = finish_session(
                    root, envelope["run_id"], envelope["run_token"], []
                )
            finally:
                os.environ.pop("RB_WIKI_FAULT_STAGE", None)
            self.assertEqual(code, 5)
            resolution = record_resolution(
                root, record["run_id"], "manual-resolver", "reviewer", "audited managed commit",
                record["commit_hash"],
            )
            self.assertEqual(resolution["commit_classification"], "managed-reconciled")
            original = json.loads(
                (root / ".wiki_state" / "runs" / f"{record['run_id']}.json").read_text()
            )
            self.assertEqual(original["state"], "committed-recovery-required")


if __name__ == "__main__":
    unittest.main()
