from __future__ import annotations

import json
import hashlib
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

from release_test_support import REPO, TEMPLATE, init_git, make_v01, run, tree_hashes

sys.path.insert(0, str(TEMPLATE / "tools"))
sys.path.insert(0, str(TEMPLATE / "tests"))
from fake_agent_harness import proposal  # noqa: E402
from wiki_run import new_record  # noqa: E402


class WikiDoctorTests(unittest.TestCase):
    def doctor(self, root: Path):
        completed = run(
            [sys.executable, str(TEMPLATE / "tools" / "wiki_doctor.py"), "--json", "--root", str(root)],
            REPO,
            check=False,
        )
        return completed, json.loads(completed.stdout)

    def test_doctor_is_read_only_on_a_clean_v02_wiki(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "wiki"
            shutil.copytree(TEMPLATE, root, ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".wiki_state"))
            init_git(root)
            before = tree_hashes(root)
            completed, report = self.doctor(root)
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertEqual(report["overall"], "healthy")
            self.assertEqual(before, tree_hashes(root))

    def test_doctor_diagnoses_dirty_governance_stale_lock_and_incomplete_state(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "wiki"
            shutil.copytree(TEMPLATE, root, ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".wiki_state"))
            init_git(root)
            (root / "schema" / "agent_policy.yml").write_text(
                (root / "schema" / "agent_policy.yml").read_text(encoding="utf-8") + "\n",
                encoding="utf-8",
            )
            lock = root / ".wiki_state" / "mutation.lock"
            lock.mkdir(parents=True)
            (lock / "owner.json").write_text(
                json.dumps({"run_id": "missing-session", "pid": 99999999, "host": "test-host"}), encoding="utf-8"
            )
            runs = root / ".wiki_state" / "runs"
            runs.mkdir(parents=True)
            (runs / "incomplete.json").write_text('{"state":"running"}\n', encoding="utf-8")
            completed, report = self.doctor(root)
            self.assertEqual(completed.returncode, 0)
            self.assertEqual(report["overall"], "attention")
            by_id = {item["diagnostic_id"]: item for item in report["diagnostics"]}
            self.assertEqual(by_id["governance-dirt"]["status"], "warn")
            self.assertEqual(by_id["mutation-lock"]["status"], "warn")
            self.assertEqual(by_id["incomplete-runs"]["status"], "warn")

    def test_doctor_rejects_schema_shaped_but_semantically_impossible_run(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "wiki"
            shutil.copytree(TEMPLATE, root, ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".wiki_state"))
            init_git(root)
            run_id = "20260713T120000Z-abcdef123456"
            record = new_record(
                run_id,
                "wiki",
                "maintain",
                "scheduled-propose",
                "grant",
                [],
                {
                    "schema_version": "rb-wiki-lane-contract/0.2",
                    "lane_id": "deterministic-maintain",
                    "controller_lane": "maintain",
                    "path": "schema/lanes/deterministic-maintain.yml",
                    "digest_sha256": "a" * 64,
                },
                root,
            )
            record.update(state="running", result="success")
            runs = root / ".wiki_state" / "runs"
            runs.mkdir(parents=True)
            (runs / f"{run_id}.json").write_text(json.dumps(record), encoding="utf-8")
            completed, report = self.doctor(root)
            self.assertEqual(completed.returncode, 0)
            by_id = {item["diagnostic_id"]: item for item in report["diagnostics"]}
            self.assertEqual(by_id["incomplete-runs"]["status"], "warn")
            self.assertTrue(
                any("non-terminal run cannot have a result" in item for item in by_id["incomplete-runs"]["evidence"])
            )

    def test_doctor_identifies_branch_moved_recovery_stage(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "wiki"
            shutil.copytree(TEMPLATE, root, ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".wiki_state"))
            init_git(root)
            base = run(["git", "rev-parse", "HEAD"], root).stdout.strip()
            run_id = "20260713T120000Z-abcdef123456"
            page = root / "wiki" / "index.md"
            page.write_text(page.read_text(encoding="utf-8") + "\ntransaction test\n", encoding="utf-8")
            run(["git", "add", "wiki/index.md"], root)
            run(["git", "commit", "-m", f"transaction test\n\nRB-Wiki-Run: {run_id}"], root)
            commit = run(["git", "rev-parse", "HEAD"], root).stdout.strip()
            tree = run(["git", "rev-parse", "HEAD^{tree}"], root).stdout.strip()
            branch = run(["git", "symbolic-ref", "HEAD"], root).stdout.strip()
            digest = hashlib.sha256(page.read_bytes()).hexdigest()
            manifest = hashlib.sha256(f"wiki/index.md\0{digest}".encode("utf-8")).hexdigest()
            transaction = {
                "schema_version": "rb-wiki-git-transaction/0.2",
                "run_id": run_id,
                "stage": "branch-moved",
                "base_commit": base,
                "branch_ref": branch,
                "expected_paths": ["wiki/index.md"],
                "content_manifest": manifest,
                "commit_hash": commit,
                "tree_hash": tree,
                "branch_head": commit,
                "created_at": "2026-07-13T12:00:00Z",
                "updated_at": "2026-07-13T12:00:01Z",
                "error": "injected read-tree failure",
            }
            transactions = root / ".wiki_state" / "transactions"
            transactions.mkdir(parents=True)
            (transactions / f"{run_id}.json").write_text(json.dumps(transaction), encoding="utf-8")
            completed, report = self.doctor(root)
            self.assertEqual(completed.returncode, 0)
            by_id = {item["diagnostic_id"]: item for item in report["diagnostics"]}
            recovery = by_id["transaction-recovery"]
            self.assertEqual(recovery["status"], "warn")
            self.assertTrue(any("index refresh and receipt" in item for item in recovery["evidence"]))

    def test_doctor_diagnoses_v01_policy_and_provenance_compatibility(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = make_v01(Path(temporary), local_override=True, policy_diverged=True)
            completed, report = self.doctor(root)
            self.assertEqual(completed.returncode, 1)
            self.assertEqual(report["overall"], "blocked")
            by_id = {item["diagnostic_id"]: item for item in report["diagnostics"]}
            self.assertEqual(by_id["versions-and-policy"]["status"], "fail")
            self.assertEqual(by_id["provenance"]["status"], "pass")
            self.assertIn("scheduled-propose", by_id["unavailable-capabilities"]["evidence"])

    def test_doctor_reports_missing_dependencies_without_a_traceback(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "wiki"
            shutil.copytree(TEMPLATE, root, ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".wiki_state"))
            init_git(root)
            completed = run(
                [
                    sys.executable,
                    "-S",
                    str(TEMPLATE / "tools" / "wiki_doctor.py"),
                    "--json",
                    "--root",
                    str(root),
                ],
                REPO,
                check=False,
            )
            self.assertEqual(completed.returncode, 1)
            self.assertNotIn("Traceback", completed.stderr)
            report = json.loads(completed.stdout)
            by_id = {item["diagnostic_id"]: item for item in report["diagnostics"]}
            self.assertEqual(report["overall"], "blocked")
            self.assertEqual(by_id["dependencies"]["status"], "fail")

    def test_doctor_does_not_execute_target_wiki_tools(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "wiki"
            shutil.copytree(TEMPLATE, root, ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".wiki_state"))
            init_git(root)
            marker = Path(temporary) / "target-tool-executed"
            (root / "tools" / "provenance.py").write_text(
                f"from pathlib import Path\nPath({str(marker)!r}).write_text('executed')\n",
                encoding="utf-8",
            )
            completed, report = self.doctor(root)
            self.assertEqual(completed.returncode, 0)
            self.assertFalse(marker.exists())
            by_id = {item["diagnostic_id"]: item for item in report["diagnostics"]}
            self.assertEqual(by_id["provenance"]["status"], "pass")

    def test_doctor_reports_stale_proposal_capability_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "wiki"
            shutil.copytree(TEMPLATE, root, ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".wiki_state"))
            proposed = proposal("prior-run", proposal_id="stale-proposal")
            proposed["policy_snapshot"]["capabilities"]["digest_sha256"] = "0" * 64
            (root / "reports" / "proposals" / "stale-proposal.json").write_text(
                json.dumps(proposed), encoding="utf-8"
            )
            init_git(root)
            completed, report = self.doctor(root)
            self.assertEqual(completed.returncode, 1)
            by_id = {item["diagnostic_id"]: item for item in report["diagnostics"]}
            snapshot = by_id["proposal-capability-snapshots"]
            self.assertEqual(snapshot["status"], "fail")
            self.assertTrue(any("stale" in item for item in snapshot["evidence"]))

    def test_doctor_reports_malformed_lock_owner_without_crashing(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "wiki"
            shutil.copytree(TEMPLATE, root, ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".wiki_state"))
            init_git(root)
            lock = root / ".wiki_state" / "mutation.lock"
            lock.mkdir(parents=True)
            (lock / "owner.json").write_text(json.dumps({"pid": None, "run_id": "../../escape"}), encoding="utf-8")
            completed, report = self.doctor(root)
            self.assertEqual(completed.returncode, 1)
            self.assertNotIn("Traceback", completed.stderr)
            by_id = {item["diagnostic_id"]: item for item in report["diagnostics"]}
            self.assertEqual(by_id["mutation-lock"]["status"], "fail")

    def test_doctor_rejects_symlinked_lock_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            parent = Path(temporary)
            root = parent / "wiki"
            shutil.copytree(TEMPLATE, root, ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".wiki_state"))
            init_git(root)
            external_lock = parent / "external-lock"
            external_lock.mkdir()
            state = root / ".wiki_state"
            state.mkdir()
            (state / "mutation.lock").symlink_to(external_lock, target_is_directory=True)
            completed, report = self.doctor(root)
            self.assertEqual(completed.returncode, 1)
            by_id = {item["diagnostic_id"]: item for item in report["diagnostics"]}
            self.assertEqual(by_id["mutation-lock"]["status"], "fail")

    def test_doctor_does_not_follow_symlinked_target_data_directories(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            parent = Path(temporary)
            root = parent / "wiki"
            shutil.copytree(TEMPLATE, root, ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".wiki_state"))
            init_git(root)
            external_sources = parent / "external-sources"
            shutil.move(root / "sources", external_sources)
            (root / "sources").symlink_to(external_sources, target_is_directory=True)
            completed, report = self.doctor(root)
            self.assertEqual(completed.returncode, 1)
            self.assertNotIn("Traceback", completed.stderr)
            by_id = {item["diagnostic_id"]: item for item in report["diagnostics"]}
            self.assertEqual(by_id["provenance"]["status"], "fail")
            self.assertTrue(any("symlink" in item for item in by_id["provenance"]["evidence"]))


if __name__ == "__main__":
    unittest.main()
