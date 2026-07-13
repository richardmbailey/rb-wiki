from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

from wiki_test_support import make_git_wiki, run


class ReverseProvenanceTests(unittest.TestCase):
    def ingest(self, root: Path) -> dict:
        (root / "inbox" / "proof.txt").write_text("proof\n", encoding="utf-8")
        completed = run(
            [sys.executable, "tools/ingest.py", "inbox/proof.txt"], root, check=False,
            env_overrides={"RB_WIKI_RUN_CONTROLLER": "1"},
        )
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        return yaml.safe_load((root / "sources" / "_source_registry.yml").read_text())["sources"][0]

    def test_unregistered_raw_and_orphan_and_duplicate_references_fail(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = make_git_wiki(Path(temporary))
            entry = self.ingest(root)
            (root / "sources" / "raw" / "unregistered.txt").write_text("extra\n", encoding="utf-8")
            reference = root / entry["reference_path"]
            (root / "wiki" / "references" / "duplicate.md").write_bytes(reference.read_bytes())
            invalid = run([sys.executable, "tools/provenance.py", "validate"], root, check=False)
            self.assertNotEqual(invalid.returncode, 0)
            self.assertIn("unregistered raw evidence", invalid.stdout)
            self.assertIn("orphan Reference", invalid.stdout)
            self.assertIn("duplicate Reference pages", invalid.stdout)

    def test_incomplete_transition_explains_extra_as_recovery_required_not_pass(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = make_git_wiki(Path(temporary))
            entry = self.ingest(root)
            journal_path = next((root / ".wiki_state" / "sources").glob("*.json"))
            journal = json.loads(journal_path.read_text(encoding="utf-8"))
            extra = root / "sources" / "raw" / "recovery-extra.txt"
            extra.write_text("proof\n", encoding="utf-8")
            journal["raw_path"] = "sources/raw/recovery-extra.txt"
            journal["outcome"] = "recovery-required"
            journal["state"] = "raw-preserved"
            journal["completed_transitions"] = ["captured", "raw-preserved"]
            journal["last_run_transitions"] = ["raw-preserved"]
            journal["next_transition"] = "registered"
            journal["failed_transition"] = "registered"
            journal["error"] = "injected"
            journal_path.write_text(json.dumps(journal), encoding="utf-8")
            invalid = run([sys.executable, "tools/provenance.py", "validate"], root, check=False)
            self.assertNotEqual(invalid.returncode, 0)
            self.assertIn("recovery-required", invalid.stdout)

    def test_symlinked_raw_directory_is_never_followed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            parent = Path(temporary)
            root = make_git_wiki(parent)
            outside = parent / "outside"
            outside.mkdir()
            (outside / "marker.txt").write_text("SECRET-MARKER", encoding="utf-8")
            raw = root / "sources" / "raw"
            shutil.rmtree(raw)
            raw.symlink_to(outside, target_is_directory=True)
            invalid = run([sys.executable, "tools/provenance.py", "validate"], root, check=False)
            self.assertNotEqual(invalid.returncode, 0)
            self.assertIn("symlink", invalid.stdout)
            self.assertNotIn("SECRET-MARKER", invalid.stdout + invalid.stderr)

    def test_individual_raw_and_nested_reference_symlinks_are_never_followed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            parent = Path(temporary)
            root = make_git_wiki(parent)
            entry = self.ingest(root)
            outside_raw = parent / "outside-raw.txt"
            outside_raw.write_text("SECRET-RAW-MARKER", encoding="utf-8")
            raw = root / entry["raw_path"]
            raw.unlink()
            raw.symlink_to(outside_raw)
            outside_references = parent / "outside-references"
            outside_references.mkdir()
            (outside_references / "secret.md").write_text("SECRET-REFERENCE-MARKER", encoding="utf-8")
            (root / "wiki" / "references" / "nested").symlink_to(
                outside_references, target_is_directory=True
            )
            invalid = run([sys.executable, "tools/provenance.py", "validate"], root, check=False)
            self.assertNotEqual(invalid.returncode, 0)
            self.assertIn("symlink", invalid.stdout)
            self.assertNotIn("SECRET-RAW-MARKER", invalid.stdout + invalid.stderr)
            self.assertNotIn("SECRET-REFERENCE-MARKER", invalid.stdout + invalid.stderr)


if __name__ == "__main__":
    unittest.main()
