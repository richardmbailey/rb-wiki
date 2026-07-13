from __future__ import annotations

import copy
import sys
import tempfile
import unittest
from pathlib import Path

from wiki_test_support import make_git_wiki

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from run_lib import ContractError  # noqa: E402
from semantic_protocol import load_policy_bundle, validate_domain_precedence  # noqa: E402


class PolicyPrecedenceTests(unittest.TestCase):
    def test_domain_policy_may_tighten_but_not_weaken_core(self) -> None:
        consequence, domain = load_policy_bundle(ROOT)
        tightened = copy.deepcopy(domain)
        tightened["enabled"] = True
        tightened["action_minimum_tiers"] = {"new-synthesis": "material"}
        validate_domain_precedence(consequence, tightened)
        weakened = copy.deepcopy(tightened)
        weakened["action_minimum_tiers"] = {"contradiction-resolution": "routine"}
        with self.assertRaisesRegex(ContractError, "weakens core"):
            validate_domain_precedence(consequence, weakened)

    def test_core_invariants_are_schema_constants(self) -> None:
        schema = (ROOT / "schema" / "contracts" / "domain-policy.schema.json").read_text(encoding="utf-8")
        self.assertGreaterEqual(schema.count('"const": true'), 3)

    def test_broken_domain_policy_symlink_is_not_treated_as_absent(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = make_git_wiki(Path(temporary))
            policy = root / "schema" / "domain_policy.yml"
            policy.unlink()
            policy.symlink_to(root / "missing-domain-policy.yml")
            with self.assertRaisesRegex(ContractError, "must not be a symlink"):
                load_policy_bundle(root)


if __name__ == "__main__":
    unittest.main()
