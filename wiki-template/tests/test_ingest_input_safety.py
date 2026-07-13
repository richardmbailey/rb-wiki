from __future__ import annotations

import sys
import shutil
import tempfile
import unittest
from pathlib import Path

from wiki_test_support import make_git_wiki, run

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from ingest import load_journal  # noqa: E402
from run_lib import RunError  # noqa: E402


class IngestInputSafetyTests(unittest.TestCase):
    def ingest(self, root: Path, path: str, extra_env: dict[str, str] | None = None):
        env = {"RB_WIKI_RUN_CONTROLLER": "1", **(extra_env or {})}
        return run([sys.executable, "tools/ingest.py", path], root, check=False, env_overrides=env)

    def test_nested_symlink_traversal_and_unsafe_names_fail_before_preservation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            parent = Path(temporary)
            root = make_git_wiki(parent)
            outside = parent / "outside.txt"
            outside.write_text("outside\n", encoding="utf-8")
            nested = root / "inbox" / "nested"
            nested.mkdir()
            (nested / "source.txt").write_text("nested\n", encoding="utf-8")
            (root / "inbox" / "linked.txt").symlink_to(outside)
            inside = root / "inbox" / "inside.txt"
            inside.write_text("inside\n", encoding="utf-8")
            (root / "inbox" / "linked-inside.txt").symlink_to(inside)
            (root / "inbox" / ".unsafe.txt").write_text("unsafe\n", encoding="utf-8")
            for value in [
                "inbox/nested/source.txt",
                "inbox/linked.txt",
                "inbox/linked-inside.txt",
                str(outside),
                "inbox/.unsafe.txt",
            ]:
                with self.subTest(value=value):
                    self.assertNotEqual(self.ingest(root, value).returncode, 0)
            self.assertEqual(outside.read_text(encoding="utf-8"), "outside\n")
            self.assertEqual(len(list((root / "sources" / "raw").glob("*outside*"))), 0)

    def test_filename_with_spaces_is_ingested_without_weakening_path_validation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = make_git_wiki(Path(temporary))
            source = root / "inbox" / "source notes.txt"
            source.write_text("safe spaced filename\n", encoding="utf-8")
            completed = self.ingest(root, "inbox/source notes.txt")
            self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
            self.assertFalse(source.exists())
            self.assertEqual(
                len(list((root / "inbox" / "processed").rglob("source notes.txt"))),
                1,
            )

    def test_symlinked_output_directory_cannot_redirect_preserved_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            parent = Path(temporary)
            root = make_git_wiki(parent)
            outside = parent / "outside-raw"
            outside.mkdir()
            raw = root / "sources" / "raw"
            shutil.rmtree(raw)
            raw.symlink_to(outside, target_is_directory=True)
            (root / "inbox" / "source.txt").write_text("evidence\n", encoding="utf-8")
            completed = self.ingest(root, "inbox/source.txt")
            self.assertNotEqual(completed.returncode, 0)
            self.assertEqual(list(outside.iterdir()), [])

    def test_oversized_and_changing_input_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = make_git_wiki(Path(temporary))
            policy = root / "schema" / "agent_policy.yml"
            policy.write_text(policy.read_text().replace("max_file_bytes: 104857600", "max_file_bytes: 4"), encoding="utf-8")
            (root / "inbox" / "large.txt").write_text("too large\n", encoding="utf-8")
            self.assertNotEqual(self.ingest(root, "inbox/large.txt").returncode, 0)

        with tempfile.TemporaryDirectory() as temporary:
            root = make_git_wiki(Path(temporary))
            inbox = root / "inbox" / "changing.txt"
            inbox.write_text("original\n", encoding="utf-8")
            completed = self.ingest(
                root,
                "inbox/changing.txt",
                {
                    "RB_WIKI_FAULT_INJECTION": "1",
                    "RB_WIKI_TEST_MUTATE_INPUT_DURING_COPY": "1",
                },
            )
            self.assertNotEqual(completed.returncode, 0)
            self.assertEqual(list((root / "sources" / "raw").glob("*-changing.txt")), [])

    def test_unsupported_type_requires_explicit_preservation_only_flag(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = make_git_wiki(Path(temporary))
            path = root / "inbox" / "source.xyz"
            path.write_text("unknown format\n", encoding="utf-8")
            self.assertNotEqual(self.ingest(root, "inbox/source.xyz").returncode, 0)
            allowed = self.ingest(root, "inbox/source.xyz", {"RB_WIKI_ALLOW_PRESERVATION_ONLY": "1"})
            self.assertEqual(allowed.returncode, 0, allowed.stdout + allowed.stderr)

    def test_resume_digest_rejects_path_traversal_before_reading(self) -> None:
        with self.assertRaisesRegex(RunError, "invalid source digest"):
            load_journal("../../sessions/secret")


if __name__ == "__main__":
    unittest.main()
