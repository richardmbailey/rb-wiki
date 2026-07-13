#!/usr/bin/env python3
"""Validate semantic-lane artifacts, consequence policy, and exact apply payloads."""

from __future__ import annotations

import hashlib
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from capabilities import capability_snapshot
from contracts import bind_identity, load_json_contract, load_json_text
from provenance import validate_provenance
from run_lib import (
    ROOT,
    ContractError,
    RunError,
    canonical_json,
    git_show,
    load_yaml_contract,
    load_yaml_text,
    parse_utc,
    validate_safe_paths,
    validate_contract,
)
from source_registry import load_registry_document
from wiki_lib import WIKI_DIR, parse_frontmatter

TIER_ORDER = {"routine": 0, "material": 1, "high-consequence": 2}


def digest_payload(payload: dict[str, Any]) -> str:
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


def load_base_json(
    base: str,
    relative: str,
    contract: str,
    root: Path = ROOT,
    *,
    expected_identity: tuple[str, str] | None = None,
) -> dict[str, Any]:
    text = git_show(base, relative, root)
    return load_json_text(
        text,
        contract,
        f"base {relative}",
        root,
        expected_identity=expected_identity,
    )


def load_policy_bundle(root: Path = ROOT, base: str | None = None) -> tuple[dict[str, Any], dict[str, Any]]:
    if base:
        manifest = load_yaml_text(
            git_show(base, "wiki-manifest.yml", root),
            "wiki-manifest",
            "base wiki-manifest.yml",
            root,
        )
        consequence = load_yaml_text(
            git_show(base, "schema/consequence_policy.yml", root),
            "consequence-policy",
            "base schema/consequence_policy.yml",
            root,
        )
        try:
            domain_text = git_show(base, "schema/domain_policy.yml", root)
        except RunError:
            domain = disabled_domain_policy()
        else:
            domain = load_yaml_text(domain_text, "domain-policy", "base schema/domain_policy.yml", root)
    else:
        manifest = load_yaml_contract(root / "wiki-manifest.yml", "wiki-manifest", root)
        consequence = load_yaml_contract(root / "schema" / "consequence_policy.yml", "consequence-policy", root)
        path = root / "schema" / "domain_policy.yml"
        domain = (
            load_yaml_contract(path, "domain-policy", root)
            if path.exists() or path.is_symlink()
            else disabled_domain_policy()
        )
    bind_identity(
        consequence,
        "policy_id",
        manifest["consequence_policy_id"],
        "schema/consequence_policy.yml",
    )
    for field in ("schema_version", "policy_version"):
        if consequence[field] != manifest["consequence_policy_version"]:
            raise ContractError(
                f"schema/consequence_policy.yml {field} does not match manifest consequence_policy_version"
            )
    validate_domain_precedence(consequence, domain)
    return consequence, domain


def disabled_domain_policy() -> dict[str, Any]:
    return {
        "schema_version": "rb-wiki-domain-policy/0.2",
        "policy_id": "absent-domain-policy",
        "enabled": False,
        "core_invariants": {"raw_immutable": True, "provenance_required": True, "authority_required": True},
        "allowed_source_types": [],
        "source_hierarchy": [],
        "action_minimum_tiers": {},
        "assessment_requirements": [],
        "reviewer_roles": [],
        "ontology": {},
    }


def validate_domain_precedence(consequence: dict[str, Any], domain: dict[str, Any]) -> None:
    if not domain["enabled"]:
        return
    for action, tier in domain["action_minimum_tiers"].items():
        core = consequence["action_minimum_tiers"][action]
        if TIER_ORDER[tier] < TIER_ORDER[core]:
            raise ContractError(f"domain policy weakens core consequence tier for {action}")


def minimum_tier(action: str, consequence: dict[str, Any], domain: dict[str, Any]) -> str:
    core = consequence["action_minimum_tiers"][action]
    local = domain["action_minimum_tiers"].get(action, core) if domain["enabled"] else core
    return local if TIER_ORDER[local] >= TIER_ORDER[core] else core


def validate_acquisition(record: dict[str, Any], run_id: str, root: Path = ROOT) -> None:
    validate_contract(record, "acquisition-result", root)
    if record["run_id"] != run_id:
        raise ContractError("acquisition run_id does not match active run")
    candidates = {item["candidate_id"] for item in record["candidates"]}
    if len(candidates) != len(record["candidates"]):
        raise ContractError("acquisition candidate IDs must be unique")
    if not set(record["selected"]).issubset(candidates):
        raise ContractError("selected acquisition IDs must refer to declared candidates")
    budget = record["discovery_budget"]
    if len(record["candidates"]) > budget["max_candidates"] or len(record["selected"]) > budget["max_selected"]:
        raise ContractError("acquisition record exceeds its declared discovery budget")


