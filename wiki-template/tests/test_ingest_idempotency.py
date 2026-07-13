from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

import yaml

from wiki_test_support import make_git_wiki, run


class IngestIdempotencyTests(unittest.TestCase):
    def ingest(self, root: Path, path: str):
        return run(
            [sys.executable, "tools/ingest.py", path],
            root,
            check=False,
            env_overrides={"RB_WIKI_RUN_CONTROLLER": "1"},
        )

    def test_identical_content_reuses_one_identity_and_archives_each_capture_once(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = make_git_wiki(Path(temporary))
            initial_registry = yaml.safe_load(
                (root / "sources" / "_source_registry.yml").read_text(encoding="utf-8")
            )
            initial_ids = {entry["source_id"] for entry in initial_registry["sources"]}
            inbox = root / "inbox" / "same.txt"
            inbox.write_text("same evidence\n", encoding="utf-8")
            self.assertEqual(self.ingest(root, "inbox/same.txt").returncode, 0)
            inbox.write_text("same evidence\n", encoding="utf-8")
            self.assertEqual(self.ingest(root, "inbox/same.txt").returncode, 0)
            registry = yaml.safe_load((root / "sources" / "_source_registry.yml").read_text())
            matching = [entry for entry in registry["sources"] if entry["source_id"] not in initial_ids]
            self.assertEqual(len(matching), 1)
            source_id = matching[0]["source_id"]
            self.assertEqual(len(list((root / "sources" / "raw").glob(f"{source_id}.*"))), 1)
            self.assertEqual(len(list((root / "wiki" / "references").glob(f"{source_id}.md"))), 1)
            archived = list((root / "inbox" / "processed").rglob("same*.txt"))
            self.assertEqual(len(archived), 2)

    def test_direct_cli_without_controller_is_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = make_git_wiki(Path(temporary))
            (root / "inbox" / "blocked.txt").write_text("blocked\n", encoding="utf-8")
            completed = run([sys.executable, "tools/ingest.py", "inbox/blocked.txt"], root, check=False)
            self.assertEqual(completed.returncode, 2)
            self.assertEqual(list((root / "sources" / "raw").glob("*-blocked.txt")), [])


if __name__ == "__main__":
    unittest.main()
