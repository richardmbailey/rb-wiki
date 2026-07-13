from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import run_lib  # noqa: E402
from run_lib import LockHeldError, MutationLock  # noqa: E402


class MutationLockTests(unittest.TestCase):
    def root(self, temporary: str) -> Path:
        root = Path(temporary)
        contracts = root / "schema" / "contracts"
        contracts.mkdir(parents=True)
        shutil.copyfile(
            ROOT / "schema" / "contracts" / "mutation-lock.schema.json",
            contracts / "mutation-lock.schema.json",
        )
        return root

    def test_lock_contention_and_owned_release(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = self.root(temporary)
            first = MutationLock(root, "run-one", "maintain", "scheduled-propose")
            second = MutationLock(root, "run-two", "maintain", "scheduled-propose")
            first.acquire()
            with self.assertRaises(LockHeldError) as caught:
                second.acquire()
            self.assertEqual(caught.exception.owner["run_id"], "run-one")
            first.release()
            self.assertFalse((root / ".wiki_state" / "mutation.lock").exists())

    def test_incomplete_lock_is_still_blocking(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = self.root(temporary)
            lock = MutationLock(root, "run-one", "maintain", "scheduled-propose")
            with patch.object(run_lib, "atomic_write_json", side_effect=OSError("forced metadata failure")):
                with self.assertRaises(OSError):
                    lock.acquire()
            self.assertTrue((root / ".wiki_state" / "mutation.lock").is_dir())
            with self.assertRaisesRegex(LockHeldError, "incomplete"):
                MutationLock(root, "run-two", "maintain", "scheduled-propose").acquire()


if __name__ == "__main__":
    unittest.main()
