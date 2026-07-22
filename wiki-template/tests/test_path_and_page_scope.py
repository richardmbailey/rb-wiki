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


class PathAndPageScopeTests(unittest.TestCase):
    def test_manual_assist_preserves_unrelated_initial_dirt(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = make_git_wiki(Path(temporary))
            add_authority(
                root,
                "manual-editor",
                mode="manual-assist",
                lane="semantic",
                action="edit-wiki-pages",
                writable_paths=["wiki/concepts/**", "reports/runs/**", "reports/latest.json"],
                page_types=["Concept"],
            )
            dirty = root / "unrelated.txt"
            dirty.write_text("human work\n", encoding="utf-8")
            envelope = start_session(root, "semantic", "manual-assist", "manual-editor")
            source = root / "wiki" / "concepts" / "frontmatter.md"
            created = root / "wiki" / "concepts" / "session-created.md"
            created.write_text(source.read_text(encoding="utf-8").replace("Frontmatter", "Session Created"), encoding="utf-8")
            code, record = finish_session(root, envelope["run_id"], envelope["run_token"], [])
            self.assertEqual(code, 3)
            self.assertEqual(record["state"], "manual-commit-required")
            self.assertEqual(dirty.read_text(encoding="utf-8"), "human work\n")
            self.assertNotIn("unrelated.txt", record["changed_paths"])

    def test_page_type_violation_blocks_closure(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = make_git_wiki(Path(temporary))
            add_authority(
                root,
                "concept-only",
                mode="manual-assist",
                lane="semantic",
                action="edit-wiki-pages",
                writable_paths=["wiki/references/**", "reports/runs/**", "reports/latest.json"],
                page_types=["Concept"],
            )
            envelope = start_session(root, "semantic", "manual-assist", "concept-only")
            source = root / "wiki" / "references" / "2026-07-09-llm-wiki-system-instructions.md"
            target = root / "wiki" / "references" / "out-of-scope.md"
            target.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
            with self.assertRaisesRegex(RunError, "page-type scope"):
                finish_session(root, envelope["run_id"], envelope["run_token"], [])
            terminate_session(root, envelope["run_id"], envelope["run_token"], "failed", "test cleanup")

    def test_changed_initial_path_is_detected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = make_git_wiki(Path(temporary))
            add_authority(
                root,
                "manual-editor",
                mode="manual-assist",
                lane="semantic",
                action="edit-wiki-pages",
                writable_paths=["wiki/concepts/**", "reports/runs/**", "reports/latest.json"],
                page_types=["Concept"],
            )
            dirty = root / "wiki" / "concepts" / "frontmatter.md"
            dirty.write_text(dirty.read_text(encoding="utf-8") + "\nHuman draft.\n", encoding="utf-8")
            envelope = start_session(root, "semantic", "manual-assist", "manual-editor")
            dirty.write_text(dirty.read_text(encoding="utf-8") + "Agent overlap.\n", encoding="utf-8")
            with self.assertRaisesRegex(RunError, "protected initial"):
                finish_session(root, envelope["run_id"], envelope["run_token"], [])
            terminate_session(root, envelope["run_id"], envelope["run_token"], "failed", "test cleanup")


if __name__ == "__main__":
    unittest.main()
