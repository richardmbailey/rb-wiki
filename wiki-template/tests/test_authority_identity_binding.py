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

from errors import ContractError  # noqa: E402
from authority import load_base_policy  # noqa: E402
from wiki_run import (  # noqa: E402
    break_lock,
    execute_run,
    finish_session,
    record_resolution,
    start_session,
    terminate_session,
)
from wiki_test_support import add_authority, make_git_wiki, run  # noqa: E402


class AuthorityIdentityBindingTests(unittest.TestCase):
    def make_alias(self, parent: Path, *, governance: bool = False) -> tuple[Path, Path]:
        root = make_git_wiki(parent)
        add_authority(
            root,
            "alias",
            mode="manual-assist",
            lane="governance" if governance else "semantic",
            action="governance-maintenance" if governance else "edit-wiki-pages",
            writable_paths=(
                ["reports/runs/**", "reports/latest.json", "reports/resolutions/**"]
                if governance
                else ["wiki/concepts/**", "reports/runs/**", "reports/latest.json"]
            ),
            page_types=[] if governance else ["Concept"],
            governance=governance,
        )
        grant = root / "schema" / "authorities" / "alias.yml"
        grant.write_text(
            grant.read_text(encoding="utf-8").replace("authority_id: alias", "authority_id: committed-other"),
            encoding="utf-8",
        )
        run(["git", "add", grant.relative_to(root).as_posix()], root)
        run(["git", "commit", "-q", "-m", "commit mismatched authority identity"], root)
        return root, grant

    def test_base_policy_loader_binds_requested_authority_identity(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root, _grant = self.make_alias(Path(temporary))
            base = run(["git", "rev-parse", "HEAD"], root).stdout.strip()
            with self.assertRaisesRegex(ContractError, "filename and authority_id"):
                load_base_policy(base, "alias", root)

    def test_manual_session_cannot_label_a_different_committed_grant_as_requested(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root, grant = self.make_alias(Path(temporary))
            grant.write_text(
                grant.read_text(encoding="utf-8").replace("authority_id: committed-other", "authority_id: alias"),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ContractError, "filename and authority_id"):
                start_session(root, "semantic", "manual-assist", "alias")
            self.assertFalse((root / ".wiki_state" / "mutation.lock").exists())

    def test_break_lock_and_resolution_use_the_same_identity_boundary(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root, _grant = self.make_alias(Path(temporary), governance=True)
            lock = root / ".wiki_state" / "mutation.lock"
            lock.mkdir(parents=True)
            (lock / "owner.json").write_text(
                json.dumps({"run_id": "dead", "host": socket.gethostname(), "pid": 99999999}),
                encoding="utf-8",
            )
            with patch("wiki_run.process_alive", return_value=False):
                with self.assertRaisesRegex(ContractError, "filename and authority_id"):
                    break_lock(root, "alias", "tester", "identity test")

            fake_run = "20260101T000000Z-aaaaaaaaaaaa"
            with self.assertRaisesRegex(ContractError, "filename and authority_id"):
                record_resolution(root, fake_run, "alias", "tester", "identity test", None)

    def test_managed_and_cron_runs_reject_authority_alias_before_record_creation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = make_git_wiki(Path(temporary))
            add_authority(
                root,
                "alias",
                mode="scheduled-propose",
                lane="maintain",
                action="deterministic-maintenance",
                writable_paths=[
                    "wiki/index.md",
                    ".wiki_cache/graph.json",
                    "reports/runs/**",
                    "reports/latest.json",
                ],
            )
            grant = root / "schema" / "authorities" / "alias.yml"
            grant.write_text(
                grant.read_text(encoding="utf-8").replace(
                    "authority_id: alias", "authority_id: committed-other"
                ),
                encoding="utf-8",
            )
            run(["git", "add", grant.relative_to(root).as_posix()], root)
            run(["git", "commit", "-q", "-m", "commit managed alias"], root)
            with self.assertRaisesRegex(ContractError, "filename and authority_id"):
                execute_run(root, "maintain", "scheduled-propose", "alias")
            with patch("wiki_cron.ROOT", root):
                from wiki_cron import maintenance

                with self.assertRaisesRegex(ContractError, "filename and authority_id"):
                    maintenance("alias")
            self.assertFalse((root / ".wiki_state" / "latest.json").exists())

    def test_finish_reloads_the_requested_base_authority_identity(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root, _grant = self.make_alias(Path(temporary))
            add_authority(
                root,
                "manual-editor",
                mode="manual-assist",
                lane="semantic",
                action="edit-wiki-pages",
                writable_paths=["wiki/concepts/**", "reports/runs/**", "reports/latest.json"],
                page_types=["Concept"],
            )
            envelope = start_session(root, "semantic", "manual-assist", "manual-editor")
            session_path = root / ".wiki_state" / "sessions" / f"{envelope['run_id']}.json"
            session = json.loads(session_path.read_text(encoding="utf-8"))
            session["record"]["authority_id"] = "alias"
            session_path.write_text(json.dumps(session), encoding="utf-8")
            journal_path = root / ".wiki_state" / "runs" / f"{envelope['run_id']}.json"
            journal = json.loads(journal_path.read_text(encoding="utf-8"))
            journal["authority_id"] = "alias"
            journal_path.write_text(json.dumps(journal), encoding="utf-8")
            with self.assertRaisesRegex(ContractError, "filename and authority_id"):
                finish_session(root, envelope["run_id"], envelope["run_token"], [])
            terminate_session(root, envelope["run_id"], envelope["run_token"], "failed", "test cleanup")


if __name__ == "__main__":
    unittest.main()
