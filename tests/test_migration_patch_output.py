from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from release_test_support import make_v01, plan


class MigrationPatchOutputTests(unittest.TestCase):
    def test_plan_lists_exact_hashes_fields_commands_risks_and_validation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = make_v01(Path(temporary))
            _completed, migration = plan(root)
            manifest = next(item for item in migration["changes"] if item["path"] == "wiki-manifest.yml")
            self.assertIn("migration_version", manifest["fields"])
            self.assertEqual(len(manifest["after_sha256"]), 64)
            self.assertIn("git apply --check rb-wiki-v01-to-v02.patch", migration["commands"])
            self.assertTrue(migration["risks"])
            self.assertTrue(migration["required_approvals"])
            self.assertIn("python3 tools/wiki_doctor.py --json", migration["expected_validation"])
            self.assertIn("diff --git a/wiki-manifest.yml b/wiki-manifest.yml", migration["generated_patch"])


if __name__ == "__main__":
    unittest.main()
