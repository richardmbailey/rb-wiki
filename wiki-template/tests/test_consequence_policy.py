from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from run_lib import ContractError  # noqa: E402
from semantic_protocol import load_policy_bundle, validate_proposal  # noqa: E402
from wiki_test_support import make_git_wiki
from fake_agent_harness import proposal


class ConsequencePolicyTests(unittest.TestCase):
    def test_contradiction_resolution_requires_high_consequence(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = make_git_wiki(Path(temporary))
            proposed = proposal(
                "run", tier="material", action_class="contradiction-resolution", contradictions=["conflicting claims"]
            )
            with self.assertRaisesRegex(ContractError, "below required tier high-consequence"):
                validate_proposal(proposed, root)

    def test_tiers_are_based_on_intended_action_not_source_domain(self) -> None:
        consequence, _domain = load_policy_bundle(ROOT)
        self.assertEqual(consequence["action_minimum_tiers"]["new-synthesis"], "routine")
        self.assertEqual(consequence["action_minimum_tiers"]["contradiction-resolution"], "high-consequence")


if __name__ == "__main__":
    unittest.main()
