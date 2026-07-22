from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from run_lib import RunError  # noqa: E402
from wiki_run import finish_session, start_session, terminate_session  # noqa: E402
from wiki_test_support import add_authority, make_git_wiki


class DeclaredInputTests(unittest.TestCase):
    def make_ingest(self, parent: Path) -> Path:
        root = make_git_wiki(parent)
        add_authority(
            root,
            "scheduled-ingest",
            mode="scheduled-propose",
            lane="ingest",
            action="ingest-sources",
            input_roots=["inbox"],
            writable_paths=[
                "sources/raw/**",
                "sources/derived/**",
                "sources/_source_registry.yml",
                "wiki/references/**",
                "wiki/index.md",
                ".wiki_cache/graph.json",
                "reports/ingest/**",
                "reports/runs/**",
                "reports/latest.json",
            ],
            page_types=["Reference"],
        )
        return root

    def test_direct_untracked_inbox_input_is_snapshotted_and_accepted(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = self.make_ingest(Path(temporary))
            (root / "inbox" / "new.txt").write_text("input\n", encoding="utf-8")
            envelope = start_session(root, "ingest", "scheduled-propose", "scheduled-ingest")
            terminate_session(root, envelope["run_id"], envelope["run_token"], "cancelled", "test complete")

    def test_nested_or_staged_input_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = self.make_ingest(Path(temporary))
            nested = root / "inbox" / "nested"
            nested.mkdir()
            (nested / "new.txt").write_text("input\n", encoding="utf-8")
            with self.assertRaisesRegex(RunError, "declared direct untracked"):
                start_session(root, "ingest", "scheduled-propose", "scheduled-ingest")
            self.assertFalse((root / ".wiki_state" / "mutation.lock").exists())

    def test_snapshotted_input_cannot_change_after_session_start(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = self.make_ingest(Path(temporary))
            source = root / "inbox" / "new.txt"
            source.write_text("original input\n", encoding="utf-8")
            envelope = start_session(root, "ingest", "scheduled-propose", "scheduled-ingest")
            source.write_text("changed after snapshot\n", encoding="utf-8")
            with self.assertRaisesRegex(RunError, "declared input.*changed"):
                finish_session(root, envelope["run_id"], envelope["run_token"], [])
            terminate_session(root, envelope["run_id"], envelope["run_token"], "failed", "test cleanup")


if __name__ == "__main__":
    unittest.main()
