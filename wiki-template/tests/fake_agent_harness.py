"""Deterministic, offline external-agent fixture for semantic-lane integration tests."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from capabilities import capability_snapshot
from semantic_protocol import digest_payload
from wiki_test_support import add_authority, run

SOURCE_ID = "2026-07-09-llm-wiki-system-instructions"
REFERENCE = "/references/2026-07-09-llm-wiki-system-instructions.md"
FIXTURE_VERSION = "rb-wiki-fake-agent-fixture/0.2"
FIXTURE_RANDOM_SEED = None


def target_content(title: str = "Agent synthesis", *, cited: bool = True) -> str:
    sources = f'["{REFERENCE}"]' if cited else "[]"
    return f'''---
type: Synthesis
title: "{title}"
description: "A deterministic fake-agent synthesis used to test semantic run boundaries."
resource: ""
tags: [test, synthesis]
timestamp: 2026-07-13T00:00:00Z
created: 2026-07-13
status: active
profile: llm-wiki-profile/0.1
sources: {sources}
confidence: medium
---

This deterministic content is data supplied through an exact proposal payload.
'''


def proposal(
    run_id: str,
    proposal_id: str = "test-proposal",
    *,
    tier: str = "routine",
    action_class: str = "new-synthesis",
    path: str = "wiki/syntheses/agent-synthesis.md",
    content: str | None = None,
    contradictions: list[str] | None = None,
    with_payload: bool = True,
) -> dict[str, Any]:
    text = content if content is not None else target_content()
    payload = {
        "kind": "target-content",
        "files": [
            {"path": path, "content": text, "hash_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest()}
        ],
    } if with_payload else None
    return {
        "schema_version": "rb-wiki-synthesis-proposal/0.2",
        "proposal_id": proposal_id,
        "run_id": run_id,
        "created_at": "2026-07-13T12:00:00Z",
        "agent": {"agent_label": "deterministic-fake-agent", "runtime_label": "test-harness/0.2"},
        "intended_use": "Exercise bounded semantic controller behavior.",
        "action_class": action_class,
        "consequence_tier": tier,
        "affected_pages": [path],
        "source_ids": [SOURCE_ID],
        "agent_findings": ["A declared test finding."],
        "deterministic_evidence": ["Registry and target hashes are checked by the controller."],
        "planned_claims": ["The payload is deterministic."],
        "planned_sections": ["Summary"],
        "uncertainties": ["Semantic truth is not asserted by the harness."],
        "contradictions": contradictions or [],
        "checks_performed": ["source-selection"],
        "required_approvals": ["high-consequence-reviewer"] if tier == "high-consequence" else [],
        "policy_snapshot": {
            "agent_policy_id": "conservative-default",
            "consequence_policy_version": "rb-wiki-consequence-policy/0.2",
            "capabilities": capability_snapshot(),
        },
        "apply_payload": payload,
        "proposal_digest": digest_payload(payload) if payload else None,
    }


def semantic_output(
    run_id: str, proposal_record: dict[str, Any], *, applied: bool = False, approval_required: bool = False
) -> dict[str, Any]:
    return {
        "schema_version": "rb-wiki-semantic-output/0.2",
        "run_id": run_id,
        "proposal_id": proposal_record["proposal_id"],
        "agent": proposal_record["agent"],
        "policy_snapshot": proposal_record["policy_snapshot"],
        "source_ids": proposal_record["source_ids"],
        "agent_findings": proposal_record["agent_findings"],
        "deterministic_evidence": proposal_record["deterministic_evidence"],
        "uncertainties": proposal_record["uncertainties"],
        "contradictions": proposal_record["contradictions"],
        "checks_performed": proposal_record["checks_performed"],
        "proposed_changes": proposal_record["affected_pages"],
        "applied_changes": proposal_record["affected_pages"] if applied else [],
        "approval_required": approval_required,
        "created_at": "2026-07-13T12:05:00Z",
    }


def approval(proposal_record: dict[str, Any], approval_id: str = "test-approval") -> dict[str, Any]:
    return {
        "schema_version": "rb-wiki-approval-record/0.2",
        "approval_id": approval_id,
        "proposal_id": proposal_record["proposal_id"],
        "proposal_run_id": proposal_record["run_id"],
        "proposal_digest": proposal_record["proposal_digest"],
        "decision": "approved",
        "approver_label": "test reviewer",
        "approver_role": "high-consequence-reviewer",
        "scope": proposal_record["affected_pages"],
        "conditions": ["Apply the exact target-content payload only."],
        "issued_at": "2026-01-01T00:00:00Z",
        "expires_at": "2099-01-01T00:00:00Z",
        "policy_version": "rb-wiki-consequence-policy/0.2",
    }


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")


def write_proposal_run(root: Path, run_id: str, record: dict[str, Any]) -> None:
    write_json(root / "reports" / "proposals" / f"{record['proposal_id']}.json", record)
    write_json(
        root / "reports" / "semantic" / f"{run_id}.json",
        semantic_output(run_id, record, approval_required=record["consequence_tier"] == "high-consequence"),
    )


def write_apply_run(root: Path, run_id: str, record: dict[str, Any], *, content: str | None = None) -> None:
    item = record["apply_payload"]["files"][0]
    path = root / item["path"]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content if content is not None else item["content"], encoding="utf-8")
    write_json(root / "reports" / "semantic" / f"{run_id}.json", semantic_output(run_id, record, applied=True))


def add_proposal_authority(root: Path, tier: str = "high-consequence") -> None:
    add_authority(
        root,
        "proposal-agent",
        mode="scheduled-propose",
        lane="synthesize",
        action="propose-synthesis",
        writable_paths=["reports/proposals/**", "reports/semantic/**", "reports/runs/**", "reports/latest.json"],
        page_types=[],
        commit_policy="manual",
        consequence_tier=tier,
    )


def add_apply_authority(root: Path, tier: str = "high-consequence", commit_policy: str = "scoped-auto") -> None:
    add_authority(
        root,
        "apply-agent",
        mode="authorised-autonomous-apply",
        lane="synthesize",
        action="edit-wiki-pages",
        writable_paths=[
            "wiki/syntheses/**",
            "reports/semantic/**",
            "reports/runs/**",
            "reports/latest.json",
        ],
        page_types=["Synthesis"],
        commit_policy=commit_policy,
        consequence_tier=tier,
    )


def commit_artifact(root: Path, relative: str, data: dict[str, Any], message: str) -> None:
    write_json(root / relative, data)
    run(["git", "add", relative], root)
    run(["git", "commit", "-q", "-m", message], root)
