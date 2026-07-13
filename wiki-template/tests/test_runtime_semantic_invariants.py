from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from errors import ContractError  # noqa: E402
from wiki_run import new_record  # noqa: E402
from run_lib import validate_run_record  # noqa: E402


class RuntimeSemanticInvariantTests(unittest.TestCase):
    def record(self):
        return new_record(
            "20260713T120000Z-abcdef123456", "wiki", "maintain", "scheduled-propose", "grant", [],
            {"schema_version": "rb-wiki-lane-contract/0.2", "lane_id": "deterministic-maintain", "controller_lane": "maintain", "path": "schema/lanes/deterministic-maintain.yml", "digest_sha256": "a" * 64},
            ROOT,
        )

    def test_schema_valid_impossible_combinations_are_rejected(self) -> None:
        mutations = [
            {"updated_at": "2020-01-01T00:00:00Z"},
            {"state": "completed", "result": "failed", "finished_at": "2026-07-13T12:00:00Z"},
            {"state": "failed", "result": "success", "finished_at": "2026-07-13T12:00:00Z"},
            {"state": "running", "result": "success"},
            {"report_class": "durable-mutation", "material": False},
            {"durable_record": "reports/runs/another-run.json"},
            {"commit_hash": "a" * 40},
            {"heartbeat_at": "2026-07-13T12:00:00Z", "lease_expires_at": None},
            {"checks": [{"check_id": "provenance", "status": "pass", "summary": "spoofed", "provenance": "external-attestation"}]},
        ]
        for mutation in mutations:
            record = self.record()
            record.update(mutation)
            with self.subTest(mutation=mutation), self.assertRaises(ContractError):
                validate_run_record(record, ROOT)

    def test_non_self_referential_commit_snapshots_are_valid(self) -> None:
        record = self.record()
        record.update(
            state="completed",
            result="success",
            finished_at=record["updated_at"],
            material=True,
            report_class="durable-mutation",
            durable_record=f"reports/runs/{record['run_id']}.json",
            content_manifest="b" * 64,
            transaction=f".wiki_state/transactions/{record['run_id']}.json",
            transaction_stage="prepared",
        )
        validate_run_record(record, ROOT)
        record.update(commit_hash="c" * 40, transaction_stage="index-refreshed")
        validate_run_record(record, ROOT)
        record["transaction_stage"] = "reconciled"
        validate_run_record(record, ROOT)


if __name__ == "__main__":
    unittest.main()