def validate_proposal(
    proposal: dict[str, Any], root: Path = ROOT, *, run_id: str | None = None,
    consequence: dict[str, Any] | None = None, domain: dict[str, Any] | None = None,
) -> None:
    validate_contract(proposal, "synthesis-proposal", root)
    try:
        validate_safe_paths(proposal["affected_pages"], "proposal")
        if proposal["apply_payload"] is not None:
            validate_safe_paths(
                [item["path"] for item in proposal["apply_payload"]["files"]], "proposal payload"
            )
    except ContractError as exc:
        raise ContractError(f"unsafe proposal path: {exc}") from exc
    if run_id is not None and proposal["run_id"] != run_id:
        raise ContractError("proposal run_id does not match active run")
    consequence, domain = (consequence, domain) if consequence and domain else load_policy_bundle(root)
    declared = proposal["consequence_tier"]
    required = minimum_tier(proposal["action_class"], consequence, domain)
    if proposal["contradictions"] and TIER_ORDER[required] < TIER_ORDER["material"]:
        required = "material"
    if TIER_ORDER[declared] < TIER_ORDER[required]:
        raise ContractError(f"proposal tier {declared} is below required tier {required}")
    payload = proposal["apply_payload"]
    if payload is None:
        if declared == "high-consequence":
            raise ContractError("high-consequence proposal requires an exact apply payload")
        if proposal["proposal_digest"] is not None:
            raise ContractError("proposal without payload must have a null digest")
    else:
        paths: list[str] = []
        for item in payload["files"]:
            encoded = item["content"].encode("utf-8")
            if hashlib.sha256(encoded).hexdigest() != item["hash_sha256"]:
                raise ContractError(f"target-content hash mismatch: {item['path']}")
            paths.append(item["path"])
        if len(paths) != len(set(paths)):
            raise ContractError("proposal payload paths must be unique")
        if sorted(paths) != sorted(proposal["affected_pages"]):
            raise ContractError("proposal affected_pages must exactly match target-content paths")
        if digest_payload(payload) != proposal["proposal_digest"]:
            raise ContractError("proposal digest does not bind the exact target-content payload")
    if declared == "high-consequence" and not proposal["required_approvals"]:
        raise ContractError("high-consequence proposal must declare required approval roles")
    if declared == "high-consequence":
        allowed_roles = set(consequence["tiers"][declared]["approver_roles"])
        if domain["enabled"] and domain["reviewer_roles"]:
            allowed_roles.intersection_update(domain["reviewer_roles"])
        if not set(proposal["required_approvals"]).issubset(allowed_roles):
            raise ContractError("proposal requests an approver role not permitted by policy")
    source_entries = {
        entry["source_id"]: entry
        for entry in load_registry_document(root / "sources" / "_source_registry.yml")["sources"]
    }
    missing = sorted(set(proposal["source_ids"]).difference(source_entries))
    if missing:
        raise ContractError("proposal cites unknown source IDs: " + ", ".join(missing))
    if domain["enabled"] and domain["allowed_source_types"]:
        disallowed = sorted(
            source_id for source_id in proposal["source_ids"]
            if source_entries[source_id]["source_type"] not in domain["allowed_source_types"]
        )
        if disallowed:
            raise ContractError("domain policy rejects source types for: " + ", ".join(disallowed))


def validate_semantic_output(output: dict[str, Any], run_id: str, proposal: dict[str, Any], root: Path = ROOT) -> None:
    validate_contract(output, "semantic-output", root)
    if output["run_id"] != run_id or output["proposal_id"] != proposal["proposal_id"]:
        raise ContractError("semantic output does not identify the active run/proposal")
    if sorted(output["source_ids"]) != sorted(proposal["source_ids"]):
        raise ContractError("semantic output source set differs from proposal")
    if output["agent"] != proposal["agent"]:
        raise ContractError("semantic output agent attribution differs from proposal")
    if output["policy_snapshot"] != proposal["policy_snapshot"]:
        raise ContractError("semantic output policy snapshot differs from proposal")


