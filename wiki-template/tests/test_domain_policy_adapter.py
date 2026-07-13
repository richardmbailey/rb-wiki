from __future__ import annotations

import copy
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


class DomainPolicyAdapterTests(unittest.TestCase):
    def test_adapter_can_tighten_source_admissibility_without_core_branching(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = make_git_wiki(Path(temporary))
            consequence, domain = load_policy_bundle(root)
            restricted = copy.deepcopy(domain)
            restricted["enabled"] = True
            restricted["allowed_source_types"] = ["pdf"]
            with self.assertRaisesRegex(ContractError, "rejects source types"):
                validate_proposal(proposal("run"), root, consequence=consequence, domain=restricted)

    def test_generic_adapter_starts_disabled_and_without_local_ontology(self) -> None:
        _consequence, domain = load_policy_bundle(ROOT)
        self.assertFalse(domain["enabled"])
        self.assertEqual(domain["ontology"], {})
        self.assertEqual(domain["source_hierarchy"], [])


if __name__ == "__main__":
    unittest.main()
