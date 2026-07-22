from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from run_lib import ContractError, RunError  # noqa: E402
from wiki_run import finish_session, start_session  # noqa: E402
from wiki_test_support import make_git_wiki, run
from fake_agent_harness import (
    add_apply_authority,
    add_proposal_authority,
    approval,
    commit_artifact,
    proposal,
    write_apply_run,
    write_proposal_run,
)


class HighConsequenceTwoRunTests(unittest.TestCase):
    def prepare_proposal(self, root: Path):
        add_proposal_authority(root)
        add_apply_authority(root)
        envelope = start_session(root, "synthesize", "scheduled-propose", "proposal-agent")
        proposed = proposal(envelope["run_id"], tier="high-consequence")
        write_proposal_run(root, envelope["run_id"], proposed)
        code, record = finish_session(root, envelope["run_id"], envelope["run_token"], [])
        self.assertEqual((code, record["state"]), (4, "approval-required"))
        run(["git", "add", "."], root)
        run(["git", "commit", "-q", "-m", "commit high consequence proposal"], root)
        return proposed

    def test_apply_requires_separately_committed_approval(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = make_git_wiki(Path(temporary))
            proposed = self.prepare_proposal(root)
            with self.assertRaises((RunError, ContractError)):
                start_session(
                    root, "synthesize", "authorised-autonomous-apply", "apply-agent", proposed["proposal_id"]
                )
            approved = approval(proposed)
            commit_artifact(root, "reports/approvals/test-approval.json", approved, "record approval")
            envelope = start_session(
                root,
                "synthesize",
                "authorised-autonomous-apply",
                "apply-agent",
                proposed["proposal_id"],
                approved["approval_id"],
            )
            write_apply_run(root, envelope["run_id"], proposed)
            code, record = finish_session(root, envelope["run_id"], envelope["run_token"], [])
            self.assertEqual(code, 0)
            self.assertEqual(record["state"], "completed")

    def test_proposal_change_invalidates_prior_approval(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = make_git_wiki(Path(temporary))
            proposed = self.prepare_proposal(root)
            approved = approval(proposed)
            commit_artifact(root, "reports/approvals/test-approval.json", approved, "record approval")
            changed = proposal(proposed["run_id"], tier="high-consequence", content=proposed["apply_payload"]["files"][0]["content"] + "\nchanged\n")
            commit_artifact(root, "reports/proposals/test-proposal.json", changed, "change proposal")
            with self.assertRaisesRegex(ContractError, "digest"):
                start_session(
                    root, "synthesize", "authorised-autonomous-apply", "apply-agent", "test-proposal", "test-approval"
                )

    def test_requested_proposal_and_approval_ids_match_internal_identities(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = make_git_wiki(Path(temporary))
            add_apply_authority(root)
            mismatched = proposal(
                "prior-proposal-run", proposal_id="internal-proposal", tier="high-consequence"
            )
            commit_artifact(
                root,
                "reports/proposals/requested-proposal.json",
                mismatched,
                "commit proposal identity mismatch",
            )
            with self.assertRaisesRegex(ContractError, "proposal_id does not match requested identity"):
                start_session(
                    root,
                    "synthesize",
                    "authorised-autonomous-apply",
                    "apply-agent",
                    "requested-proposal",
                )

        with tempfile.TemporaryDirectory() as temporary:
            root = make_git_wiki(Path(temporary))
            add_apply_authority(root)
            proposed = proposal("prior-proposal-run", tier="high-consequence")
            commit_artifact(
                root, "reports/proposals/test-proposal.json", proposed, "commit proposal for approval identity"
            )
            mismatched_approval = approval(proposed, approval_id="internal-approval")
            commit_artifact(
                root,
                "reports/approvals/requested-approval.json",
                mismatched_approval,
                "commit approval identity mismatch",
            )
            with self.assertRaisesRegex(ContractError, "approval_id does not match requested identity"):
                start_session(
                    root,
                    "synthesize",
                    "authorised-autonomous-apply",
                    "apply-agent",
                    "test-proposal",
                    "requested-approval",
                )


if __name__ == "__main__":
    unittest.main()
