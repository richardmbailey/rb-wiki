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


class RawAppendOnlyTests(unittest.TestCase):
    def test_preexisting_raw_modification_deletion_and_rename_block_closure(self) -> None:
        for action in ("modify", "delete", "rename"):
            with self.subTest(action=action), tempfile.TemporaryDirectory() as temporary:
                root = make_git_wiki(Path(temporary))
                add_authority(
                    root,
                    "manual-ingest",
                    mode="manual-assist",
                    lane="ingest",
                    action="ingest-sources",
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
                envelope = start_session(root, "ingest", "manual-assist", "manual-ingest")
                raw = next((root / "sources" / "raw").glob("*.md"))
                if action == "modify":
                    raw.write_text(raw.read_text(encoding="utf-8") + "tamper\n", encoding="utf-8")
                elif action == "delete":
                    raw.unlink()
                else:
                    raw.rename(raw.with_name("renamed.md"))
                with self.assertRaisesRegex(RunError, "not append-only"):
                    finish_session(root, envelope["run_id"], envelope["run_token"], ["quick-lint=pass"])
                terminate_session(root, envelope["run_id"], envelope["run_token"], "failed", "test cleanup")


if __name__ == "__main__":
    unittest.main()
