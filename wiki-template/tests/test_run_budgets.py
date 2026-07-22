from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from run_lib import RunError, atomic_write_json  # noqa: E402
from wiki_run import finish_session, load_session, save_session, start_session, terminate_session  # noqa: E402
from wiki_test_support import add_authority, make_git_wiki, run


class RunBudgetTests(unittest.TestCase):
    def make_manual(self, parent: Path) -> Path:
        root = make_git_wiki(parent)
        add_authority(
            root,
            "budget-editor",
            mode="manual-assist",
            lane="semantic",
            action="edit-wiki-pages",
            writable_paths=["wiki/concepts/**", "reports/runs/**", "reports/latest.json"],
            page_types=["Concept"],
        )
        return root

    def test_failed_validation_prevents_closure(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = self.make_manual(Path(temporary))
            envelope = start_session(root, "semantic", "manual-assist", "budget-editor")
            with patch("wiki_run.run_controller_lint", return_value=(1, "forced lint failure")):
                with self.assertRaisesRegex(RunError, "quick-lint validation failed"):
                    finish_session(root, envelope["run_id"], envelope["run_token"], [])
            terminate_session(root, envelope["run_id"], envelope["run_token"], "failed", "test cleanup")

    def test_runtime_budget_is_enforced_from_persisted_start(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = self.make_manual(Path(temporary))
            envelope = start_session(root, "semantic", "manual-assist", "budget-editor")
            session = load_session(envelope["run_id"], root)
            session["record"]["started_at"] = "2020-01-01T00:00:00Z"
            save_session(session, root)
            atomic_write_json(
                root / ".wiki_state" / "runs" / f"{envelope['run_id']}.json",
                session["record"],
                root,
            )
            with self.assertRaisesRegex(RunError, "runtime budget"):
                finish_session(root, envelope["run_id"], envelope["run_token"], [])
            terminate_session(root, envelope["run_id"], envelope["run_token"], "failed", "test cleanup")

    def test_changed_path_budget_prevents_closure(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = self.make_manual(Path(temporary))
            authority_path = root / "schema" / "authorities" / "budget-editor.yml"
            authority_path.write_text(
                authority_path.read_text(encoding="utf-8").replace("max_changed_paths: 25", "max_changed_paths: 0"),
                encoding="utf-8",
            )
            run(["git", "add", authority_path.relative_to(root).as_posix()], root)
            run(["git", "commit", "-q", "-m", "tighten path budget"], root)
            envelope = start_session(root, "semantic", "manual-assist", "budget-editor")
            page = root / "wiki" / "concepts" / "frontmatter.md"
            page.write_text(page.read_text(encoding="utf-8") + "\nChange.\n", encoding="utf-8")
            with self.assertRaisesRegex(RunError, "changed-path budget"):
                finish_session(root, envelope["run_id"], envelope["run_token"], [])
            terminate_session(root, envelope["run_id"], envelope["run_token"], "failed", "test cleanup")


if __name__ == "__main__":
    unittest.main()
