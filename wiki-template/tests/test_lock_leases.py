from __future__ import annotations

import json
import socket
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from wiki_run import break_lock  # noqa: E402
import wiki_run  # noqa: E402
from run_lib import RunError  # noqa: E402
from wiki_test_support import add_authority, make_git_wiki


class BreakLockTests(unittest.TestCase):
    def test_break_lock_requires_governance_and_preserves_audit(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = make_git_wiki(Path(temporary))
            add_authority(
                root,
                "governor",
                mode="manual-assist",
                lane="governance",
                action="governance-maintenance",
                writable_paths=["reports/runs/**", "reports/latest.json"],
                governance=True,
            )
            lock = root / ".wiki_state" / "mutation.lock"
            lock.mkdir(parents=True)
            owner = {
                "schema_version": "rb-wiki-mutation-lock/0.2",
                "run_id": "missing-session",
                "pid": 99999999,
                "host": socket.gethostname(),
                "lane": "maintain",
                "mode": "scheduled-propose",
                "acquired_at": "2026-01-01T00:00:00Z",
            }
            (lock / "owner.json").write_text(json.dumps(owner), encoding="utf-8")
            record = break_lock(root, "governor", "human-operator", "confirmed dead test process")
            self.assertFalse(lock.exists())
            self.assertTrue((root / ".wiki_state" / "broken-locks" / record["run_id"] / "owner.json").exists())
            self.assertTrue((root / "reports" / "runs" / f"{record['run_id']}.json").exists())
            self.assertIn("observed_owner", record["checks"][0]["summary"])

    def test_break_lock_rejects_uncommitted_authority_expansion(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = make_git_wiki(Path(temporary))
            add_authority(
                root,
                "mutable-grant",
                mode="manual-assist",
                lane="maintain",
                action="deterministic-maintenance",
                writable_paths=["wiki/index.md", ".wiki_cache/graph.json", "reports/runs/**", "reports/latest.json"],
            )
            grant = root / "schema" / "authorities" / "mutable-grant.yml"
            grant.write_text(
                grant.read_text(encoding="utf-8")
                .replace("lanes: [maintain]", "lanes: [governance]")
                .replace("actions: [deterministic-maintenance]", "actions: [governance-maintenance]")
                .replace("governance_maintenance: false", "governance_maintenance: true"),
                encoding="utf-8",
            )
            lock = root / ".wiki_state" / "mutation.lock"
            lock.mkdir(parents=True)
            (lock / "owner.json").write_text(
                json.dumps(
                    {
                        "schema_version": "rb-wiki-mutation-lock/0.2",
                        "run_id": "missing-session",
                        "pid": 99999999,
                        "host": socket.gethostname(),
                        "lane": "maintain",
                        "mode": "scheduled-propose",
                        "acquired_at": "2026-01-01T00:00:00Z",
                    }
                ),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(RunError, "governance-maintenance authority"):
                break_lock(root, "mutable-grant", "human-operator", "confirmed dead test process")
            self.assertTrue(lock.exists())

    def test_break_lock_does_not_report_success_before_displacement(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = make_git_wiki(Path(temporary))
            add_authority(
                root,
                "governor",
                mode="manual-assist",
                lane="governance",
                action="governance-maintenance",
                writable_paths=["reports/runs/**", "reports/latest.json"],
                governance=True,
            )
            lock = root / ".wiki_state" / "mutation.lock"
            lock.mkdir(parents=True)
            (lock / "owner.json").write_text(
                json.dumps(
                    {
                        "schema_version": "rb-wiki-mutation-lock/0.2",
                        "run_id": "missing-session",
                        "pid": 99999999,
                        "host": socket.gethostname(),
                        "lane": "maintain",
                        "mode": "scheduled-propose",
                        "acquired_at": "2026-01-01T00:00:00Z",
                    }
                ),
                encoding="utf-8",
            )
            real_replace = wiki_run.os.replace

            def fail_lock_displacement(source: str | Path, destination: str | Path) -> None:
                if Path(source) == lock:
                    raise OSError("forced move failure")
                real_replace(source, destination)

            with patch.object(wiki_run.os, "replace", side_effect=fail_lock_displacement):
                with self.assertRaisesRegex(RunError, "original lock remains in place"):
                    break_lock(root, "governor", "human-operator", "forced move-failure test")

            self.assertTrue(lock.exists())
            reports = list((root / "reports" / "runs").glob("*.json"))
            self.assertEqual(len(reports), 1)
            report = json.loads(reports[0].read_text(encoding="utf-8"))
            self.assertEqual(report["state"], "failed")
            self.assertEqual(report["result"], "failed")
            self.assertIn("lock displacement failed", report["error"])


if __name__ == "__main__":
    unittest.main()
