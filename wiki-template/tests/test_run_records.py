from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from run_lib import atomic_write_json, new_run_id, render_run_markdown, unexpected_paths, validate_run_record  # noqa: E402


class RunRecordTests(unittest.TestCase):
    def test_atomic_json_is_canonical_and_replaces_existing_file(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "record.json"
            atomic_write_json(path, {"z": 1, "a": 2}, path.parent)
            atomic_write_json(path, {"b": 3, "a": 4}, path.parent)
            self.assertEqual(path.read_text(encoding="utf-8"), '{"a":4,"b":3}\n')
            self.assertEqual(json.loads(path.read_text(encoding="utf-8")), {"a": 4, "b": 3})

    def test_run_id_shape_and_record_contract(self) -> None:
        run_id = new_run_id()
        record = {
            "schema_version": "rb-wiki-run-record/0.2",
            "run_id": run_id,
            "wiki_id": "test-wiki",
            "lane": "maintain",
            "mode": "scheduled-propose",
            "authority_id": "test",
            "lane_contract": {
                "schema_version": "rb-wiki-lane-contract/0.2",
                "lane_id": "deterministic-maintain",
                "controller_lane": "maintain",
                "path": "schema/lanes/deterministic-maintain.yml",
                "digest_sha256": "a" * 64,
            },
            "state": "created",
            "result": None,
            "started_at": "2026-07-13T10:00:00Z",
            "updated_at": "2026-07-13T10:00:00Z",
            "finished_at": None,
            "heartbeat_at": None,
            "lease_expires_at": None,
            "base_commit": None,
            "initial_status": [],
            "initial_snapshot": [],
            "final_snapshot": [],
            "changed_paths": [],
            "writable_paths": ["wiki/index.md"],
            "checks": [],
            "capabilities": {
                "schema_version": "rb-wiki-capabilities/0.2",
                "digest_sha256": "a" * 64,
                "capabilities": {},
            },
            "agent_provenance": None,
            "material": False,
            "report_class": "ephemeral-telemetry",
            "durable_record": None,
            "commit_hash": None,
            "content_manifest": None,
            "transaction": None,
            "transaction_stage": None,
            "next_action": "Wait.",
            "error": None,
        }
        validate_run_record(record, ROOT)
        self.assertIn(run_id, render_run_markdown(record))

    def test_changed_path_reconciliation(self) -> None:
        outside = unexpected_paths(
            ["wiki/index.md", ".wiki_cache/graph.json", "reports/runs/a.json", "tools/unexpected.py"],
            ["wiki/index.md", ".wiki_cache/graph.json", "reports/runs/**"],
        )
        self.assertEqual(outside, ["tools/unexpected.py"])


if __name__ == "__main__":
    unittest.main()
