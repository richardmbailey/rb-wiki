from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from semantic_protocol import validate_proposal  # noqa: E402
from wiki_run import finish_session, start_session  # noqa: E402
from wiki_test_support import make_git_wiki
from fake_agent_harness import add_proposal_authority, proposal, write_proposal_run


class ProposalArtifactTests(unittest.TestCase):
    def test_scheduled_proposal_is_attributed_and_artifact_only(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = make_git_wiki(Path(temporary))
            add_proposal_authority(root, "routine")
            envelope = start_session(root, "synthesize", "scheduled-propose", "proposal-agent")
            record = proposal(envelope["run_id"], with_payload=False)
            write_proposal_run(root, envelope["run_id"], record)
            code, result = finish_session(root, envelope["run_id"], envelope["run_token"], ["quick-lint=pass"])
            self.assertEqual(code, 3)
            self.assertNotIn("wiki/syntheses/agent-synthesis.md", result["changed_paths"])

    def test_payload_hash_and_digest_are_enforced(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = make_git_wiki(Path(temporary))
            record = proposal("proposal-run")
            record["apply_payload"]["files"][0]["content"] += "tampered"
            with self.assertRaisesRegex(Exception, "hash mismatch"):
                validate_proposal(record, root)


if __name__ == "__main__":
    unittest.main()
