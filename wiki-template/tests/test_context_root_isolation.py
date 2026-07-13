from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from contracts import validate_contract  # noqa: E402
from errors import ContractError  # noqa: E402
from fs_safety import safe_path  # noqa: E402
from wiki_context import WikiContext  # noqa: E402


class ContextRootIsolationTests(unittest.TestCase):
    def make_contract_root(self, parent: Path, name: str) -> Path:
        root = parent / name
        shutil.copytree(ROOT / "schema" / "contracts", root / "schema" / "contracts")
        (root / "reports").mkdir()
        return root

    def test_contract_and_filesystem_operations_use_the_supplied_root(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            parent = Path(temporary)
            first = self.make_contract_root(parent, "first")
            second = self.make_contract_root(parent, "second")
            data = {
                "schema_version": "rb-wiki-agent-provenance/0.2",
                "agent_label": None,
                "runtime": None,
                "provider_model": None,
                "prompt_policy_digest": None,
                "trace_reference": None,
                "started_at": None,
                "finished_at": None,
                "tool_call_summary": {},
            }
            validate_contract(data, "agent-provenance", first)

            schema_path = second / "schema" / "contracts" / "agent-provenance.schema.json"
            schema = json.loads(schema_path.read_text(encoding="utf-8"))
            schema["properties"]["schema_version"]["const"] = "deliberately-incompatible"
            schema_path.write_text(json.dumps(schema), encoding="utf-8")
            with self.assertRaises(ContractError):
                validate_contract(data, "agent-provenance", second)
            validate_contract(data, "agent-provenance", first)

            artifact = first / "reports" / "evidence.json"
            artifact.write_text("{}\n", encoding="utf-8")
            self.assertEqual(safe_path(first, "reports/evidence.json"), artifact)
            with self.assertRaises(ContractError):
                safe_path(second, "reports/evidence.json")

    def test_context_derives_paths_only_from_its_own_root(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "wiki"
            root.mkdir()
            context = WikiContext(root)
            self.assertEqual(context.root, root.absolute())
            self.assertEqual(context.contracts_dir, root.absolute() / "schema" / "contracts")
            self.assertEqual(context.state_dir, root.absolute() / ".wiki_state")


if __name__ == "__main__":
    unittest.main()
