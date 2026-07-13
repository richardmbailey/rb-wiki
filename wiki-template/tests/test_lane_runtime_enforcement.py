from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from run_lib import ContractError  # noqa: E402
from run_lib import RunError  # noqa: E402
from wiki_run import finish_session, start_session, terminate_session  # noqa: E402
from wiki_test_support import add_authority, make_git_wiki  # noqa: E402


AUDIT_PATHS = ["reports/runs/**", "reports/latest.json"]


class LaneRuntimeEnforcementTests(unittest.TestCase):
    def assert_start_rejects_overbroad_grant(
        self,
        root: Path,
        authority_id: str,
        lane: str,
        mode: str,
        action: str,
        writable_paths: list[str],
        page_types: list[str],
        *,
        input_roots: list[str] | None = None,
    ) -> None:
        add_authority(
            root,
            authority_id,
            mode=mode,
            lane=lane,
            action=action,
            input_roots=input_roots,
            writable_paths=writable_paths,
            page_types=page_types,
            commit_policy="scoped-auto",
        )
        authorised_head = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=root, text=True, capture_output=True, check=True
        ).stdout.strip()
        with self.assertRaisesRegex(ContractError, "lane contract"):
            start_session(root, lane, mode, authority_id)
        after = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=root, text=True, capture_output=True, check=True
        ).stdout.strip()
        self.assertEqual(after, authorised_head)
        self.assertFalse((root / ".wiki_state" / "mutation.lock").exists())

    def test_maintenance_grant_cannot_include_substantive_page_scope(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = make_git_wiki(Path(temporary))
            self.assert_start_rejects_overbroad_grant(
                root,
                "broad-maintainer",
                "maintain",
                "scheduled-propose",
                "deterministic-maintenance",
                ["wiki/index.md", ".wiki_cache/graph.json", "wiki/concepts/**", *AUDIT_PATHS],
                ["Concept"],
            )

    def test_acquire_and_ingest_grants_cannot_include_ordinary_page_scope(self) -> None:
        cases = [
            (
                "broad-acquirer",
                "acquire",
                "acquire-sources",
                ["reports/acquisitions/**", "wiki/concepts/**", *AUDIT_PATHS],
                [],
                ["Concept"],
            ),
            (
                "broad-ingestor",
                "ingest",
                "ingest-sources",
                [
                    "sources/raw/**",
                    "sources/derived/**",
                    "sources/_source_registry.yml",
                    "wiki/references/**",
                    "wiki/index.md",
                    ".wiki_cache/graph.json",
                    "reports/ingest/**",
                    "wiki/concepts/**",
                    *AUDIT_PATHS,
                ],
                ["inbox"],
                ["Reference", "Concept"],
            ),
        ]
        for authority_id, lane, action, paths, inputs, page_types in cases:
            with self.subTest(lane=lane), tempfile.TemporaryDirectory() as temporary:
                root = make_git_wiki(Path(temporary))
                self.assert_start_rejects_overbroad_grant(
                    root,
                    authority_id,
                    lane,
                    "scheduled-propose",
                    action,
                    paths,
                    page_types,
                    input_roots=inputs,
                )

    def test_lane_contract_rejects_a_mode_even_when_authority_allows_it(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = make_git_wiki(Path(temporary))
            add_authority(
                root,
                "scheduled-semantic",
                mode="scheduled-propose",
                lane="semantic",
                action="edit-wiki-pages",
                writable_paths=["wiki/concepts/**", *AUDIT_PATHS],
                page_types=["Concept"],
            )
            with self.assertRaisesRegex(ContractError, "lane contract.*mode"):
                start_session(root, "semantic", "scheduled-propose", "scheduled-semantic")

    def test_session_binds_lane_contract_identity_and_digest(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = make_git_wiki(Path(temporary))
            add_authority(
                root,
                "manual-editor",
                mode="manual-assist",
                lane="semantic",
                action="edit-wiki-pages",
                writable_paths=["wiki/concepts/**", *AUDIT_PATHS],
                page_types=["Concept"],
            )
            envelope = start_session(root, "semantic", "manual-assist", "manual-editor")
            self.assertEqual(envelope["lane_contract"]["lane_id"], "semantic-maintain")
            self.assertRegex(envelope["lane_contract"]["digest_sha256"], r"^[a-f0-9]{64}$")
            session = json.loads(
                (root / ".wiki_state" / "sessions" / f"{envelope['run_id']}.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(session["lane_contract"], envelope["lane_contract"])
            self.assertEqual(session["record"]["lane_contract"], envelope["lane_contract"])

    def test_broad_output_scope_is_rejected_even_without_page_permissions(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = make_git_wiki(Path(temporary))
            add_authority(
                root,
                "broad-maintainer",
                mode="scheduled-propose",
                lane="maintain",
                action="deterministic-maintenance",
                writable_paths=[
                    "wiki/index.md",
                    ".wiki_cache/graph.json",
                    "wiki/concepts/**",
                    *AUDIT_PATHS,
                ],
                page_types=[],
            )
            with self.assertRaisesRegex(ContractError, "output scope"):
                start_session(root, "maintain", "scheduled-propose", "broad-maintainer")

    def test_forbidden_page_change_cannot_move_the_branch_at_closure(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = make_git_wiki(Path(temporary))
            add_authority(
                root,
                "bounded-maintainer",
                mode="scheduled-propose",
                lane="maintain",
                action="deterministic-maintenance",
                writable_paths=["wiki/index.md", ".wiki_cache/graph.json", *AUDIT_PATHS],
                page_types=[],
                commit_policy="scoped-auto",
            )
            head = subprocess.run(
                ["git", "rev-parse", "HEAD"], cwd=root, text=True, capture_output=True, check=True
            ).stdout.strip()
            envelope = start_session(root, "maintain", "scheduled-propose", "bounded-maintainer")
            page = root / "wiki" / "concepts" / "forbidden.md"
            page.write_text("# forbidden\n", encoding="utf-8")
            with self.assertRaisesRegex(RunError, "lane contract"):
                finish_session(root, envelope["run_id"], envelope["run_token"], ["quick-lint=pass"])
            after = subprocess.run(
                ["git", "rev-parse", "HEAD"], cwd=root, text=True, capture_output=True, check=True
            ).stdout.strip()
            self.assertEqual(after, head)
            terminate_session(root, envelope["run_id"], envelope["run_token"], "failed", "test cleanup")

    def test_required_page_type_permissions_fail_fast(self) -> None:
        cases = [
            (
                "ingest-without-reference",
                "ingest",
                "scheduled-propose",
                "ingest-sources",
                [
                    "sources/raw/**",
                    "sources/derived/**",
                    "sources/_source_registry.yml",
                    "wiki/references/**",
                    "wiki/index.md",
                    ".wiki_cache/graph.json",
                    "reports/ingest/**",
                    *AUDIT_PATHS,
                ],
                ["inbox"],
                "Reference page type",
            ),
            (
                "semantic-without-page-type",
                "semantic",
                "manual-assist",
                "edit-wiki-pages",
                ["wiki/concepts/**", *AUDIT_PATHS],
                [],
                "page type scope",
            ),
        ]
        for authority_id, lane, mode, action, paths, inputs, message in cases:
            with self.subTest(lane=lane), tempfile.TemporaryDirectory() as temporary:
                root = make_git_wiki(Path(temporary))
                add_authority(
                    root,
                    authority_id,
                    mode=mode,
                    lane=lane,
                    action=action,
                    writable_paths=paths,
                    input_roots=inputs,
                    page_types=[],
                )
                with self.assertRaisesRegex(ContractError, message):
                    start_session(root, lane, mode, authority_id)

    def test_authority_cannot_include_an_action_from_another_mode(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = make_git_wiki(Path(temporary))
            add_authority(
                root,
                "mixed-mode-proposer",
                mode="scheduled-propose",
                lane="synthesize",
                action=["propose-synthesis", "edit-wiki-pages"],
                writable_paths=[
                    "reports/proposals/**",
                    "reports/semantic/**",
                    *AUDIT_PATHS,
                ],
                page_types=[],
            )
            with self.assertRaisesRegex(ContractError, "does not permit authority actions"):
                start_session(root, "synthesize", "scheduled-propose", "mixed-mode-proposer")

    def test_uncommitted_scope_cannot_expand_scheduled_or_autonomous_authority(self) -> None:
        cases = [
            (
                "proposal-agent",
                "scheduled-propose",
                "propose-synthesis",
                ["reports/proposals/**", "reports/semantic/**", *AUDIT_PATHS],
                [],
                "  - wiki/syntheses/**\n",
            ),
            (
                "apply-agent",
                "authorised-autonomous-apply",
                "edit-wiki-pages",
                ["wiki/syntheses/**", "reports/semantic/**", *AUDIT_PATHS],
                ["Synthesis"],
                "  - reports/proposals/**\n",
            ),
        ]
        for authority_id, mode, action, paths, page_types, injected in cases:
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as temporary:
                root = make_git_wiki(Path(temporary))
                add_authority(
                    root,
                    authority_id,
                    mode=mode,
                    lane="synthesize",
                    action=action,
                    writable_paths=paths,
                    page_types=page_types,
                )
                grant = root / "schema" / "authorities" / f"{authority_id}.yml"
                grant.write_text(
                    grant.read_text(encoding="utf-8").replace(
                        "page_types:", injected + "page_types:"
                    ),
                    encoding="utf-8",
                )
                with self.assertRaisesRegex(ContractError, "output scope"):
                    start_session(root, "synthesize", mode, authority_id)
                self.assertFalse((root / ".wiki_state" / "mutation.lock").exists())


if __name__ == "__main__":
    unittest.main()
