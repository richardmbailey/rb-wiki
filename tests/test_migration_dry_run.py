from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from release_test_support import make_v01, plan, tree_hashes


class MigrationDryRunTests(unittest.TestCase):
    def test_dry_run_does_not_change_wiki(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = make_v01(Path(temporary))
            before = tree_hashes(root)
            completed, migration = plan(root)
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertEqual(migration["status"], "ready")
            self.assertEqual(before, tree_hashes(root))
            self.assertTrue(migration["generated_patch"])
            self.assertFalse(any(item["path"].startswith("sources/raw/") for item in migration["changes"]))


if __name__ == "__main__":
    unittest.main()
