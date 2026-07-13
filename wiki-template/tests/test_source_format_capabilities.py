from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from capabilities import capability_snapshot  # noqa: E402
from ingest import SUPPORTED_SUFFIXES  # noqa: E402
from source_registry import SOURCE_FORMAT_CAPABILITIES  # noqa: E402


class SourceFormatCapabilityTests(unittest.TestCase):
    def test_format_declarations_reconcile(self) -> None:
        declared_ingest = {suffix for suffix, state in SOURCE_FORMAT_CAPABILITIES.items() if state == "ingest"}
        self.assertEqual(SUPPORTED_SUFFIXES, declared_ingest)
        capabilities = capability_snapshot()["capabilities"]
        self.assertTrue(capabilities["pdf-ingest"]["available"])
        self.assertFalse(capabilities["html-ingest"]["available"])
        self.assertEqual(SOURCE_FORMAT_CAPABILITIES[".html"], "preservation-only")


if __name__ == "__main__":
    unittest.main()
