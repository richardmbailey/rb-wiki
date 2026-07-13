from __future__ import annotations

import unittest

from test_lint_grace_periods import lint_json
from wiki_test_support import make_git_wiki
import tempfile
from pathlib import Path


class SemanticCheckOutcomeTests(unittest.TestCase):
    def test_unimplemented_semantic_checks_are_not_run(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            report = lint_json(make_git_wiki(Path(temporary)))
        semantic = [item for item in report["results"] if item["check_id"].startswith("semantic-")]
        self.assertEqual(len(semantic), 3)
        self.assertTrue(all(item["outcome"] == "not_run" for item in semantic))
        self.assertTrue(all(item["disposition"] == "agent-required" for item in semantic))


if __name__ == "__main__":
    unittest.main()
