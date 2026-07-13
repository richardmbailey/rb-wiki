from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from run_lib import ContractError  # noqa: E402
from wiki_run import finish_session, start_session  # noqa: E402
from wiki_test_support import make_git_wiki
from fake_agent_harness import add_apply_authority, commit_artifact, proposal, write_apply_run


class AutonomousApplyScopeTests(unittest.TestCase):
    def prepared(self, parent: Path):
        root = make_git_wiki(parent)
        add_apply_authority(root, "routine")
        proposed = proposal("prior-proposal-run")
        commit_artifact(root, "reports/proposals/test-proposal.json", proposed, "add proposal")
        return root, proposed

    def test_exact_bounded_apply_succeeds(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root, proposed = self.prepared(Path(temporary))
            envelope = start_session(
                root, "synthesize", "authorised-autonomous-apply", "apply-agent", "test-proposal"
            )
            write_apply_run(root, envelope["run_id"], proposed)
            code, record = finish_session(root, envelope["run_id"], envelope["run_token"], ["quick-lint=pass"])
            self.assertEqual(code, 0)
            self.assertEqual(record["state"], "completed")
            self.assertIsNotNone(record["commit_hash"])

    def test_content_outside_exact_payload_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root, proposed = self.prepared(Path(temporary))
            envelope = start_session(
                root, "synthesize", "authorised-autonomous-apply", "apply-agent", "test-proposal"
            )
            write_apply_run(root, envelope["run_id"], proposed, content=proposed["apply_payload"]["files"][0]["content"] + "extra")
            with self.assertRaisesRegex(ContractError, "does not match approved target"):
                finish_session(root, envelope["run_id"], envelope["run_token"], ["quick-lint=pass"])


if __name__ == "__main__":
    unittest.main()
