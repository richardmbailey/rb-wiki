from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from wiki_lib import parse_frontmatter  # noqa: E402


PROFILE_02 = """---
type: Concept
title: Test
description: Strict profile test.
resource: ""
tags: [test]
timestamp: 2026-07-13T00:00:00Z
created: 2026-07-13
status: active
profile: llm-wiki-profile/0.2
sources: []
confidence: high
review_state: pending
review_priority: normal
consequence_tier: ordinary
---
Body.
"""


class Profile02LifecycleTests(unittest.TestCase):
    def test_valid_lifecycle_fields_are_accepted(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "page.md"
            path.write_text(PROFILE_02, encoding="utf-8")
            frontmatter, _body, error = parse_frontmatter(path)
        self.assertIsNone(error)
        self.assertEqual(frontmatter["review_state"], "pending")

    def test_unknown_or_missing_lifecycle_fields_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "page.md"
            path.write_text(PROFILE_02.replace("review_state: pending\n", "extra_state: pending\n"), encoding="utf-8")
            _frontmatter, _body, error = parse_frontmatter(path)
        self.assertIn("contract violation", error or "")


if __name__ == "__main__":
    unittest.main()
