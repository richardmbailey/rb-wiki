from __future__ import annotations

import tempfile
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from lint import semantic_review_for  # noqa: E402
from test_lint_grace_periods import lint_json  # noqa: E402
from wiki_test_support import make_git_wiki  # noqa: E402


class SemanticCheckOutcomeTests(unittest.TestCase):
    def test_unimplemented_semantic_checks_are_not_run(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            report = lint_json(make_git_wiki(Path(temporary)))
        semantic = [item for item in report["results"] if item["check_id"].startswith("semantic-")]
        self.assertEqual(len(semantic), 3)
        self.assertTrue(all(item["outcome"] == "not_run" for item in semantic))
        self.assertTrue(all(item["disposition"] == "agent-required" for item in semantic))
        self.assertEqual(report["overall"], "green")
        self.assertEqual(report["semantic_review"], "required")

    def test_missing_semantic_results_cannot_be_reported_as_complete(self) -> None:
        self.assertEqual(semantic_review_for("full", []), "required")


if __name__ == "__main__":
    unittest.main()
