from __future__ import annotations

import ast
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class ContractRegistryCompletenessTests(unittest.TestCase):
    def test_every_production_schema_version_literal_has_a_registered_schema(self) -> None:
        schemas = [
            json.loads(path.read_text(encoding="utf-8"))
            for path in sorted((ROOT / "schema" / "contracts").glob("*.schema.json"))
        ]
        ids = [schema["$id"] for schema in schemas]
        self.assertEqual(len(ids), len(set(ids)), "contract $id values must be unique")
        registered_versions = {
            schema.get("properties", {}).get("schema_version", {}).get("const")
            for schema in schemas
        }
        registered_versions.discard(None)

        emitted: set[str] = set()
        version_pattern = re.compile(r"^rb-wiki-[a-z-]+/0\.2$")
        for path in sorted((ROOT / "tools").glob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if not isinstance(node, ast.Dict):
                    continue
                for key, value in zip(node.keys, node.values):
                    if (
                        isinstance(key, ast.Constant)
                        and key.value == "schema_version"
                        and isinstance(value, ast.Constant)
                        and isinstance(value.value, str)
                        and version_pattern.fullmatch(value.value)
                    ):
                        emitted.add(value.value)
        emitted.add("rb-wiki-source-registry/0.2")  # emitted through REGISTRY_VERSION
        self.assertEqual(emitted - registered_versions, set())

        required_runtime = {
            "rb-wiki-agent-provenance/0.2", "rb-wiki-capabilities/0.2",
            "rb-wiki-commit-receipt/0.2", "rb-wiki-git-transaction/0.2",
            "rb-wiki-graph-cache/0.2", "rb-wiki-ingest-report/0.2",
            "rb-wiki-latest/0.2", "rb-wiki-mutation-lock/0.2",
            "rb-wiki-run-envelope/0.2", "rb-wiki-run-record/0.2",
            "rb-wiki-session/0.2", "rb-wiki-source-transition/0.2",
        }
        self.assertEqual(required_runtime - registered_versions, set())


if __name__ == "__main__":
    unittest.main()
