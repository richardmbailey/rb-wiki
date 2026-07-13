from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from errors import ContractError  # noqa: E402
from agent_provenance import validate_agent_provenance  # noqa: E402
from wiki_run import start_session, terminate_session  # noqa: E402
from wiki_test_support import add_authority, make_git_wiki  # noqa: E402


class AgentProvenanceContractTests(unittest.TestCase):
    def metadata(self):
        return {
            "schema_version": "rb-wiki-agent-provenance/0.2", "agent_label": "review-agent",
            "runtime": "codex/1", "provider_model": None, "prompt_policy_digest": "a" * 64,
            "trace_reference": "reports/traces/run-1.json", "started_at": None, "finished_at": None,
            "tool_call_summary": {"read": 3, "write": 1},
        }

    def test_valid_and_absent_metadata_are_preserved_without_inference(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = make_git_wiki(Path(temporary))
            add_authority(root, "manual", mode="manual-assist", lane="semantic", action="edit-wiki-pages", writable_paths=["wiki/concepts/**", "reports/runs/**", "reports/latest.json"], page_types=["Concept"])
            envelope = start_session(root, "semantic", "manual-assist", "manual", agent_provenance=self.metadata())
            self.assertEqual(envelope["agent_provenance"]["agent_label"], "review-agent")
            terminate_session(root, envelope["run_id"], envelope["run_token"], "cancelled", "test")
            offset = self.metadata()
            offset["started_at"] = "2026-07-13T12:00:00+02:00"
            offset["finished_at"] = "2026-07-13T10:30:00Z"
            self.assertEqual(validate_agent_provenance(offset, root), offset)

    def test_secret_and_malformed_or_oversized_metadata_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = make_git_wiki(Path(temporary))
            secret = self.metadata(); secret["agent_label"] = "api_key=supersecret"
            with self.assertRaises(ContractError):
                validate_agent_provenance(secret, root)
            malformed = self.metadata(); malformed["trace_reference"] = "https://outside/trace"
            with self.assertRaises(ContractError):
                validate_agent_provenance(malformed, root)
            escaped = self.metadata(); escaped["trace_reference"] = "reports/../outside.json"
            with self.assertRaises(ContractError):
                validate_agent_provenance(escaped, root)
            oversized = self.metadata(); oversized["agent_label"] = "x" * 129
            with self.assertRaises(ContractError):
                validate_agent_provenance(oversized, root)
            reversed_time = self.metadata()
            reversed_time["started_at"] = "2026-07-13T12:00:00+02:00"
            reversed_time["finished_at"] = "2026-07-13T09:59:59Z"
            with self.assertRaises(ContractError):
                validate_agent_provenance(reversed_time, root)


if __name__ == "__main__":
    unittest.main()