def validate_approval(
    approval: dict[str, Any], proposal: dict[str, Any], consequence: dict[str, Any], domain: dict[str, Any],
    now: datetime | None = None, root: Path = ROOT,
) -> None:
    validate_contract(approval, "approval-record", root)
    current = now or datetime.now(timezone.utc)
    if approval["decision"] != "approved":
        raise ContractError("approval decision is not approved")
    if approval["proposal_id"] != proposal["proposal_id"] or approval["proposal_run_id"] != proposal["run_id"]:
        raise ContractError("approval identifies a different proposal")
    if approval["proposal_digest"] != proposal["proposal_digest"]:
        raise ContractError("approval digest does not bind the current proposal payload")
    if approval["policy_version"] != consequence["policy_version"]:
        raise ContractError("approval policy version does not match the committed consequence policy")
    if parse_utc(approval["issued_at"]) >= parse_utc(approval["expires_at"]):
        raise ContractError("approval expiry must be later than issue time")
    if current < parse_utc(approval["issued_at"]) or current >= parse_utc(approval["expires_at"]):
        raise ContractError("approval is outside its validity window")
    if not set(proposal["affected_pages"]).issubset(approval["scope"]):
        raise ContractError("approval scope does not cover every affected page")
    roles = set(consequence["tiers"][proposal["consequence_tier"]]["approver_roles"])
    if domain["enabled"] and domain["reviewer_roles"]:
        roles.intersection_update(domain["reviewer_roles"])
    if approval["approver_role"] not in roles:
        raise ContractError("approver role is not permitted by committed policy")


def substantive_wiki_paths(paths: list[str]) -> list[str]:
    return sorted(
        path for path in paths
        if path.startswith("wiki/") and path.endswith(".md") and path not in {"wiki/index.md", "wiki/log.md"}
    )


def validate_exact_apply(proposal: dict[str, Any], changed_paths: list[str], root: Path = ROOT) -> None:
    payload = proposal.get("apply_payload")
    if not isinstance(payload, dict):
        raise ContractError("autonomous apply requires an exact target-content payload")
    expected = {item["path"]: item for item in payload["files"]}
    actual = substantive_wiki_paths(changed_paths)
    if actual != sorted(expected):
        raise ContractError(f"substantive diff does not match proposal paths: expected {sorted(expected)}, got {actual}")
    for relative, item in expected.items():
        path = root / relative
        if path.is_symlink() or not path.is_file() or path.read_text(encoding="utf-8") != item["content"]:
            raise ContractError(f"final content does not match approved target payload: {relative}")


def validate_changed_page_citations(paths: list[str], root: Path = ROOT) -> None:
    for relative in substantive_wiki_paths(paths):
        path = root / relative
        frontmatter, _body, error = parse_frontmatter(path)
        if error:
            raise ContractError(f"changed page frontmatter is invalid: {relative}: {error}")
        if frontmatter.get("type") != "Reference" and not frontmatter.get("sources"):
            raise ContractError(f"changed ordinary page has no Reference citation: {relative}")
    provenance_errors = validate_provenance(root=root, contract_root=root)
    if provenance_errors:
        raise ContractError("semantic provenance failed: " + "; ".join(provenance_errors))


def validate_policy_snapshot(
    proposal: dict[str, Any], agent_policy: dict[str, Any], consequence: dict[str, Any], root: Path = ROOT
) -> None:
    snapshot = proposal["policy_snapshot"]
    if snapshot["agent_policy_id"] != agent_policy["policy_id"]:
        raise ContractError("proposal agent policy snapshot does not match committed policy")
    if snapshot["consequence_policy_version"] != consequence["policy_version"]:
        raise ContractError("proposal consequence policy snapshot does not match committed policy")
    active = capability_snapshot(root)
    if snapshot["capabilities"] != active:
        raise ContractError(
            "proposal capability snapshot is missing, stale, or from a pre-hardening v0.2 controller"
        )


def main(argv: list[str]) -> int:
    if len(argv) != 3 or argv[1] not in {"validate-proposal", "validate-acquisition", "validate-semantic-output"}:
        print("usage: python3 tools/semantic_protocol.py validate-proposal|validate-acquisition|validate-semantic-output ARTIFACT")
        return 1
    command, path = argv[1], Path(argv[2])
    try:
        if command == "validate-proposal":
            proposal = load_json_contract(path, "synthesis-proposal", ROOT)
            validate_proposal(proposal)
            print(proposal["proposal_digest"] or "no-payload")
        elif command == "validate-acquisition":
            record = load_json_contract(path, "acquisition-result", ROOT)
            validate_acquisition(record, record["run_id"])
            print("valid")
        else:
            output = load_json_contract(path, "semantic-output", ROOT)
            proposal = load_json_contract(
                ROOT / "reports" / "proposals" / f"{output['proposal_id']}.json",
                "synthesis-proposal",
                ROOT,
            )
            validate_semantic_output(output, output["run_id"], proposal)
            print("valid")
        return 0
    except (ContractError, RunError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
