from __future__ import annotations

import shutil
import sys
import tempfile
import unittest
from pathlib import Path

from release_test_support import MIGRATE, REPO, TEMPLATE, make_v01, run


class MigrationParentSymlinkSafetyTests(unittest.TestCase):
    def migrate(self, root: Path, template: Path):
        return run(
            [sys.executable, str(MIGRATE), "--dry-run", "--root", str(root), "--template", str(template)],
            REPO,
            check=False,
        )

    def test_symlinked_target_tools_parent_is_rejected_without_external_content(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            parent = Path(temporary)
            root = make_v01(parent)
            outside = parent / "outside-tools"
            outside.mkdir()
            (outside / "marker.py").write_text("SECRET-EXTERNAL-MARKER", encoding="utf-8")
            tools = root / "tools"
            shutil.rmtree(tools)
            tools.symlink_to(outside, target_is_directory=True)
            completed = self.migrate(root, TEMPLATE)
            self.assertEqual(completed.returncode, 1)
            self.assertIn("symlink", completed.stderr)
            self.assertNotIn("SECRET-EXTERNAL-MARKER", completed.stdout + completed.stderr)

    def test_symlinked_template_operational_parents_are_rejected(self) -> None:
        for relative in ["tools", "schema/contracts", "schema/lanes", "schema/prompts", "docs", "reports"]:
            with self.subTest(relative=relative), tempfile.TemporaryDirectory() as temporary:
                parent = Path(temporary)
                root = make_v01(parent)
                template = parent / "template"
                shutil.copytree(TEMPLATE, template, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
                outside = parent / "outside"
                outside.mkdir()
                (outside / "marker.txt").write_text("SECRET-EXTERNAL-MARKER", encoding="utf-8")
                target = template / relative
                if target.is_dir():
                    shutil.rmtree(target)
                else:
                    target.unlink()
                target.symlink_to(outside, target_is_directory=True)
                completed = self.migrate(root, template)
                self.assertEqual(completed.returncode, 1)
                self.assertIn("symlink", completed.stderr)
                self.assertNotIn("SECRET-EXTERNAL-MARKER", completed.stdout + completed.stderr)

    def test_symlinked_target_operational_parents_are_rejected(self) -> None:
        for relative in ["tools", "schema", "reports", "sources", "wiki/references"]:
            with self.subTest(relative=relative), tempfile.TemporaryDirectory() as temporary:
                parent = Path(temporary)
                root = make_v01(parent)
                outside = parent / "outside"
                outside.mkdir()
                (outside / "marker.txt").write_text("SECRET-EXTERNAL-MARKER", encoding="utf-8")
                target = root / relative
                if target.is_dir():
                    shutil.rmtree(target)
                elif target.exists() or target.is_symlink():
                    target.unlink()
                target.symlink_to(outside, target_is_directory=True)
                completed = self.migrate(root, TEMPLATE)
                self.assertEqual(completed.returncode, 1)
                self.assertNotIn("SECRET-EXTERNAL-MARKER", completed.stdout + completed.stderr)

    def test_symlinked_template_or_target_root_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            parent = Path(temporary)
            real_root = make_v01(parent)
            linked_root = parent / "linked-wiki"
            linked_root.symlink_to(real_root, target_is_directory=True)
            completed = self.migrate(linked_root, TEMPLATE)
            self.assertEqual(completed.returncode, 1)
            self.assertIn("real directory", completed.stderr)

    def test_broken_and_chained_root_links_are_rejected(self) -> None:
        for kind in ["broken", "relative-chain", "absolute-chain"]:
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as temporary:
                parent = Path(temporary)
                root = make_v01(parent)
                linked = parent / "linked-wiki"
                if kind == "broken":
                    linked.symlink_to(parent / "missing", target_is_directory=True)
                else:
                    intermediate = parent / "intermediate"
                    intermediate.symlink_to(
                        root.name if kind == "relative-chain" else root,
                        target_is_directory=True,
                    )
                    linked.symlink_to(intermediate, target_is_directory=True)
                completed = self.migrate(linked, TEMPLATE)
                self.assertEqual(completed.returncode, 1)
                self.assertIn("real directory", completed.stderr)


if __name__ == "__main__":
    unittest.main()
