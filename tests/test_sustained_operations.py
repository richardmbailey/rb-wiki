from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

from release_test_support import TEMPLATE

sys.path.insert(0, str(TEMPLATE / "tools"))
sys.path.insert(0, str(TEMPLATE / "tests"))

from run_lib import MutationLock
from wiki_run import finish_session, start_session
from wiki_test_support import add_authority, make_git_wiki, run, run_controller
from fake_agent_harness import add_proposal_authority, proposal, write_json, write_proposal_run


class SustainedOperationTests(unittest.TestCase):
    def test_accelerated_handoffs_overlap_recovery_and_bounded_telemetry(self) -> None:
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
            add_authority(
                root,
                "cron-ingest",
                mode="scheduled-propose",
                lane="ingest",
                action="ingest-sources",
                input_roots=["inbox"],
                writable_paths=[
                    "sources/raw/**", "sources/derived/**", "sources/_source_registry.yml",
                    "wiki/references/**", "wiki/index.md", ".wiki_cache/graph.json",
                    "reports/ingest/**", "reports/runs/**", "reports/latest.json",
                ],
                page_types=["Reference"],
                commit_policy="scoped-auto",
            )
            add_proposal_authority(root, "routine")

            acquired = start_session(root, "acquire", "scheduled-propose", "acquirer")
            acquisition = {
                "schema_version": "rb-wiki-acquisition-result/0.2",
                "acquisition_id": "sustained-acquisition",
                "run_id": acquired["run_id"],
                "created_at": "2026-07-13T12:00:00Z",
                "agent": {"agent_label": "sustained-fixture", "runtime_label": "test"},
                "query": "selected sustained source",
                "provider": {"name": "fixture", "method": "static"},
                "discovery_budget": {"max_candidates": 1, "max_selected": 1},
                "candidates": [{"candidate_id": "source", "locator": "inbox:sustained.txt", "metadata": {}}],
                "selected": ["source"],
                "selection_rationale": ["Exercise artifact handoff."],
                "preservation_state": "inbox-staged",
                "next_artifact": "source-transition",
            }
            write_json(root / "reports" / "acquisitions" / "sustained-acquisition.json", acquisition)
            code, _record = finish_session(root, acquired["run_id"], acquired["run_token"], [])
            self.assertEqual(code, 3)
            run(["git", "add", "."], root)
            run(["git", "commit", "-q", "-m", "record acquisition handoff"], root)

            (root / "inbox" / "sustained.txt").write_text("sustained evidence\n", encoding="utf-8")
            ingested = run(
                [
                    sys.executable, "tools/wiki_cron.py", "inbox", "--authority", "cron-ingest",
                    "--acquisition-id", "sustained-acquisition",
                ],
                root,
                check=False,
            )
            self.assertEqual(ingested.returncode, 0, ingested.stdout + ingested.stderr)
            self.assertEqual(len(list((root / "sources" / "raw").glob("*-sustained.txt"))), 1)

            proposed_run = start_session(root, "synthesize", "scheduled-propose", "proposal-agent")
            proposed = proposal(proposed_run["run_id"], proposal_id="sustained-proposal", with_payload=False)
            write_proposal_run(root, proposed_run["run_id"], proposed)
            code, _record = finish_session(
                root, proposed_run["run_id"], proposed_run["run_token"], []
            )
            self.assertEqual(code, 3)
            run(["git", "add", "."], root)
            run(["git", "commit", "-q", "-m", "record proposal handoff"], root)

            routed = run_controller(root)
            self.assertEqual(routed.returncode, 3, routed.stdout + routed.stderr)
            reference = next((root / "wiki" / "references").glob("*-sustained.md"))
            self.assertIn(
                "/" + reference.relative_to(root / "wiki").as_posix(),
                (root / "wiki" / "index.md").read_text(encoding="utf-8"),
            )
            run(["git", "add", "."], root)
            run(["git", "commit", "-q", "-m", "record scheduled routing maintenance"], root)

            durable_before = len(list((root / "reports" / "runs").glob("*.json")))
            for _ in range(8):
                completed = run_controller(root)
                self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
            self.assertEqual(durable_before, len(list((root / "reports" / "runs").glob("*.json"))))
            self.assertEqual(run(["git", "status", "--porcelain"], root).stdout, "")

            lock = MutationLock(root, "overlap-owner", "maintain", "scheduled-propose")
            lock.acquire()
            try:
                blocked = run_controller(root)
                self.assertEqual(blocked.returncode, 2)
            finally:
                lock.release()

            recovery = root / "inbox" / "recovery.txt"
            recovery.write_text("restart evidence\n", encoding="utf-8")
            digest = hashlib.sha256(recovery.read_bytes()).hexdigest()
            failed = run(
                [sys.executable, "tools/ingest.py", "inbox/recovery.txt", "--fault-after", "registered"],
                root,
                check=False,
                env_overrides={"RB_WIKI_RUN_CONTROLLER": "1", "RB_WIKI_FAULT_INJECTION": "1"},
            )
            self.assertEqual(failed.returncode, 1)
            resumed = run(
                [sys.executable, "tools/ingest.py", "--resume-digest", digest],
                root,
                check=False,
                env_overrides={"RB_WIKI_RUN_CONTROLLER": "1"},
            )
            self.assertEqual(resumed.returncode, 0, resumed.stdout + resumed.stderr)
            journal = json.loads((root / ".wiki_state" / "sources" / f"{digest}.json").read_text(encoding="utf-8"))
            self.assertEqual(journal["outcome"], "complete")


if __name__ == "__main__":
    unittest.main()
