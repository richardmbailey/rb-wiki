from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from run_lib import LockHeldError  # noqa: E402
from wiki_run import start_session  # noqa: E402
from wiki_test_support import add_authority, make_git_wiki, run  # noqa: E402


class ExternalSessionContentionTests(unittest.TestCase):
    def test_contention_is_terminalised_once_as_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = make_git_wiki(Path(temporary))
            add_authority(
                root,
                "manual-editor",
                mode="manual-assist",
                lane="semantic",
                action="edit-wiki-pages",
                writable_paths=[
                    "wiki/concepts/**",
                    "reports/runs/**",
                    "reports/latest.json",
                ],
                page_types=["Concept"],
            )
            lock = root / ".wiki_state" / "mutation.lock"
            lock.mkdir(parents=True)
            (lock / "owner.json").write_text(
                json.dumps({"run_id": "other", "host": "test", "pid": 1}), encoding="utf-8"
            )
            with self.assertRaises(LockHeldError):
                start_session(root, "semantic", "manual-assist", "manual-editor")
            latest = json.loads((root / ".wiki_state" / "latest.json").read_text(encoding="utf-8"))
            self.assertEqual(latest["state"], "blocked")
            self.assertEqual(latest["result"], "blocked")
            self.assertIsNotNone(latest["finished_at"])
            journal = json.loads(
                (root / ".wiki_state" / "runs" / f"{latest['run_id']}.json").read_text(encoding="utf-8")
            )
            self.assertEqual(journal, latest)

    def test_cli_contention_uses_the_transient_blocked_exit_code(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = make_git_wiki(Path(temporary))
            add_authority(
                root,
                "manual-editor",
                mode="manual-assist",
                lane="semantic",
                action="edit-wiki-pages",
                writable_paths=["wiki/concepts/**", "reports/runs/**", "reports/latest.json"],
                page_types=["Concept"],
            )
            lock = root / ".wiki_state" / "mutation.lock"
            lock.mkdir(parents=True)
            (lock / "owner.json").write_text(
                json.dumps({"run_id": "other", "host": "test", "pid": 1}), encoding="utf-8"
            )
            result = run(
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
                check=False,
            )
            self.assertEqual(result.returncode, 2)
            latest = json.loads((root / ".wiki_state" / "latest.json").read_text(encoding="utf-8"))
            self.assertEqual((latest["state"], latest["result"]), ("blocked", "blocked"))


if __name__ == "__main__":
    unittest.main()
