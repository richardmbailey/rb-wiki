from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from lane_runtime import validate_lane_contracts  # noqa: E402
from wiki_run import finish_session, start_session  # noqa: E402
from wiki_test_support import add_authority, make_git_wiki, run
from fake_agent_harness import write_json


class LaneHandoffTests(unittest.TestCase):
    def test_lane_dependencies_are_declared_artifacts(self) -> None:
        lanes = {item["lane_id"]: item for item in validate_lane_contracts(ROOT)}
        self.assertIn("acquisition-result", set(lanes["acquire"]["produces"]) & set(lanes["ingest"]["consumes"]))
        self.assertIn("source-registry", set(lanes["ingest"]["produces"]) & set(lanes["synthesize"]["consumes"]))
        self.assertIn("synthesis-proposal", set(lanes["synthesize"]["produces"]) & set(lanes["semantic-maintain"]["consumes"]))

    def test_acquire_closure_requires_a_valid_result_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = make_git_wiki(Path(temporary))
            add_authority(
                root,
                "acquirer",
                mode="scheduled-propose",
                lane="acquire",
                action="acquire-sources",
                writable_paths=["reports/acquisitions/**", "reports/runs/**", "reports/latest.json"],
            )
            envelope = start_session(root, "acquire", "scheduled-propose", "acquirer")
            acquisition = {
                "schema_version": "rb-wiki-acquisition-result/0.2",
                "acquisition_id": "test-acquisition",
                "run_id": envelope["run_id"],
                "created_at": "2026-07-13T12:00:00Z",
                "agent": {"agent_label": "fake", "runtime_label": "harness"},
                "query": "bounded source discovery",
                "provider": {"name": "fixture", "method": "static"},
                "discovery_budget": {"max_candidates": 2, "max_selected": 1},
                "candidates": [{"candidate_id": "one", "locator": "fixture:one", "metadata": {}}],
                "selected": ["one"],
                "selection_rationale": ["Declared fixture."],
                "preservation_state": "inbox-staged",
                "next_artifact": "source-transition",
            }
            write_json(root / "reports" / "acquisitions" / "test-acquisition.json", acquisition)
            code, record = finish_session(root, envelope["run_id"], envelope["run_token"], [])
            self.assertEqual(code, 3)
            self.assertEqual(record["state"], "manual-commit-required")

    def test_ingest_refuses_inbox_that_does_not_match_committed_acquisition(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = make_git_wiki(Path(temporary))
            add_authority(
                root,
                "handoff-ingest",
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
            acquisition = {
                "schema_version": "rb-wiki-acquisition-result/0.2",
                "acquisition_id": "handoff-acquisition",
                "run_id": "prior-acquire-run",
                "created_at": "2026-07-13T12:00:00Z",
                "agent": {"agent_label": "fake", "runtime_label": "harness"},
                "query": "bounded source discovery",
                "provider": {"name": "fixture", "method": "static"},
                "discovery_budget": {"max_candidates": 1, "max_selected": 1},
                "candidates": [
                    {"candidate_id": "selected", "locator": "inbox:selected.txt", "metadata": {}}
                ],
                "selected": ["selected"],
                "selection_rationale": ["Declared fixture."],
                "preservation_state": "inbox-staged",
                "next_artifact": "source-transition",
            }
            write_json(root / "reports" / "acquisitions" / "handoff-acquisition.json", acquisition)
            run(["git", "add", "reports/acquisitions/handoff-acquisition.json"], root)
            run(["git", "commit", "-q", "-m", "record acquisition"], root)
            (root / "inbox" / "different.txt").write_text("not selected\n", encoding="utf-8")

            completed = run(
                [
                    sys.executable,
                    "tools/wiki_cron.py",
                    "inbox",
                    "--authority",
                    "handoff-ingest",
                    "--acquisition-id",
                    "handoff-acquisition",
                ],
                root,
                check=False,
            )

            self.assertEqual(completed.returncode, 1)
            self.assertIn("acquisition handoff mismatch", completed.stdout + completed.stderr)
            self.assertTrue((root / "inbox" / "different.txt").is_file())
            self.assertEqual(list((root / "sources" / "raw").glob("*-different.txt")), [])


if __name__ == "__main__":
    unittest.main()
