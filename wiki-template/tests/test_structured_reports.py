from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from capabilities import capability_snapshot  # noqa: E402
from lint import check_result, render_report_markdown  # noqa: E402
from run_lib import validate_contract  # noqa: E402


class StructuredReportTests(unittest.TestCase):
    def test_lint_report_validates_and_renders_deterministically(self) -> None:
        report = {
            "schema_version": "rb-wiki-lint-report/0.2",
            "report_id": "2026-07-13T120000Z-lint",
            "created_at": "2026-07-13T12:00:00Z",
            "mode": "quick",
            "overall": "green",
            "results": [check_result("test-check", "Test check", "pass")],
            "queues": {"blockers": [], "overdue": [], "agent_required": []},
            "capabilities": capability_snapshot(),
        }
        validate_contract(report, "lint-report", ROOT)
        first = render_report_markdown(report)
        self.assertEqual(first, render_report_markdown(report))
        self.assertIn("`pass`", first)


if __name__ == "__main__":
    unittest.main()
