from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

from wiki_test_support import make_git_wiki, run


def lint_json(root: Path) -> dict[str, object]:
    completed = run([sys.executable, "tools/lint.py", "--full", "--json"], root)
    return next(json.loads(line) for line in completed.stdout.splitlines() if line.startswith("{"))


class LintGracePeriodTests(unittest.TestCase):
    def set_lifecycle(self, root: Path, validated_at: str, priority: str = "normal") -> None:
        path = root / "wiki" / "references" / "2026-07-13-llm-wiki-system-instructions.md"
        text = path.read_text(encoding="utf-8")
        text = text.replace("integration_state: integrated", "integration_state: unintegrated")
        text = text.replace("validated_at: 2026-07-13T00:00:00Z", f"validated_at: {validated_at}")
        text = text.replace("review_priority: normal", f"review_priority: {priority}")
        path.write_text(text, encoding="utf-8")

    def test_new_reference_in_grace_does_not_make_health_yellow(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = make_git_wiki(Path(temporary))
            self.set_lifecycle(root, "2098-01-01T00:00:00Z")
            report = lint_json(root)
            self.assertEqual(report["overall"], "green")

    def test_overdue_reference_enters_action_queues(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = make_git_wiki(Path(temporary))
            self.set_lifecycle(root, "2020-01-01T00:00:00Z")
            report = lint_json(root)
            self.assertEqual(report["overall"], "yellow")
            self.assertIn("2026-07-13-llm-wiki-system-instructions", report["queues"]["overdue"])

    def test_high_priority_escalates_inside_grace(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = make_git_wiki(Path(temporary))
            self.set_lifecycle(root, "2098-01-01T00:00:00Z", "high")
            report = lint_json(root)
            result = next(item for item in report["results"] if item["check_id"] == "reference-integration")
            self.assertEqual((result["outcome"], result["severity"]), ("warn", "high"))

    def test_ordinary_synthesis_orphan_remains_a_warning(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = make_git_wiki(Path(temporary))
            orphan = root / "wiki" / "syntheses" / "unlinked-synthesis.md"
            orphan.write_text(
                """---
type: Synthesis
title: Unlinked synthesis
description: A deliberately unlinked synthesis for lint testing.
resource: ""
tags: [test]
timestamp: 2026-07-13T00:00:00Z
created: 2026-07-13
status: active
profile: llm-wiki-profile/0.1
sources: [/references/2026-07-09-llm-wiki-system-instructions.md]
confidence: medium
---
This page deliberately has no incoming links.
""",
                encoding="utf-8",
            )
            report = lint_json(root)
            result = next(item for item in report["results"] if item["check_id"] == "ordinary-orphans")
            self.assertEqual(result["outcome"], "warn")
            self.assertIn("/syntheses/unlinked-synthesis.md", result["affected_paths"])


if __name__ == "__main__":
    unittest.main()
