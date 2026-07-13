from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

from wiki_test_support import make_git_wiki, run


class ProvenanceCitationChainTests(unittest.TestCase):
    def test_citation_to_non_reference_page_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = make_git_wiki(Path(temporary))
            page = root / "wiki" / "concepts" / "llm-wiki.md"
            text = page.read_text(encoding="utf-8").replace(
                '  - "/references/2026-07-13-llm-wiki-system-instructions.md"',
                '  - "/concepts/frontmatter.md"',
                1,
            )
            page.write_text(text, encoding="utf-8")
            completed = run([sys.executable, "tools/provenance.py", "validate"], root, check=False)
            self.assertEqual(completed.returncode, 1)
            self.assertIn("citation is not a registered Reference", completed.stdout)

    def test_parent_traversal_citation_is_rejected_without_reading_outside(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            parent = Path(temporary)
            root = make_git_wiki(parent)
            (parent / "outside.md").write_text("SECRET-CITATION-MARKER", encoding="utf-8")
            page = root / "wiki" / "concepts" / "llm-wiki.md"
            page.write_text(
                page.read_text(encoding="utf-8").replace(
                    '  - "/references/2026-07-13-llm-wiki-system-instructions.md"',
                    '  - "../../../outside.md"',
                    1,
                ),
                encoding="utf-8",
            )
            completed = run([sys.executable, "tools/provenance.py", "validate"], root, check=False)
            self.assertEqual(completed.returncode, 1)
            self.assertIn("citation escapes wiki/", completed.stdout)
            self.assertNotIn("SECRET-CITATION-MARKER", completed.stdout + completed.stderr)


if __name__ == "__main__":
    unittest.main()
