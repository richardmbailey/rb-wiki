from __future__ import annotations

import copy
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from lane_runtime import select_lane_contract, validate_lane_authority  # noqa: E402
from errors import ContractError  # noqa: E402
from authority import load_authority, load_runtime_policy, validate_authority  # noqa: E402
from wiki_test_support import make_git_wiki


class AuthorityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.manifest, self.policy = load_runtime_policy(ROOT)
        self.authority = load_authority("disabled-example", ROOT)
        self.authority["enabled"] = True
        self.authority["issued_at"] = "2026-01-01T00:00:00Z"
        self.authority["expires_at"] = "2099-01-01T00:00:00Z"

    def test_expiry_revocation_mode_lane_action_and_budget_are_enforced(self) -> None:
        cases = []
        expired = copy.deepcopy(self.authority)
        expired["expires_at"] = "2026-01-02T00:00:00Z"
        cases.append(expired)
        revoked = copy.deepcopy(self.authority)
        revoked["revoked_at"] = "2026-02-01T00:00:00Z"
        cases.append(revoked)
        mode = copy.deepcopy(self.authority)
        mode["modes"] = ["manual-assist"]
        cases.append(mode)
        lane = copy.deepcopy(self.authority)
        lane["lanes"] = ["semantic"]
        cases.append(lane)
        budget = copy.deepcopy(self.authority)
        budget["budgets"]["max_changed_paths"] = self.policy["limits"]["max_changed_files"] + 1
        cases.append(budget)
        for authority in cases:
            with self.subTest(authority=authority):
                with self.assertRaises(ContractError):
                    validate_authority(
                        authority,
                        self.policy,
                        "maintain",
                        "scheduled-propose",
                        datetime(2026, 7, 13, tzinfo=timezone.utc),
                    )

    def test_lane_contract_owns_action_enforcement(self) -> None:
        authority = copy.deepcopy(self.authority)
        authority["actions"] = ["edit-wiki-pages"]
        contract = select_lane_contract(ROOT, "maintain")["contract"]
        with self.assertRaisesRegex(ContractError, "requires action"):
            validate_lane_authority(contract, authority, "scheduled-propose")

    def test_authority_selection_is_exact_with_no_fallback(self) -> None:
        with self.assertRaises(ContractError):
            load_authority("disabled", ROOT)

    def test_template_grant_is_not_active(self) -> None:
        authority = load_authority("disabled-example", ROOT)
        with self.assertRaisesRegex(ContractError, "disabled"):
            validate_authority(authority, self.policy, "maintain", "scheduled-propose")


if __name__ == "__main__":
    unittest.main()
