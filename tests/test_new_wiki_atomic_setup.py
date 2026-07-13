from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from test_new_wiki_v02 import create


class NewWikiAtomicSetupTests(unittest.TestCase):
    def test_injected_failure_preserves_diagnostic_but_not_destination(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            parent = Path(temporary)
            completed = create(
                parent,
                check=False,
                env={"RB_WIKI_INJECT_SETUP_FAILURE": "after-configure"},
            )
            self.assertEqual(completed.returncode, 1)
            self.assertFalse((parent / "fresh-wiki").exists())
            diagnostics = list(parent.glob("fresh-wiki.rb-wiki-failed-*"))
            self.assertEqual(len(diagnostics), 1)
            self.assertTrue((diagnostics[0] / "wiki-manifest.yml").is_file())
            self.assertIn("Diagnostic staging directory preserved at", completed.stderr)
            self.assertIn("retry", completed.stderr)

    def test_success_has_no_staging_or_diagnostic_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            parent = Path(temporary)
            create(parent)
            self.assertTrue((parent / "fresh-wiki").is_dir())
            self.assertEqual(list(parent.glob("*rb-wiki-staging*")), [])
            self.assertEqual(list(parent.glob("*rb-wiki-failed*")), [])


if __name__ == "__main__":
    unittest.main()
