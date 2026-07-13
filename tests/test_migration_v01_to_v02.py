from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from release_test_support import REPO, make_v01, plan, run, tree_hashes


class MigrationV01ToV02Tests(unittest.TestCase):
    def test_reviewed_patch_is_idempotent_and_preserves_raw(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = make_v01(Path(temporary))
            raw_before = {key: value for key, value in tree_hashes(root).items() if key.startswith("sources/raw/")}
            _completed, migration = plan(root)
            patch = Path(temporary) / "migration.patch"
            patch.write_text(migration["generated_patch"], encoding="utf-8")
            run(["git", "apply", "--check", str(patch)], root)
            run(["git", "apply", str(patch)], root)
            _second, after = plan(root)
            self.assertEqual(after["status"], "no-op")
            self.assertEqual(after["changes"], [])
            self.assertEqual(raw_before, {key: value for key, value in tree_hashes(root).items() if key.startswith("sources/raw/")})
            reference = (root / "wiki" / "references" / "2026-07-09-llm-wiki-system-instructions.md").read_text(encoding="utf-8")
            self.assertIn("profile: llm-wiki-profile/0.2", reference)
            self.assertIn("integration_state: integrated", reference)


if __name__ == "__main__":
    unittest.main()
