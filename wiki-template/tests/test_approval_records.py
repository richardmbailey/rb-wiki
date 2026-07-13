from __future__ import annotations

import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from run_lib import ContractError  # noqa: E402
from semantic_protocol import load_policy_bundle, validate_approval  # noqa: E402
from fake_agent_harness import approval, proposal
from wiki_test_support import make_git_wiki


class ApprovalRecordTests(unittest.TestCase):
    def test_approval_binds_digest_scope_role_and_expiry(self) -> None:
        proposed = proposal("proposal-run", tier="high-consequence")
        record = approval(proposed)
        consequence, domain = load_policy_bundle(ROOT)
        validate_approval(record, proposed, consequence, domain, datetime(2026, 7, 13, tzinfo=timezone.utc), ROOT)
        record["proposal_digest"] = "0" * 64
        with self.assertRaisesRegex(ContractError, "digest"):
            validate_approval(record, proposed, consequence, domain, datetime(2026, 7, 13, tzinfo=timezone.utc), ROOT)

    def test_expired_approval_is_rejected(self) -> None:
        proposed = proposal("proposal-run", tier="high-consequence")
        record = approval(proposed)
        record["expires_at"] = "2026-02-01T00:00:00Z"
        consequence, domain = load_policy_bundle(ROOT)
        with self.assertRaisesRegex(ContractError, "validity window"):
            validate_approval(record, proposed, consequence, domain, datetime(2026, 7, 13, tzinfo=timezone.utc), ROOT)

    def test_manifest_binds_consequence_policy_identity(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = make_git_wiki(Path(temporary))
            policy = root / "schema" / "consequence_policy.yml"
            policy.write_text(
                policy.read_text(encoding="utf-8").replace(
                    "policy_id: domain-neutral-default", "policy_id: substituted-policy"
                ),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ContractError, "policy_id does not match requested identity"):
                load_policy_bundle(root)


if __name__ == "__main__":
    unittest.main()
