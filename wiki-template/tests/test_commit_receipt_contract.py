from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from errors import ContractError, RunError  # noqa: E402
from run_store import load_receipt, save_receipt, save_transaction  # noqa: E402
from run_lib import new_run_id  # noqa: E402


class CommitReceiptContractTests(unittest.TestCase):
    def test_receipt_is_validated_on_write_and_reload(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "schema" / "contracts").mkdir(parents=True)
            for name in ("commit-receipt.schema.json", "git-transaction.schema.json"):
                (root / "schema" / "contracts" / name).write_bytes(
                    (ROOT / "schema" / "contracts" / name).read_bytes()
                )
            run_id = new_run_id()
            receipt = {
                "schema_version": "rb-wiki-commit-receipt/0.2",
                "run_id": run_id,
                "base_commit": "a" * 40,
                "branch_ref": "refs/heads/main",
                "commit_hash": "b" * 40,
                "tree_hash": "c" * 40,
                "changed_paths": ["wiki/index.md"],
                "content_manifest": "d" * 64,
                "verified_at": "2026-07-13T12:00:00Z",
            }
            save_receipt(receipt, root)
            self.assertEqual(load_receipt(root, run_id), receipt)
            path = root / ".wiki_state" / "receipts" / f"{run_id}.json"
            tampered = dict(receipt, changed_paths=["tools/escape.py"])
            path.write_text(json.dumps(tampered), encoding="utf-8")
            with self.assertRaises(RunError):
                save_receipt(receipt, root)

    def test_semantically_impossible_transaction_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "schema" / "contracts").mkdir(parents=True)
            (root / "schema" / "contracts" / "git-transaction.schema.json").write_bytes(
                (ROOT / "schema" / "contracts" / "git-transaction.schema.json").read_bytes()
            )
            run_id = new_run_id()
            transaction = {
                "schema_version": "rb-wiki-git-transaction/0.2",
                "run_id": run_id,
                "stage": "prepared",
                "base_commit": "a" * 40,
                "branch_ref": "refs/heads/main",
                "expected_paths": ["wiki/index.md"],
                "content_manifest": "d" * 64,
                "commit_hash": "b" * 40,
                "tree_hash": "c" * 40,
                "branch_head": None,
                "created_at": "2026-07-13T12:00:00Z",
                "updated_at": "2026-07-13T12:00:00Z",
                "error": None,
            }
            with self.assertRaises(ContractError):
                save_transaction(transaction, root)


if __name__ == "__main__":
    unittest.main()
