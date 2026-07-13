from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from run_lib import RunError  # noqa: E402
from wiki_run import finish_session, start_session  # noqa: E402
from wiki_test_support import add_authority, make_git_wiki
from fake_agent_harness import target_content


class ScheduledProposeEnforcementTests(unittest.TestCase):
    def test_substantive_page_edit_cannot_close(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = make_git_wiki(Path(temporary))
            add_authority(
                root,
                "overbroad-proposer",
                mode="scheduled-propose",
                lane="synthesize",
                action="propose-synthesis",
                writable_paths=[
                    "reports/proposals/**", "reports/semantic/**",
                    "reports/runs/**", "reports/latest.json",
                ],
                page_types=[],
            )
            envelope = start_session(root, "synthesize", "scheduled-propose", "overbroad-proposer")
            path = root / "wiki" / "syntheses" / "forbidden.md"
            path.write_text(target_content(), encoding="utf-8")
            with self.assertRaisesRegex(RunError, "forbids substantive wiki edits"):
                finish_session(root, envelope["run_id"], envelope["run_token"], ["quick-lint=pass"])


if __name__ == "__main__":
    unittest.main()
