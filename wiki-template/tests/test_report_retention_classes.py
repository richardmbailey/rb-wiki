from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from run_lib import RunError, atomic_write_json  # noqa: E402
from wiki_run import new_record, persist_durable_record, prune_ephemeral_records  # noqa: E402
from wiki_test_support import make_git_wiki


class ReportRetentionClassTests(unittest.TestCase):
    def old_record(
        self, root: Path, state: str = "completed", run_id: str = "20260101T000000Z-abcdefabcdef"
    ) -> tuple[dict[str, object], Path]:
        record = new_record(
            run_id,
            "test-wiki",
            "maintain",
            "scheduled-propose",
            "test",
            [],
            {
                "schema_version": "rb-wiki-lane-contract/0.2",
                "lane_id": "deterministic-maintain",
                "controller_lane": "maintain",
                "path": "schema/lanes/deterministic-maintain.yml",
                "digest_sha256": "a" * 64,
            },
        )
        record.update(
            state=state,
            result="no-op" if state == "completed" else None,
            started_at="2026-01-01T00:00:00Z",
            updated_at="2026-01-01T00:00:00Z",
            finished_at="2026-01-01T00:00:00Z" if state == "completed" else None,
        )
        path = root / ".wiki_state" / "runs" / f"{record['run_id']}.json"
        atomic_write_json(path, record, root)
        return record, path

    def test_prune_is_dry_run_by_default_and_never_prunes_live_state(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = make_git_wiki(Path(temporary))
            _record, expired = self.old_record(root)
            _live, live_path = self.old_record(root, "running", "20260101T000000Z-fedcbafedcba")
            candidates = prune_ephemeral_records(
                root, 30, now=datetime(2026, 7, 13, tzinfo=timezone.utc)
            )
            self.assertEqual(candidates, [expired.relative_to(root).as_posix()])
            self.assertTrue(expired.exists())
            prune_ephemeral_records(
                root, 30, dry_run=False, now=datetime(2026, 7, 13, tzinfo=timezone.utc)
            )
            self.assertFalse(expired.exists())
            self.assertTrue(live_path.exists())

    def test_durable_classification_and_latest_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = make_git_wiki(Path(temporary))
            record, _path = self.old_record(root)
            record.update(material=True, result="success")
            persist_durable_record(record, root)
            self.assertEqual(record["report_class"], "durable-mutation")
            latest = json.loads((root / "reports" / "latest.json").read_text(encoding="utf-8"))
            self.assertEqual(latest["report_class"], "durable-mutation")
            self.assertIn("capabilities", latest)
            self.assertEqual(prune_ephemeral_records(root, 30, now=datetime(2026, 7, 13, tzinfo=timezone.utc)), [])

    def test_prune_refuses_symlinked_runtime_state(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            parent = Path(temporary)
            root = make_git_wiki(parent)
            external = parent / "external-state"
            runs = external / "runs"
            runs.mkdir(parents=True)
            state = root / ".wiki_state"
            if state.exists():
                shutil.rmtree(state)
            state.symlink_to(external, target_is_directory=True)
            marker = runs / "keep.json"
            marker.write_text("{}\n", encoding="utf-8")
            with self.assertRaisesRegex(RunError, "through symlink"):
                prune_ephemeral_records(root, 30, dry_run=False)
            self.assertTrue(marker.exists())


if __name__ == "__main__":
    unittest.main()
