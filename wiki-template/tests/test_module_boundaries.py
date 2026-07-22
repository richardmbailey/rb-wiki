from __future__ import annotations

import ast
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class ModuleBoundaryTests(unittest.TestCase):
    MODULES = {
        "errors", "wiki_context", "fs_safety", "contracts", "run_lib",
        "agent_provenance", "semantic_protocol", "authority", "lane_runtime", "run_store",
        "git_transaction", "authorised_apply",
    }

    def imports_for(self, name: str) -> set[str]:
        tree = ast.parse((ROOT / "tools" / f"{name}.py").read_text(encoding="utf-8"))
        return {
            alias.name.split(".", 1)[0]
            for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names
        } | {
            node.module.split(".", 1)[0]
            for node in ast.walk(tree) if isinstance(node, ast.ImportFrom) and node.module
        }

    def test_lower_layers_do_not_import_cli_orchestration(self) -> None:
        for name in self.MODULES:
            imports = self.imports_for(name)
            with self.subTest(name=name):
                self.assertNotIn("wiki_run", imports)
                self.assertNotIn("wiki_cron", imports)

    def test_declared_lower_layer_import_graph_is_acyclic(self) -> None:
        graph = {name: self.imports_for(name) & self.MODULES for name in self.MODULES}
        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(name: str, trail: tuple[str, ...]) -> None:
            if name in visiting:
                self.fail("circular lower-layer import: " + " -> ".join((*trail, name)))
            if name in visited:
                return
            visiting.add(name)
            for dependency in sorted(graph[name]):
                visit(dependency, (*trail, name))
            visiting.remove(name)
            visited.add(name)

        for name in sorted(graph):
            visit(name, ())

    def test_run_lib_does_not_delegate_back_to_owned_modules(self) -> None:
        self.assertTrue(
            self.imports_for("run_lib").isdisjoint(
                {"authority", "lane_runtime", "git_transaction", "run_store"}
            )
        )


if __name__ == "__main__":
    unittest.main()
