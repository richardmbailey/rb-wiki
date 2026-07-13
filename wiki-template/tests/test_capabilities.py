from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from capabilities import capability_snapshot  # noqa: E402


class CapabilityTests(unittest.TestCase):
    def test_capability_json_is_truthful(self) -> None:
        completed = subprocess.run(
            [sys.executable, "tools/capabilities.py", "--json"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=True,
        )
        data = json.loads(completed.stdout)
        capabilities = data["capabilities"]
        self.assertTrue(capabilities["lexical-search"]["available"])
        self.assertFalse(capabilities["bm25-search"]["available"])
        self.assertFalse(capabilities["vector-search"]["available"])
        self.assertFalse(capabilities["hybrid-search"]["available"])

    def test_corrupt_python_and_schema_make_affected_capabilities_unavailable(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "wiki"
            shutil.copytree(ROOT, root, ignore=shutil.ignore_patterns(".git", ".wiki_state", "__pycache__", "*.pyc"))
            (root / "tools" / "query.py").write_text("def broken(:\n", encoding="utf-8")
            (root / "schema" / "contracts" / "lint-report.schema.json").write_text(
                '{"type":"not-a-json-schema-type"}', encoding="utf-8"
            )
            capabilities = capability_snapshot(root)["capabilities"]
            self.assertFalse(capabilities["lexical-search"]["available"])
            self.assertFalse(capabilities["typed-lint"]["available"])


if __name__ == "__main__":
    unittest.main()
