from __future__ import annotations

import tempfile
import sys
import unittest
from pathlib import Path

from release_test_support import MIGRATE, REPO, TEMPLATE, make_v01, run


def unsafe_plan(root: Path):
    return run(
        [sys.executable, str(MIGRATE), "--dry-run", "--root", str(root), "--template", str(TEMPLATE)],
        REPO,
        check=False,
    )


class MigrationPathSafetyTests(unittest.TestCase):
    def test_unsafe_legacy_reference_path_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = make_v01(Path(temporary))
            registry = root / "sources" / "_source_registry.yml"
            registry.write_text(
                registry.read_text(encoding="utf-8").replace(
                    "wiki/references/2026-07-09-llm-wiki-system-instructions.md",
                    "../../outside.md",
                ),
                encoding="utf-8",
            )
            completed = unsafe_plan(root)
            self.assertEqual(completed.returncode, 1)
            self.assertIn("unsafe legacy reference path", completed.stderr)

    def test_symlinked_manifest_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            parent = Path(temporary)
            root = make_v01(parent)
            manifest = root / "wiki-manifest.yml"
            outside = parent / "outside-manifest.yml"
            outside.write_text(manifest.read_text(encoding="utf-8"), encoding="utf-8")
            manifest.unlink()
            manifest.symlink_to(outside)
            completed = unsafe_plan(root)
            self.assertEqual(completed.returncode, 1)
            self.assertIn("must not be a symlink", completed.stderr)

    def test_symlinked_canonical_target_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            parent = Path(temporary)
            root = make_v01(parent)
            ignore = root / ".gitignore"
            outside = parent / "outside-ignore"
            outside.write_text(ignore.read_text(encoding="utf-8"), encoding="utf-8")
            ignore.unlink()
            ignore.symlink_to(outside)
            completed = unsafe_plan(root)
            self.assertEqual(completed.returncode, 1)
            self.assertIn("legacy .gitignore must not be a symlink", completed.stderr)


if __name__ == "__main__":
    unittest.main()
