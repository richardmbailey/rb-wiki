from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

from wiki_test_support import run

ROOT = Path(__file__).resolve().parents[1]


class SearchCapabilityTests(unittest.TestCase):
    def test_unavailable_backends_are_not_lexical_aliases(self) -> None:
        for mode in ("bm25", "vector", "hybrid"):
            completed = run([sys.executable, "tools/query.py", mode, "wiki"], ROOT, check=False)
            self.assertEqual(completed.returncode, 2)
            diagnostic = json.loads(completed.stdout)
            self.assertEqual(diagnostic["error"], "unavailable-capability")
            self.assertFalse(diagnostic["available"])


if __name__ == "__main__":
    unittest.main()
