from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from run_lib import ContractError  # noqa: E402
from source_registry import load_registry_document  # noqa: E402
from wiki_test_support import make_git_wiki, run  # noqa: E402


class RegistryContractTests(unittest.TestCase):
    def test_legacy_v01_list_is_normalized_without_identity_change(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "registry.yml"
            path.write_text(
                '''- source_id: "legacy-source"
  raw_path: "sources/raw/legacy-source.txt"
  reference_path: "wiki/references/legacy-source.md"
  hash_sha256: "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
  source_type: "note"
  date_ingested: "2026-01-01"
  date_published: "unknown"
  status: "active"
''',
                encoding="utf-8",
            )
            document = load_registry_document(path)
            self.assertEqual(document["schema_version"], "rb-wiki-source-registry/0.2")
            self.assertEqual(document["sources"][0]["source_id"], "legacy-source")
            self.assertEqual(document["sources"][0]["ingest_state"], "validated")

    def test_unknown_registry_fields_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "registry.yml"
            text = (ROOT / "sources" / "_source_registry.yml").read_text(encoding="utf-8")
            path.write_text(text.replace("    derivative_path: null", "    derivative_path: null\n    surprise: true"), encoding="utf-8")
            with self.assertRaises(ContractError):
                load_registry_document(path)

    def test_legacy_incomplete_entry_is_reported_not_silently_duplicated(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = make_git_wiki(Path(temporary))
            (root / "sources" / "_source_registry.yml").write_text(
                '''- source_id: legacy-missing
  raw_path: sources/raw/legacy-missing.txt
  reference_path: wiki/references/legacy-missing.md
  hash_sha256: aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
  source_type: note
  date_ingested: "2026-01-01"
  date_published: unknown
  status: active
''',
                encoding="utf-8",
            )
            completed = run([sys.executable, "tools/source_registry.py", "validate"], root, check=False)
            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("raw path is missing", completed.stdout)


if __name__ == "__main__":
    unittest.main()
