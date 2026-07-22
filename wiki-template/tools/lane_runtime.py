#!/usr/bin/env python3
"""Load lane contracts and enforce them as executable runtime policy."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path, PurePosixPath
from typing import Any

from contracts import load_json_contract, load_yaml_contract, load_yaml_text, register_semantic_validator
from errors import ContractError, RunError
from run_lib import git_show, run_git
from wiki_context import WikiContext
from fs_safety import enumerate_regular_files
from semantic_protocol import (
    TIER_ORDER,
    load_policy_bundle,
    validate_acquisition,
    validate_approval,
    validate_changed_page_citations,
    validate_exact_apply,
    validate_policy_snapshot,
    validate_proposal,
    validate_semantic_output,
)


EXPECTED_LANE_IDS = {
    "acquire",
    "ingest",
    "synthesize",
    "deterministic-maintain",
    "semantic-maintain",
    "governance-maintain",
}
CONTROLLER_CHECK_IDS = {
    "quick-lint",
    "semantic-output",
    "provenance",
    "proposal-payload",
    "approval-binding",
}
CONTROLLER_ONLY_ARTIFACTS = {"run-record", "source-transition"}

ARTIFACT_WRITE_PATTERNS: dict[str, tuple[str, ...]] = {
    "acquisition-result": ("reports/acquisitions/**",),
    "raw-sources": ("sources/raw/**",),
    "derived-sources": ("sources/derived/**",),
    "source-transition": (),
    "source-registry": ("sources/_source_registry.yml",),
    "reference-pages": ("wiki/references/**",),
    "routing-index": ("wiki/index.md",),
    "graph-cache": (".wiki_cache/graph.json",),
    "ingest-report": ("reports/ingest/**",),
    "synthesis-proposal": ("reports/proposals/**",),
    "semantic-output": ("reports/semantic/**",),
    "lint-report": ("reports/lint/**",),
    "wiki-pages": (
        "wiki/overview.md",
        "wiki/concepts/**",
        "wiki/entities/**",
        "wiki/summaries/**",
        "wiki/syntheses/**",
        "wiki/decisions/**",
        "wiki/contradictions/**",
        "wiki/references/**",
        "wiki/datasets/**",
        "wiki/methods/**",
        "wiki/tools/**",
        "wiki/projects/**",
    ),
    "governance-files": (
        "wiki-manifest.yml",
        "schema/**",
        "tools/**",
        "docs/**",
        "AGENTS.md",
        "README.md",
    ),
    "run-record": ("reports/runs/**", "reports/latest.json"),
}
ARTIFACT_INPUT_PATTERNS: dict[str, tuple[str, ...]] = {
    "inbox-files": ("inbox",),
    "acquisition-result": (),
    "source-transition": (),
    "source-registry": (),
    "reference-pages": (),
    "synthesis-proposal": (),
    "approval-record": (),
    "semantic-output": (),
}


def _canonical_digest(contract: dict[str, Any]) -> str:
    encoded = json.dumps(contract, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _validate_lane_contract_semantics(contract: Any, _context: WikiContext) -> None:
    if not isinstance(contract, dict):
        return  # JSON Schema reports the structural error first.
    modes = set(contract["allowed_modes"])
    for field in (
        "actions_by_mode",
        "closure_profile_by_mode",
        "produces_by_mode",
        "required_produces_by_mode",
        "required_checks_by_mode",
    ):
        actual = set(contract[field])
        if actual != modes:
            raise ContractError(
                f"lane {contract['lane_id']} {field} modes differ from allowed modes: "
                f"expected {sorted(modes)}, got {sorted(actual)}"
            )
    produced = {item for values in contract["produces_by_mode"].values() for item in values}
    if produced != set(contract["produces"]):
        raise ContractError(f"lane {contract['lane_id']} produces does not match produces_by_mode")
    for mode in modes:
        required_outputs = set(contract["required_produces_by_mode"][mode])
        if not required_outputs.issubset(contract["produces_by_mode"][mode]):
            raise ContractError(
                f"lane {contract['lane_id']} required outputs exceed produces for mode {mode}"
            )
    required = {item for values in contract["required_checks_by_mode"].values() for item in values}
    if required != set(contract["required_checks"]):
        raise ContractError(f"lane {contract['lane_id']} required_checks does not match mode-specific checks")
    substantive_modes = set(contract["substantive_wiki_edit_modes"])
    if not substantive_modes.issubset(modes):
        raise ContractError(f"lane {contract['lane_id']} has substantive modes outside allowed_modes")
    if bool(substantive_modes) != contract["substantive_wiki_edits"]:
        raise ContractError(f"lane {contract['lane_id']} substantive edit declaration is inconsistent")
    for mode in substantive_modes:
        if "wiki-pages" not in contract["produces_by_mode"][mode]:
            raise ContractError(f"lane {contract['lane_id']} substantive mode {mode} cannot produce wiki-pages")


register_semantic_validator("lane-contract", _validate_lane_contract_semantics)


def _validate_contract_set(contracts: list[tuple[str, dict[str, Any]]]) -> None:
    lane_ids = [contract["lane_id"] for _path, contract in contracts]
    if set(lane_ids) != EXPECTED_LANE_IDS or len(lane_ids) != len(EXPECTED_LANE_IDS):
        raise ContractError(
            f"lane contract set mismatch: expected {sorted(EXPECTED_LANE_IDS)}, got {sorted(lane_ids)}"
        )
    controller_lanes = [contract["controller_lane"] for _path, contract in contracts]
    duplicates = sorted({lane for lane in controller_lanes if controller_lanes.count(lane) > 1})
    if duplicates:
        raise ContractError("duplicate lane contract controller_lane: " + ", ".join(duplicates))


def load_lane_contracts(root: Path, base_commit: str | None = None) -> list[tuple[str, dict[str, Any]]]:
    context = WikiContext(root)
    contracts: list[tuple[str, dict[str, Any]]] = []
    if base_commit is None:
        paths = enumerate_regular_files(context, "schema/lanes", ".yml")
        for path in paths:
            relative = path.relative_to(context.root).as_posix()
            contracts.append((relative, load_yaml_contract(path, "lane-contract", context.root)))
    else:
        listing = run_git(
            context.root,
            "ls-tree",
            "-r",
            "--name-only",
            base_commit,
            "--",
            "schema/lanes",
        ).stdout.splitlines()
        paths = sorted(
            path for path in listing
            if PurePosixPath(path).parent == PurePosixPath("schema/lanes") and path.endswith(".yml")
        )
        for relative in paths:
            contracts.append(
                (
                    relative,
                    load_yaml_text(
                        git_show(base_commit, relative, context.root),
                        "lane-contract",
                        f"base {relative}",
                        context.root,
                    ),
                )
            )
    _validate_contract_set(contracts)
    return contracts


def validate_lane_contracts(root: Path) -> list[dict[str, Any]]:
    return [contract for _path, contract in load_lane_contracts(root)]


def select_lane_contract(root: Path, controller_lane: str, base_commit: str | None = None) -> dict[str, Any]:
    matches = [
        (path, contract)
        for path, contract in load_lane_contracts(root, base_commit)
        if contract["controller_lane"] == controller_lane
    ]
    if len(matches) != 1:
        raise ContractError(
            f"lane contract selection for {controller_lane} is ambiguous or missing: {len(matches)} matches"
        )
    relative, contract = matches[0]
    return {
        "contract": contract,
        "binding": {
            "schema_version": contract["schema_version"],
            "lane_id": contract["lane_id"],
            "controller_lane": contract["controller_lane"],
            "path": relative,
            "digest_sha256": _canonical_digest(contract),
        },
    }


def _pattern_within(candidate: str, boundary: str) -> bool:
    if boundary.endswith("/**"):
        prefix = boundary[:-3].rstrip("/")
        return candidate == prefix or candidate == boundary or candidate.startswith(prefix + "/")
    return candidate == boundary


def artifact_patterns(contract: dict[str, Any], mode: str, *, include_controller: bool) -> list[str]:
    artifacts = contract["produces_by_mode"][mode]
    patterns: list[str] = []
    for artifact in artifacts:
        if not include_controller and artifact in CONTROLLER_ONLY_ARTIFACTS:
            continue
        patterns.extend(ARTIFACT_WRITE_PATTERNS[artifact])
    return sorted(set(patterns))


def closure_profile(contract: dict[str, Any], mode: str) -> str:
    try:
        return str(contract["closure_profile_by_mode"][mode])
    except KeyError as exc:
        raise ContractError(
            f"lane contract {contract.get('lane_id', '<unknown>')} has no closure profile for mode {mode}"
        ) from exc


def effective_writable_paths(contract: dict[str, Any], authority: dict[str, Any], mode: str) -> list[str]:
    allowed_patterns = artifact_patterns(contract, mode, include_controller=True)
    return sorted(
        candidate
        for candidate in authority["writable_paths"]
        if any(_pattern_within(candidate, boundary) for boundary in allowed_patterns)
    )


def validate_lane_authority(contract: dict[str, Any], authority: dict[str, Any], mode: str) -> list[str]:
    lane_id = contract["lane_id"]
    if mode not in contract["allowed_modes"]:
        raise ContractError(f"lane contract {lane_id} does not allow mode {mode}")
    required_action = contract["actions_by_mode"][mode]
    if required_action not in authority["actions"]:
        raise ContractError(f"lane contract {lane_id} requires action {required_action}")
    permitted_actions = {required_action}
    if contract["controller_lane"] == "ingest":
        permitted_actions.add("preserve-unsupported")
    extra_actions = sorted(set(authority["actions"]).difference(permitted_actions))
    if extra_actions:
        raise ContractError(f"lane contract {lane_id} does not permit authority actions: {', '.join(extra_actions)}")

    allowed_outputs = artifact_patterns(contract, mode, include_controller=True)
    output_excess = sorted(
        candidate
        for candidate in authority["writable_paths"]
        if not any(_pattern_within(candidate, boundary) for boundary in allowed_outputs)
    )
    if output_excess:
        raise ContractError(
            f"lane contract {lane_id} rejects authority output scope: {', '.join(output_excess)}"
        )
    allowed_inputs = [
        pattern for artifact in contract["consumes"] for pattern in ARTIFACT_INPUT_PATTERNS[artifact]
    ]
    input_excess = sorted(
        candidate
        for candidate in authority["input_roots"]
        if not any(_pattern_within(candidate, boundary) for boundary in allowed_inputs)
    )
    if input_excess:
        raise ContractError(
            f"lane contract {lane_id} rejects authority input scope: {', '.join(input_excess)}"
        )

    artifacts = set(contract["produces_by_mode"][mode])
    allowed_page_types = set(authority["page_types"])
    if "wiki-pages" not in artifacts:
        if "reference-pages" in artifacts and "Reference" not in allowed_page_types:
            raise ContractError(f"lane contract {lane_id} requires Reference page type permission")
        allowed_page_types.difference_update({"Reference"} if "reference-pages" in artifacts else set())
        if allowed_page_types:
            raise ContractError(
                f"lane contract {lane_id} does not permit page types: {', '.join(sorted(allowed_page_types))}"
            )
    elif mode not in contract["substantive_wiki_edit_modes"] and authority["page_types"]:
        raise ContractError(f"lane contract {lane_id} does not permit substantive page types in mode {mode}")
    elif "wiki-pages" in contract["required_produces_by_mode"][mode] and not authority["page_types"]:
        raise ContractError(f"lane contract {lane_id} authority omits required page type scope")
    effective = effective_writable_paths(contract, authority, mode)
    required_artifacts = contract["required_produces_by_mode"][mode]
    missing_patterns: list[str] = []
    for artifact in required_artifacts:
        patterns = ARTIFACT_WRITE_PATTERNS[artifact]
        if artifact == "wiki-pages":
            if not any(
                _pattern_within(candidate, boundary)
                for candidate in effective
                for boundary in patterns
            ):
                missing_patterns.append("wiki-pages")
            continue
        for required_pattern in patterns:
            if not any(_pattern_within(required_pattern, candidate) for candidate in effective):
                missing_patterns.append(required_pattern)
    if missing_patterns:
        raise ContractError(
            f"lane contract {lane_id} authority omits required output scope: "
            + ", ".join(sorted(set(missing_patterns)))
        )
    return effective


def validate_lane_changes(contract: dict[str, Any], mode: str, changed: list[str]) -> None:
    ordinary = [
        path for path in changed
        if path.startswith("wiki/")
        and path.endswith(".md")
        and path not in {"wiki/index.md", "wiki/log.md"}
        and not ("reference-pages" in contract["produces_by_mode"][mode] and path.startswith("wiki/references/"))
    ]
    if ordinary and mode not in contract["substantive_wiki_edit_modes"]:
        raise RunError(
            f"lane contract {contract['lane_id']} forbids substantive wiki edits: {', '.join(sorted(ordinary))}"
        )
    allowed = artifact_patterns(contract, mode, include_controller=False)
    outside = sorted(path for path in changed if not any(_pattern_within(path, boundary) for boundary in allowed))
    if outside:
        raise RunError(
            f"lane contract {contract['lane_id']} prohibits changed paths: {', '.join(outside)}"
        )


def required_external_checks(contract: dict[str, Any], authority: dict[str, Any], mode: str) -> list[str]:
    required = set(authority["required_checks"]) | set(contract["required_checks_by_mode"][mode])
    return sorted(required.difference(CONTROLLER_CHECK_IDS))


def validate_lane_binding(binding: dict[str, Any], selected: dict[str, Any]) -> None:
    if binding != selected["binding"]:
        raise RunError("runtime lane contract differs from the recorded clean-base contract")


def _validate_acquisition_closure(root: Path, run_id: str, changed: list[str]) -> None:
    artifacts = [path for path in changed if path.startswith("reports/acquisitions/") and path.endswith(".json")]
    if not artifacts:
        raise RunError("acquire lane must produce an acquisition-result artifact")
    if set(changed) != set(artifacts):
        raise RunError("acquire lane changed paths outside acquisition-result artifacts")
    for relative in artifacts:
        record = load_json_contract(root / relative, "acquisition-result", root)
        validate_acquisition(record, run_id, root)
        if Path(relative).stem != record["acquisition_id"]:
            raise RunError("acquisition filename must match acquisition_id")


def _semantic_output(root: Path, run_id: str, proposal: dict[str, Any]) -> dict[str, Any]:
    output = load_json_contract(root / "reports" / "semantic" / f"{run_id}.json", "semantic-output", root)
    validate_semantic_output(output, run_id, proposal, root)
    return output


def _validate_scheduled_synthesis(
    root: Path,
    run_id: str,
    changed: list[str],
    policy: dict[str, Any],
    authority: dict[str, Any],
) -> tuple[dict[str, Any], bool]:
    proposal_paths = [path for path in changed if path.startswith("reports/proposals/") and path.endswith(".json")]
    if len(proposal_paths) != 1:
        raise RunError("scheduled synthesize must produce exactly one proposal artifact")
    consequence, domain = load_policy_bundle(root)
    proposal = load_json_contract(root / proposal_paths[0], "synthesis-proposal", root)
    validate_proposal(proposal, root, run_id=run_id, consequence=consequence, domain=domain)
    validate_policy_snapshot(proposal, policy, consequence, root)
    if Path(proposal_paths[0]).stem != proposal["proposal_id"]:
        raise RunError("proposal filename must match proposal_id")
    if TIER_ORDER[proposal["consequence_tier"]] > TIER_ORDER[authority["consequence_tier"]]:
        raise RunError("proposal consequence tier exceeds authority maximum")
    output = _semantic_output(root, run_id, proposal)
    semantic_paths = [path for path in changed if path.startswith("reports/semantic/")]
    if semantic_paths != [f"reports/semantic/{run_id}.json"]:
        raise RunError("scheduled synthesize must produce exactly one run-bound semantic output")
    expected_artifacts = {proposal_paths[0], f"reports/semantic/{run_id}.json"}
    if set(changed) != expected_artifacts:
        raise RunError("scheduled synthesize changed paths outside its proposal handoff artifacts")
    approval_required = proposal["consequence_tier"] == "high-consequence"
    if output["approval_required"] != approval_required or output["applied_changes"]:
        raise RunError("scheduled semantic output must distinguish proposal from apply state")
    return proposal, approval_required


def _validate_autonomous_apply(
    root: Path, run_id: str, changed: list[str], session: dict[str, Any]
) -> dict[str, Any]:
    context = session.get("semantic_context") or {}
    proposal = context.get("proposal")
    if not isinstance(proposal, dict):
        raise RunError("autonomous semantic apply lacks a validated base-committed proposal")
    protected = [
        path for path in changed
        if path.startswith("reports/proposals/") or path.startswith("reports/approvals/")
    ]
    if protected:
        raise RunError("apply run may not create or modify its proposal/approval: " + ", ".join(protected))
    expected_paths = set(proposal["affected_pages"]) | {f"reports/semantic/{run_id}.json"}
    if set(changed) != expected_paths:
        raise RunError("autonomous apply changed paths outside its exact page and semantic-output payload")
    if proposal["consequence_tier"] == "high-consequence":
        approval = context.get("approval")
        if not isinstance(approval, dict):
            raise RunError("high-consequence apply lacks a validated approval")
        validate_approval(
            approval,
            proposal,
            context["consequence_policy"],
            context["domain_policy"],
            root=root,
        )
    validate_exact_apply(proposal, changed, root)
    validate_changed_page_citations(changed, root)
    output = _semantic_output(root, run_id, proposal)
    expected = sorted(proposal["affected_pages"])
    if sorted(output["applied_changes"]) != expected or output["approval_required"]:
        raise RunError("apply semantic output does not identify the exact applied payload")
    return proposal


def validate_lane_closure(
    contract: dict[str, Any],
    mode: str,
    root: Path,
    run_id: str,
    changed: list[str],
    policy: dict[str, Any],
    authority: dict[str, Any],
    session: dict[str, Any],
) -> tuple[dict[str, Any] | None, bool]:
    """Dispatch contract-selected closure behavior without branching on lane names."""
    profile = closure_profile(contract, mode)
    if profile == "acquisition-result":
        _validate_acquisition_closure(root, run_id, changed)
        return None, False
    if profile == "scheduled-synthesis":
        return _validate_scheduled_synthesis(root, run_id, changed, policy, authority)
    if profile == "autonomous-semantic-apply":
        return _validate_autonomous_apply(root, run_id, changed, session), False
    if profile == "manual-semantic":
        validate_changed_page_citations(changed, root)
    return None, False
