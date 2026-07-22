from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from lint import build_report, check_result  # noqa: E402
from wiki_test_support import make_git_wiki, run  # noqa: E402
from fake_agent_harness import target_content  # noqa: E402


class ControllerLintReadOnlyTests(unittest.TestCase):
    def add_committed_stale_routing_input(self, root: Path) -> str:
        relative = "wiki/syntheses/controller-lint-fixture.md"
        target = root / relative
        target.write_text(target_content("Controller lint fixture"), encoding="utf-8")
        run(["git", "add", relative], root)
        run(["git", "commit", "-q", "-m", "add stale routing input"], root)
        return relative

    def test_normal_quick_lint_retains_derived_builder_behaviour(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = make_git_wiki(Path(temporary))
            relative = self.add_committed_stale_routing_input(root)
            route = "/syntheses/controller-lint-fixture.md"
            self.assertNotIn(route, (root / "wiki" / "index.md").read_text(encoding="utf-8"))

            completed = run([sys.executable, "tools/lint.py", "--quick"], root, check=False)

            self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
            self.assertIn(route, (root / "wiki" / "index.md").read_text(encoding="utf-8"))
            graph = json.loads((root / ".wiki_cache" / "graph.json").read_text(encoding="utf-8"))
            self.assertIn("/syntheses/controller-lint-fixture.md", graph["nodes"])

    def test_controller_report_excludes_mutating_builders(self) -> None:
        invoked: list[str] = []

        def fake_run_tool(script: str, *args: str) -> dict[str, object]:
            invoked.append(script)
            return check_result(script.removesuffix(".py").replace("_", "-"), script, "pass")

        with patch("lint.run_tool", side_effect=fake_run_tool):
            build_report("quick", include_mutating_builders=False)

        self.assertIn("validate_frontmatter.py", invoked)
        self.assertNotIn("build_index.py", invoked)
        self.assertNotIn("build_graph.py", invoked)

    def test_controller_owned_quick_lint_preserves_git_status_exactly(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = make_git_wiki(Path(temporary))
            relative = self.add_committed_stale_routing_input(root)
            before = run(["git", "status", "--porcelain=v1", "--untracked-files=all"], root).stdout

            completed = run(
                [sys.executable, "tools/lint.py", "--quick", "--no-report"],
                root,
                check=False,
                env_overrides={"RB_WIKI_RUN_CONTROLLER": "1"},
            )

            after = run(["git", "status", "--porcelain=v1", "--untracked-files=all"], root).stdout
            self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
            self.assertEqual(after, before)
            self.assertNotIn(
                "/syntheses/controller-lint-fixture.md",
                (root / "wiki" / "index.md").read_text(encoding="utf-8"),
            )


if __name__ == "__main__":
    unittest.main()
