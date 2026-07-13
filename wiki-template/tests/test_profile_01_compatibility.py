from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from wiki_lib import parse_frontmatter  # noqa: E402


class Profile01CompatibilityTests(unittest.TestCase):
    def test_profile_01_remains_permissively_readable(self) -> None:
        text = """---
profile: llm-wiki-profile/0.1
title: "A: quoted title"
legacy_extension: [one, "two: three"]
created: 2026-07-13
---
Body.
"""
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "page.md"
            path.write_text(text, encoding="utf-8")
            frontmatter, body, error = parse_frontmatter(path)
        self.assertIsNone(error)
        self.assertEqual(frontmatter["title"], "A: quoted title")
        self.assertEqual(frontmatter["created"], "2026-07-13")
        self.assertEqual(body, "Body.")
        self.assertEqual(text, text)  # parsing does not reserialise source pages


if __name__ == "__main__":
    unittest.main()
