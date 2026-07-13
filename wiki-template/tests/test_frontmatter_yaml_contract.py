from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from wiki_lib import parse_frontmatter  # noqa: E402


class FrontmatterYamlContractTests(unittest.TestCase):
    def parse(self, text: str):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "page.md"
            path.write_text(text, encoding="utf-8")
            return parse_frontmatter(path)

    def test_dates_lists_and_quoted_scalars_normalise_predictably(self) -> None:
        frontmatter, _body, error = self.parse(
            '---\nprofile: llm-wiki-profile/0.1\ncreated: 2026-07-13\ntags: ["a:b", two]\n---\n'
        )
        self.assertIsNone(error)
        self.assertEqual(frontmatter, {"profile": "llm-wiki-profile/0.1", "created": "2026-07-13", "tags": ["a:b", "two"]})

    def test_unsafe_tag_and_malformed_yaml_are_rejected(self) -> None:
        for payload in ("value: !!python/object/apply:os.system ['id']", "value: [unterminated"):
            _frontmatter, _body, error = self.parse(f"---\nprofile: llm-wiki-profile/0.1\n{payload}\n---\n")
            self.assertIn("unsafe or invalid YAML", error or "")


if __name__ == "__main__":
    unittest.main()
