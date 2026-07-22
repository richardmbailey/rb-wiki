from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from authorised_apply import (  # noqa: E402
    build_applied_semantic_output,
    select_authorised_candidate,
)
from run_lib import ContractError, RunError, validate_contract  # noqa: E402
from semantic_protocol import digest_payload  # noqa: E402
from wiki_test_support import add_authority, make_git_wiki, run  # noqa: E402
from fake_agent_harness import (  # noqa: E402
    add_apply_authority,
    approval,
    commit_artifact,
    proposal,
    target_content,
    write_proposal_run,
)


def commit_proposal_bundle(root: Path, proposed: dict[str, object], message: str = "add proposal bundle") -> None:
    write_proposal_run(root, str(proposed["run_id"]), proposed)
    paths = [
        f"reports/proposals/{proposed['proposal_id']}.json",
        f"reports/semantic/{proposed['run_id']}.json",
    ]
    run(["git", "add", *paths], root)
    run(["git", "commit", "-q", "-m", message], root)


def rejection_text(selection: object) -> str:
    return "\n".join(item.reason for item in selection.rejected)


class AuthorisedApplySelectionTests(unittest.TestCase):
    def test_high_consequence_candidate_requires_and_selects_valid_committed_approval(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = make_git_wiki(Path(temporary))
            add_apply_authority(root, "high-consequence")
            proposed = proposal("proposal-run", tier="high-consequence")
            commit_proposal_bundle(root, proposed)
            without_approval = select_authorised_candidate(root, "apply-agent")
            self.assertIsNone(without_approval.candidate)
            self.assertIn("no valid committed approval", rejection_text(without_approval))

            approved = approval(proposed)
            commit_artifact(
                root,
                "reports/approvals/test-approval.json",
                approved,
                "add valid approval",
            )
            with_approval = select_authorised_candidate(root, "apply-agent")
            self.assertEqual(with_approval.candidate.approval_id, "test-approval")

    def test_selection_is_deterministic_and_semantic_output_uses_exact_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = make_git_wiki(Path(temporary))
            add_apply_authority(root, "routine")
            later = proposal(
                "proposal-run-later",
                proposal_id="z-proposal",
                path="wiki/syntheses/z-proposal.md",
            )
            later["created_at"] = "2026-07-13T13:00:00Z"
            earlier = proposal(
                "proposal-run-earlier",
                proposal_id="a-proposal",
                path="wiki/syntheses/a-proposal.md",
            )
            earlier["created_at"] = "2026-07-13T12:00:00Z"
            commit_proposal_bundle(root, later, "add later proposal")
            commit_proposal_bundle(root, earlier, "add earlier proposal")

            first = select_authorised_candidate(root, "apply-agent")
            second = select_authorised_candidate(root, "apply-agent")

            self.assertEqual(first.candidate.proposal["proposal_id"], "a-proposal")
            self.assertEqual(second.candidate.proposal["proposal_id"], "a-proposal")
            output = build_applied_semantic_output("apply-run", first.candidate.proposal)
            self.assertEqual(output["applied_changes"], first.candidate.proposal["affected_pages"])
            self.assertEqual(output["applied_changes"], ["wiki/syntheses/a-proposal.md"])
            prose = {**output, "applied_changes": ["Applied the proposal successfully."]}
            with self.assertRaisesRegex(ContractError, "applied_changes"):
                validate_contract(prose, "semantic-output", root)

    def test_selection_rejects_consequence_path_page_type_and_action_scope(self) -> None:
        cases = [
            (
                "consequence",
                lambda root: add_apply_authority(root, "routine"),
                lambda: proposal("proposal-run", tier="material"),
                "consequence tier",
                False,
            ),
            (
                "path",
                lambda root: add_apply_authority(root, "routine"),
                lambda: proposal("proposal-run", path="wiki/concepts/outside-path.md"),
                "writable path scope",
                False,
            ),
            (
                "page-type",
                lambda root: add_apply_authority(root, "routine"),
                lambda: proposal(
                    "proposal-run",
                    content=target_content().replace("type: Synthesis", "type: Concept", 1),
                ),
                "page type",
                False,
            ),
            (
                "action",
                lambda root: add_authority(
                    root,
                    "wrong-action",
                    mode="authorised-autonomous-apply",
                    lane="synthesize",
                    action="propose-synthesis",
                    writable_paths=[
                        "wiki/syntheses/**",
                        "reports/semantic/**",
                        "reports/runs/**",
                        "reports/latest.json",
                    ],
                    page_types=["Synthesis"],
                ),
                lambda: proposal("proposal-run"),
                "requires action edit-wiki-pages",
                True,
            ),
        ]
        for name, add_grant, make_proposal, expected, raises in cases:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as temporary:
                root = make_git_wiki(Path(temporary))
                add_grant(root)
                proposed = make_proposal()
                commit_proposal_bundle(root, proposed)
                if raises:
                    with self.assertRaisesRegex(ContractError, expected):
                        select_authorised_candidate(root, "wrong-action")
                else:
                    selection = select_authorised_candidate(root, "apply-agent")
                    self.assertIsNone(selection.candidate)
                    self.assertIn(expected, rejection_text(selection))

    def test_selection_rejects_malformed_uncommitted_stale_partial_applied_and_invalid_pages(self) -> None:
        with self.subTest("malformed"), tempfile.TemporaryDirectory() as temporary:
            root = make_git_wiki(Path(temporary))
            add_apply_authority(root, "routine")
            malformed = root / "reports" / "proposals" / "malformed.json"
            malformed.parent.mkdir(parents=True, exist_ok=True)
            malformed.write_text('{"proposal_id":"malformed"}\n', encoding="utf-8")
            run(["git", "add", malformed.relative_to(root).as_posix()], root)
            run(["git", "commit", "-q", "-m", "add malformed proposal"], root)
            selection = select_authorised_candidate(root, "apply-agent")
            self.assertIsNone(selection.candidate)
            self.assertIn("contract violation", rejection_text(selection))

        with self.subTest("uncommitted"), tempfile.TemporaryDirectory() as temporary:
            root = make_git_wiki(Path(temporary))
            add_apply_authority(root, "routine")
            proposed = proposal("proposal-run")
            write_proposal_run(root, str(proposed["run_id"]), proposed)
            with self.assertRaisesRegex(RunError, "clean committed base"):
                select_authorised_candidate(root, "apply-agent")

        with self.subTest("missing-handoff"), tempfile.TemporaryDirectory() as temporary:
            root = make_git_wiki(Path(temporary))
            add_apply_authority(root, "routine")
            proposed = proposal("proposal-run")
            proposal_path = root / "reports" / "proposals" / "test-proposal.json"
            proposal_path.parent.mkdir(parents=True, exist_ok=True)
            proposal_path.write_text(json.dumps(proposed) + "\n", encoding="utf-8")
            run(["git", "add", proposal_path.relative_to(root).as_posix()], root)
            run(["git", "commit", "-q", "-m", "add proposal without handoff"], root)
            selection = select_authorised_candidate(root, "apply-agent")
            self.assertIsNone(selection.candidate)
            self.assertIn("reports/semantic/proposal-run.json", rejection_text(selection))

        with self.subTest("mismatched-handoff"), tempfile.TemporaryDirectory() as temporary:
            root = make_git_wiki(Path(temporary))
            add_apply_authority(root, "routine")
            proposed = proposal("proposal-run")
            write_proposal_run(root, str(proposed["run_id"]), proposed)
            semantic_path = root / "reports" / "semantic" / "proposal-run.json"
            semantic = json.loads(semantic_path.read_text(encoding="utf-8"))
            semantic["uncertainties"] = ["This handoff no longer matches its proposal."]
            semantic_path.write_text(json.dumps(semantic) + "\n", encoding="utf-8")
            run(
                [
                    "git",
                    "add",
                    "reports/proposals/test-proposal.json",
                    "reports/semantic/proposal-run.json",
                ],
                root,
            )
            run(["git", "commit", "-q", "-m", "add mismatched semantic handoff"], root)
            selection = select_authorised_candidate(root, "apply-agent")
            self.assertIsNone(selection.candidate)
            self.assertIn("uncertainties differs", rejection_text(selection))

        with self.subTest("stale"), tempfile.TemporaryDirectory() as temporary:
            root = make_git_wiki(Path(temporary))
            add_apply_authority(root, "routine")
            relative = "wiki/syntheses/llm-wiki-vs-rag.md"
            current = (root / relative).read_text(encoding="utf-8")
            proposed = proposal(
                "proposal-run",
                path=relative,
                content=current + "\nProposed bounded update.\n",
                action_class="update-synthesis",
            )
            commit_proposal_bundle(root, proposed)
            (root / relative).write_text(current + "\nNewer human edit.\n", encoding="utf-8")
            run(["git", "add", relative], root)
            run(["git", "commit", "-q", "-m", "newer target edit"], root)
            selection = select_authorised_candidate(root, "apply-agent")
            self.assertIsNone(selection.candidate)
            self.assertIn("changed since proposal introduction", rejection_text(selection))
            (root / relative).write_text(current, encoding="utf-8")
            run(["git", "add", relative], root)
            run(["git", "commit", "-q", "-m", "revert newer target edit"], root)
            reverted = select_authorised_candidate(root, "apply-agent")
            self.assertIsNone(reverted.candidate)
            self.assertIn("changed since proposal introduction", rejection_text(reverted))

        with self.subTest("partially-applied"), tempfile.TemporaryDirectory() as temporary:
            root = make_git_wiki(Path(temporary))
            add_apply_authority(root, "routine")
            proposed = proposal("proposal-run")
            first = proposed["apply_payload"]["files"][0]
            second_content = target_content("Second target")
            second = {
                "path": "wiki/syntheses/second-target.md",
                "content": second_content,
                "hash_sha256": hashlib.sha256(second_content.encode("utf-8")).hexdigest(),
            }
            proposed["apply_payload"]["files"].append(second)
            proposed["affected_pages"].append(second["path"])
            proposed["proposal_digest"] = digest_payload(proposed["apply_payload"])
            commit_proposal_bundle(root, proposed)
            target = root / str(first["path"])
            target.write_text(str(first["content"]), encoding="utf-8")
            run(["git", "add", str(first["path"])], root)
            run(["git", "commit", "-q", "-m", "partially apply proposal"], root)
            selection = select_authorised_candidate(root, "apply-agent")
            self.assertIsNone(selection.candidate)
            self.assertIn("partially applied", rejection_text(selection))

        with self.subTest("already-applied"), tempfile.TemporaryDirectory() as temporary:
            root = make_git_wiki(Path(temporary))
            add_apply_authority(root, "routine")
            proposed = proposal("proposal-run")
            commit_proposal_bundle(root, proposed)
            item = proposed["apply_payload"]["files"][0]
            target = root / str(item["path"])
            target.write_text(str(item["content"]), encoding="utf-8")
            run(["git", "add", str(item["path"])], root)
            run(["git", "commit", "-q", "-m", "apply proposal elsewhere"], root)
            selection = select_authorised_candidate(root, "apply-agent")
            self.assertIsNone(selection.candidate)
            self.assertIn("already fully applied", rejection_text(selection))

        with self.subTest("invalid-frontmatter"), tempfile.TemporaryDirectory() as temporary:
            root = make_git_wiki(Path(temporary))
            add_apply_authority(root, "routine")
            proposed = proposal("proposal-run", content="# Missing frontmatter\n")
            commit_proposal_bundle(root, proposed)
            selection = select_authorised_candidate(root, "apply-agent")
            self.assertIsNone(selection.candidate)
            self.assertIn("frontmatter", rejection_text(selection))


class AuthorisedApplyEndToEndTests(unittest.TestCase):
    def prepared(self, parent: Path, *, broken_link: bool = False) -> tuple[Path, dict[str, object]]:
        root = make_git_wiki(parent)
        add_apply_authority(root, "routine", commit_policy="scoped-auto")
        content = target_content("Deterministic apply")
        if broken_link:
            content += "\n[Missing target](/concepts/does-not-exist.md)\n"
        proposed = proposal("proposal-run", content=content)
        commit_proposal_bundle(root, proposed)
        return root, proposed

    def test_apply_command_commits_only_payload_semantic_and_controller_records(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root, proposed = self.prepared(Path(temporary))
            base = run(["git", "rev-parse", "HEAD"], root).stdout.strip()
            index_before = hashlib.sha256((root / "wiki" / "index.md").read_bytes()).hexdigest()
            graph_before = hashlib.sha256((root / ".wiki_cache" / "graph.json").read_bytes()).hexdigest()

            completed = run(
                [sys.executable, "tools/wiki_cron.py", "apply", "--authority", "apply-agent"],
                root,
                check=False,
            )

            self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
            self.assertEqual(run(["git", "status", "--porcelain"], root).stdout, "")
            self.assertNotEqual(run(["git", "rev-parse", "HEAD"], root).stdout.strip(), base)
            committed = set(
                run(["git", "diff-tree", "--no-commit-id", "--name-only", "-r", "HEAD"], root)
                .stdout.splitlines()
            )
            run_paths = sorted(path for path in committed if path.startswith("reports/runs/"))
            self.assertEqual(len(run_paths), 2)
            run_id = Path(run_paths[0]).stem
            self.assertEqual(
                committed,
                {
                    "wiki/syntheses/agent-synthesis.md",
                    f"reports/semantic/{run_id}.json",
                    f"reports/runs/{run_id}.json",
                    f"reports/runs/{run_id}.md",
                    "reports/latest.json",
                },
            )
            semantic = json.loads(
                run(["git", "show", f"HEAD:reports/semantic/{run_id}.json"], root).stdout
            )
            self.assertEqual(semantic["applied_changes"], proposed["affected_pages"])
            self.assertEqual(hashlib.sha256((root / "wiki" / "index.md").read_bytes()).hexdigest(), index_before)
            self.assertEqual(hashlib.sha256((root / ".wiki_cache" / "graph.json").read_bytes()).hexdigest(), graph_before)

    def test_lint_failure_preserves_evidence_without_committing_generated_page(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root, _proposed = self.prepared(Path(temporary), broken_link=True)
            base = run(["git", "rev-parse", "HEAD"], root).stdout.strip()

            completed = run(
                [sys.executable, "tools/wiki_cron.py", "apply", "--authority", "apply-agent"],
                root,
                check=False,
            )

            self.assertEqual(completed.returncode, 1, completed.stdout + completed.stderr)
            self.assertEqual(run(["git", "rev-parse", "HEAD"], root).stdout.strip(), base)
            records = list((root / "reports" / "runs").glob("*.json"))
            self.assertEqual(len(records), 1)
            record = json.loads(records[0].read_text(encoding="utf-8"))
            self.assertEqual(record["state"], "failed")
            self.assertIn("recover any material changes", record["next_action"])
            self.assertTrue((root / "wiki" / "syntheses" / "agent-synthesis.md").exists())
            self.assertFalse((root / ".wiki_state" / "mutation.lock").exists())

    def test_transaction_failure_preserves_committed_recovery_state(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root, _proposed = self.prepared(Path(temporary))
            completed = run(
                [sys.executable, "tools/wiki_cron.py", "apply", "--authority", "apply-agent"],
                root,
                check=False,
                env_overrides={"RB_WIKI_FAULT_STAGE": "after-cas"},
            )

            self.assertEqual(completed.returncode, 5, completed.stdout + completed.stderr)
            record = json.loads((root / ".wiki_state" / "latest.json").read_text(encoding="utf-8"))
            self.assertEqual(record["state"], "committed-recovery-required")
            self.assertIsNotNone(record["commit_hash"])
            self.assertTrue((root / ".wiki_state" / "mutation.lock").exists())
            self.assertIn("wiki_run.py recover", record["next_action"])


if __name__ == "__main__":
    unittest.main()
