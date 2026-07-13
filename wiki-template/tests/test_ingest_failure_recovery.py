from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

from wiki_test_support import make_git_wiki, run


class IngestFailureRecoveryTests(unittest.TestCase):
    def engine(self, root: Path, *args: str, fault: str | None = None):
        env = {"RB_WIKI_RUN_CONTROLLER": "1"}
        if fault:
            env["RB_WIKI_FAULT_INJECTION"] = "1"
        command = [sys.executable, "tools/ingest.py", *args]
        if fault:
            command.extend(["--fault-after", fault])
        return run(command, root, check=False, env_overrides=env)

    def test_failure_after_each_transition_has_exact_resume_and_stable_identity(self) -> None:
        transitions = ["captured", "raw-preserved", "registered", "reference-created", "validated", "inbox-archived"]
        for transition in transitions:
            with self.subTest(transition=transition), tempfile.TemporaryDirectory() as temporary:
                root = make_git_wiki(Path(temporary))
                inbox = root / "inbox" / "recover.txt"
                content = b"recoverable evidence\n"
                inbox.write_bytes(content)
                digest = hashlib.sha256(content).hexdigest()
                failed = self.engine(root, "inbox/recover.txt", "--run-id", "fault-run", fault=transition)
                self.assertEqual(failed.returncode, 1)
                journal_path = root / ".wiki_state" / "sources" / f"{digest}.json"
                journal = json.loads(journal_path.read_text(encoding="utf-8"))
                source_id = journal["source_id"]
                evidence = root / journal["raw_path"] if transition != "captured" else inbox
                self.assertTrue(evidence.exists())
                self.assertEqual(hashlib.sha256(evidence.read_bytes()).hexdigest(), digest)
                resumed = self.engine(root, "--resume-digest", digest, "--run-id", "resume-run")
                self.assertEqual(resumed.returncode, 0, resumed.stdout + resumed.stderr)
                final = json.loads(journal_path.read_text(encoding="utf-8"))
                self.assertEqual(final["source_id"], source_id)
                self.assertEqual(final["outcome"], "complete")
                self.assertEqual(final["completed_transitions"], transitions)
                self.assertTrue((root / final["raw_path"]).exists())
                self.assertTrue((root / final["reference_path"]).exists())

    def test_missing_raw_and_reference_are_restored_from_verified_processed_copy(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = make_git_wiki(Path(temporary))
            content = b"restore me\n"
            inbox = root / "inbox" / "restore.txt"
            inbox.write_bytes(content)
            digest = hashlib.sha256(content).hexdigest()
            self.assertEqual(self.engine(root, "inbox/restore.txt").returncode, 0)
            journal = json.loads((root / ".wiki_state" / "sources" / f"{digest}.json").read_text())
            (root / journal["raw_path"]).unlink()
            (root / journal["reference_path"]).unlink()
            resumed = self.engine(root, "--resume-digest", digest)
            self.assertEqual(resumed.returncode, 0, resumed.stdout + resumed.stderr)
            self.assertEqual((root / journal["raw_path"]).read_bytes(), content)
            self.assertTrue((root / journal["reference_path"]).is_file())
            repaired = json.loads(
                (root / ".wiki_state" / "sources" / f"{digest}.json").read_text(encoding="utf-8")
            )
            self.assertEqual(repaired["resume_count"], 1)
            self.assertEqual(
                repaired["last_run_transitions"],
                ["raw-preserved", "registered", "reference-created", "validated", "inbox-archived"],
            )


if __name__ == "__main__":
    unittest.main()
