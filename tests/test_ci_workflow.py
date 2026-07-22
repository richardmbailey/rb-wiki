from __future__ import annotations

import unittest

from release_test_support import REPO


class CIWorkflowTests(unittest.TestCase):
    def test_ci_runs_both_test_suites_and_release_gates(self) -> None:
        workflow = REPO / ".github" / "workflows" / "ci.yml"
        self.assertTrue(workflow.is_file(), "the repository must run its verification in CI")
        text = workflow.read_text(encoding="utf-8")
        for command in (
            "python -m unittest discover -s tests -v",
            "python scripts/sync_distributed.py --check",
            "python tools/provenance.py validate",
            "python tools/lint.py --quick --no-report",
            "python tools/lint.py --full --no-report",
        ):
            self.assertIn(command, text)
        self.assertGreaterEqual(text.count("python -m unittest discover -s tests -v"), 2)


if __name__ == "__main__":
    unittest.main()
