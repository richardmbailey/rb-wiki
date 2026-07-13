from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from lint import check_result  # noqa: E402
from run_lib import ContractError  # noqa: E402


class LintResultContractTests(unittest.TestCase):
    def test_typed_result_validates(self) -> None:
        result = check_result("test-check", "Test check", "warn", "medium", "agent-required")
        self.assertEqual(result["outcome"], "warn")

    def test_invalid_outcome_is_rejected(self) -> None:
        with self.assertRaises(ContractError):
            check_result("test-check", "Test check", "unknown")


if __name__ == "__main__":
    unittest.main()
