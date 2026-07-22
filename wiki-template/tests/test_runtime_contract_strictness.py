from __future__ import annotations

import copy
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from contracts import validate_contract  # noqa: E402
from errors import ContractError  # noqa: E402
from wiki_run import load_session, start_session  # noqa: E402
from wiki_test_support import make_git_wiki  # noqa: E402


class RuntimeContractStrictnessTests(unittest.TestCase):
    def test_run_envelope_rejects_unknown_lane_action_and_malformed_binding(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = make_git_wiki(Path(temporary))
            envelope = start_session(root, "maintain", "scheduled-propose", "test-maintainer")
            mutations = (
                ("lane", "unexpected-lane"),
                ("permitted_actions", ["unexpected-action"]),
                ("lane_contract", {"digest_sha256": "0" * 64}),
            )
            for field, value in mutations:
                with self.subTest(field=field):
                    malformed = copy.deepcopy(envelope)
                    malformed[field] = value
                    with self.assertRaises(ContractError):
                        validate_contract(malformed, "run-envelope", root)

    def test_runtime_session_rejects_malformed_nested_state(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = make_git_wiki(Path(temporary))
            envelope = start_session(root, "maintain", "scheduled-propose", "test-maintainer")
            session = load_session(str(envelope["run_id"]), root)
            malformed_entries = copy.deepcopy(session)
            malformed_entries["initial_entries"] = [{"path": "wiki/index.md"}]
            with self.assertRaises(ContractError):
                validate_contract(malformed_entries, "runtime-session", root)

            malformed_authority = copy.deepcopy(session)
            malformed_authority["authority"] = {"enabled": True}
            with self.assertRaises(ContractError):
                validate_contract(malformed_authority, "runtime-session", root)


if __name__ == "__main__":
    unittest.main()
