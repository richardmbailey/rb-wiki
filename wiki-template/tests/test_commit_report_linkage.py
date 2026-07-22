from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from run_lib import RunError  # noqa: E402
from wiki_run import finish_session, record_resolution, start_session  # noqa: E402
from wiki_test_support import add_authority, make_git_wiki


class ResolutionRecordTests(unittest.TestCase):
    def test_resolution_links_without_rewriting_terminal_outcome(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = make_git_wiki(Path(temporary))
            add_authority(
                root,
                "manual-editor",
                mode="manual-assist",
                lane="semantic",
                action="edit-wiki-pages",
                writable_paths=[
                    "wiki/concepts/**",
                    "reports/runs/**",
                    "reports/latest.json",
                ],
                page_types=["Concept"],
            )
            add_authority(
                root,
                "manual-resolver",
                mode="manual-assist",
                lane="semantic",
                action="edit-wiki-pages",
                writable_paths=["reports/resolutions/**", "reports/runs/**", "reports/latest.json"],
                page_types=[],
            )
            envelope = start_session(root, "semantic", "manual-assist", "manual-editor")
            page = root / "wiki" / "concepts" / "frontmatter.md"
            page.write_text(page.read_text(encoding="utf-8") + "\nManual closure.\n", encoding="utf-8")
            _code, original = finish_session(
                root, envelope["run_id"], envelope["run_token"], []
            )
            resolution = record_resolution(
                root, original["run_id"], "manual-resolver", "reviewer", "committed after review", None
            )
            persisted = json.loads(
                (root / "reports" / "runs" / f"{original['run_id']}.json").read_text(encoding="utf-8")
            )
            self.assertEqual(persisted["state"], "manual-commit-required")
            self.assertEqual(resolution["original_state"], "manual-commit-required")

            committed = root / "schema" / "authorities" / "manual-resolver.yml"
            uncommitted = root / "schema" / "authorities" / "uncommitted-resolver.yml"
            uncommitted.write_text(
                committed.read_text(encoding="utf-8").replace(
                    "authority_id: manual-resolver", "authority_id: uncommitted-resolver"
                ),
                encoding="utf-8",
            )
            with self.assertRaises(RunError):
                record_resolution(
                    root,
                    original["run_id"],
                    "uncommitted-resolver",
                    "reviewer",
                    "must not trust working authority",
                    None,
                )


if __name__ == "__main__":
    unittest.main()
