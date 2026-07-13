from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

from wiki_test_support import make_git_wiki, run


class LinkPathSafetyTests(unittest.TestCase):
    def test_traversal_and_symlink_escape_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            parent = Path(temporary)
            root = make_git_wiki(parent)
            outside = parent / "outside.md"
            outside.write_text("outside", encoding="utf-8")
            os.symlink(outside, root / "wiki" / "outside-link.md")
            page = root / "wiki" / "overview.md"
            page.write_text(
                page.read_text(encoding="utf-8")
                + "\n[Traversal](../../outside.md)\n[Symlink](/outside-link.md)\n",
                encoding="utf-8",
            )
            completed = run([sys.executable, "tools/check_links.py"], root, check=False)
            self.assertEqual(completed.returncode, 1)
            self.assertGreaterEqual(completed.stdout.count("unsafe link escapes wiki/"), 2)
            generated = run([sys.executable, "tools/build_index.py"], root, check=False)
            self.assertEqual(generated.returncode, 0, generated.stdout + generated.stderr)
            self.assertEqual(outside.read_text(encoding="utf-8"), "outside")


if __name__ == "__main__":
    unittest.main()
