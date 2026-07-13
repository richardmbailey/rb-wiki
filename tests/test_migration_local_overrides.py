from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from release_test_support import make_v01, plan


class MigrationLocalOverrideTests(unittest.TestCase):
    def test_declared_override_is_preserved_and_policy_divergence_is_manual(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = make_v01(Path(temporary), local_override=True)
            before = (root / "tools" / "query.py").read_text(encoding="utf-8")
            _completed, migration = plan(root)
            self.assertIn("tools/query.py", migration["preserved_overrides"])
            self.assertFalse(any(item["path"] == "tools/query.py" for item in migration["changes"]))
            self.assertEqual(before, (root / "tools" / "query.py").read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as temporary:
            root = make_v01(Path(temporary), policy_diverged=True)
            completed, migration = plan(root)
            self.assertEqual(completed.returncode, 2)
            self.assertEqual(migration["status"], "manual-review")
            self.assertTrue(any("semantic policy" in item for item in migration["manual_review"]))

    def test_dirty_and_incomplete_ingest_fixtures_require_manual_review(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = make_v01(Path(temporary))
            (root / "README.md").write_text(
                (root / "README.md").read_text(encoding="utf-8") + "\ndirty\n", encoding="utf-8"
            )
            completed, migration = plan(root)
            self.assertEqual(completed.returncode, 2)
            self.assertTrue(any("Dirty worktree" in item for item in migration["manual_review"]))
        with tempfile.TemporaryDirectory() as temporary:
            root = make_v01(Path(temporary), incomplete_ingest=True)
            completed, migration = plan(root)
            self.assertEqual(completed.returncode, 2)
            self.assertTrue(any("Incomplete ingest" in item for item in migration["manual_review"]))


if __name__ == "__main__":
    unittest.main()
