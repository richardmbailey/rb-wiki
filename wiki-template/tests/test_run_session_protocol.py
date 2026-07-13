from __future__ import annotations

import json
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from run_lib import RunError  # noqa: E402
from wiki_run import heartbeat_session, start_session, status_session, finish_session, terminate_session  # noqa: E402
from wiki_test_support import add_authority, make_git_wiki, run


class RunSessionProtocolTests(unittest.TestCase):
    def make_manual(self, parent: Path) -> Path:
        root = make_git_wiki(parent)
        add_authority(
            root,
            "manual-editor",
            mode="manual-assist",
            lane="semantic",
            action="edit-wiki-pages",
            writable_paths=["wiki/concepts/**", "reports/runs/**", "reports/latest.json"],
            page_types=["Concept"],
        )
        return root

    def test_external_agent_start_heartbeat_status_and_finish(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = self.make_manual(Path(temporary))
            envelope = start_session(root, "semantic", "manual-assist", "manual-editor")
            self.assertIn("run_token", envelope)
            renewed = heartbeat_session(root, envelope["run_id"], envelope["run_token"])
            self.assertEqual(renewed["state"], "running")
            owner = json.loads((root / ".wiki_state" / "mutation.lock" / "owner.json").read_text(encoding="utf-8"))
            self.assertEqual(owner["heartbeat_at"], status_session(root, envelope["run_id"])["heartbeat_at"])
            self.assertEqual(owner["lease_expires_at"], renewed["lease_expires_at"])
            status = status_session(root, envelope["run_id"])
            self.assertNotIn("run_token", status)
            code, record = finish_session(root, envelope["run_id"], envelope["run_token"], ["quick-lint=pass"])
            self.assertEqual(code, 0)
            self.assertEqual(record["result"], "no-op")
            self.assertFalse((root / ".wiki_state" / "mutation.lock").exists())

    def test_cli_protocol_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = self.make_manual(Path(temporary))
            started = run(
                [
                    sys.executable,
                    "tools/wiki_run.py",
                    "start",
                    "--lane",
                    "semantic",
                    "--mode",
                    "manual-assist",
                    "--authority",
                    "manual-editor",
                ],
                root,
            )
            envelope = json.loads(started.stdout)
            run(
                [
                    sys.executable,
                    "tools/wiki_run.py",
                    "heartbeat",
                    "--run-id",
                    envelope["run_id"],
                    "--token",
                    envelope["run_token"],
                ],
                root,
            )
            status = run(
                [sys.executable, "tools/wiki_run.py", "status", "--run-id", envelope["run_id"]], root
            )
            self.assertNotIn(envelope["run_token"], status.stdout)
            finished = run(
                [
                    sys.executable,
                    "tools/wiki_run.py",
                    "finish",
                    "--run-id",
                    envelope["run_id"],
                    "--token",
                    envelope["run_token"],
                    "--check",
                    "quick-lint=pass",
                ],
                root,
            )
            self.assertEqual(json.loads(finished.stdout)["state"], "completed")

    def test_generated_token_cannot_look_like_a_command_line_option(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = self.make_manual(Path(temporary))
            with patch("wiki_run.secrets.token_urlsafe", return_value="-" + "a" * 42):
                envelope = start_session(root, "semantic", "manual-assist", "manual-editor")
            self.assertTrue(envelope["run_token"].startswith("run_"))
            self.assertFalse(envelope["run_token"].startswith("-"))

    def test_token_mismatch_is_rejected_without_leaking_token(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = self.make_manual(Path(temporary))
            envelope = start_session(root, "semantic", "manual-assist", "manual-editor")
            with self.assertRaisesRegex(RunError, "token mismatch"):
                heartbeat_session(root, envelope["run_id"], "wrong-token")
            status_text = json.dumps(status_session(root, envelope["run_id"]))
            self.assertNotIn(envelope["run_token"], status_text)

    def test_injectable_clock_reports_stale_lease_without_breaking_lock(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = self.make_manual(Path(temporary))
            envelope = start_session(root, "semantic", "manual-assist", "manual-editor")
            future = datetime.now(timezone.utc) + timedelta(hours=1)
            status = status_session(root, envelope["run_id"], now=future)
            self.assertTrue(status["lease_stale"])
            self.assertTrue((root / ".wiki_state" / "mutation.lock").exists())

    def test_authority_is_revalidated_for_revocation_at_closure(self) -> None:
        class FutureDateTime(datetime):
            @classmethod
            def now(cls, tz=None):
                value = datetime(2028, 1, 1, tzinfo=timezone.utc)
                return value if tz is None else value.astimezone(tz)

        with tempfile.TemporaryDirectory() as temporary:
            root = self.make_manual(Path(temporary))
            grant = root / "schema" / "authorities" / "manual-editor.yml"
            grant.write_text(
                grant.read_text(encoding="utf-8").replace("revoked_at: null", 'revoked_at: "2027-01-01T00:00:00Z"'),
                encoding="utf-8",
            )
            run(["git", "add", grant.relative_to(root).as_posix()], root)
            run(["git", "commit", "-q", "-m", "schedule authority revocation"], root)
            envelope = start_session(root, "semantic", "manual-assist", "manual-editor")
            with patch("wiki_run.datetime", FutureDateTime):
                with self.assertRaisesRegex(RunError, "revoked"):
                    finish_session(root, envelope["run_id"], envelope["run_token"], ["quick-lint=pass"])
            terminate_session(root, envelope["run_id"], envelope["run_token"], "failed", "test cleanup")

    def test_runtime_session_cannot_expand_base_committed_authority(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = self.make_manual(Path(temporary))
            envelope = start_session(root, "semantic", "manual-assist", "manual-editor")
            session_path = root / ".wiki_state" / "sessions" / f"{envelope['run_id']}.json"
            session = json.loads(session_path.read_text(encoding="utf-8"))
            session["authority"]["writable_paths"].append("wiki/syntheses/**")
            session_path.write_text(json.dumps(session), encoding="utf-8")
            with self.assertRaisesRegex(RunError, "runtime session.*base"):
                finish_session(root, envelope["run_id"], envelope["run_token"], ["quick-lint=pass"])
            terminate_session(root, envelope["run_id"], envelope["run_token"], "failed", "test cleanup")

    def test_runtime_session_cannot_replace_the_bound_lane_contract(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = self.make_manual(Path(temporary))
            envelope = start_session(root, "semantic", "manual-assist", "manual-editor")
            session_path = root / ".wiki_state" / "sessions" / f"{envelope['run_id']}.json"
            session = json.loads(session_path.read_text(encoding="utf-8"))
            session["lane_contract"]["digest_sha256"] = "0" * 64
            session_path.write_text(json.dumps(session), encoding="utf-8")
            with self.assertRaisesRegex(RunError, "lane contract differs"):
                finish_session(root, envelope["run_id"], envelope["run_token"], ["quick-lint=pass"])
            terminate_session(root, envelope["run_id"], envelope["run_token"], "failed", "test cleanup")

    def test_terminal_session_cannot_be_finished_or_terminated_again(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = self.make_manual(Path(temporary))
            envelope = start_session(root, "semantic", "manual-assist", "manual-editor")
            code, completed = finish_session(
                root, envelope["run_id"], envelope["run_token"], ["quick-lint=pass"]
            )
            self.assertEqual(code, 0)
            with self.assertRaisesRegex(RunError, "invalid run-state transition"):
                finish_session(root, envelope["run_id"], envelope["run_token"], ["quick-lint=pass"])
            with self.assertRaisesRegex(RunError, "already terminal"):
                terminate_session(root, envelope["run_id"], envelope["run_token"], "failed", "again")
            persisted = json.loads(
                (root / ".wiki_state" / "runs" / f"{envelope['run_id']}.json").read_text(encoding="utf-8")
            )
            self.assertEqual(persisted["state"], completed["state"])
            self.assertEqual(persisted["result"], completed["result"])
            self.assertEqual(persisted["finished_at"], completed["finished_at"])


if __name__ == "__main__":
    unittest.main()
