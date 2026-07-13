from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

import yaml

from wiki_test_support import make_git_wiki, run


class ProvenanceTests(unittest.TestCase):
    def ingest(self, root: Path) -> dict:
        (root / "inbox" / "proof.txt").write_text("proof\n", encoding="utf-8")
        completed = run(
            [sys.executable, "tools/ingest.py", "inbox/proof.txt"],
            root,
            check=False,
            env_overrides={"RB_WIKI_RUN_CONTROLLER": "1"},
        )
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        registry = yaml.safe_load((root / "sources" / "_source_registry.yml").read_text())
        return next(entry for entry in registry["sources"] if entry["source_id"].endswith("proof"))

    def test_valid_provenance_and_each_reconciled_field(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = make_git_wiki(Path(temporary))
            entry = self.ingest(root)
            valid = run([sys.executable, "tools/provenance.py", "validate", "--source-id", entry["source_id"]], root, check=False)
            self.assertEqual(valid.returncode, 0, valid.stdout + valid.stderr)
            self.assertIn("reverse global checks skipped", valid.stdout)
            reference = root / entry["reference_path"]
            original = reference.read_text(encoding="utf-8")
            for field, old, new in [
                ("source_id", entry["source_id"], "wrong-source"),
                ("raw path", entry["raw_path"], "sources/raw/wrong.txt"),
                ("hash", entry["hash_sha256"], "b" * 64),
                ("source type", "source_type: note", "source_type: pdf"),
            ]:
                with self.subTest(field=field):
                    reference.write_text(original.replace(old, new, 1), encoding="utf-8")
                    invalid = run([sys.executable, "tools/provenance.py", "validate", "--source-id", entry["source_id"]], root, check=False)
                    self.assertNotEqual(invalid.returncode, 0)
                    reference.write_text(original, encoding="utf-8")

    def test_raw_hash_mismatch_is_detected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = make_git_wiki(Path(temporary))
            entry = self.ingest(root)
            (root / entry["raw_path"]).write_text("tampered\n", encoding="utf-8")
            invalid = run([sys.executable, "tools/provenance.py", "validate"], root, check=False)
            self.assertNotEqual(invalid.returncode, 0)
            self.assertIn("hash mismatch", invalid.stdout)


if __name__ == "__main__":
    unittest.main()
