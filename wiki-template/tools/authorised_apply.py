#!/usr/bin/env python3
"""Select and materialise one base-committed, authority-bounded proposal."""

from __future__ import annotations

import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any

from authority import load_base_policy, validate_authority
from errors import ContractError, RunError
from fs_safety import safe_path, symlink_component
from lane_runtime import closure_profile, select_lane_contract, validate_lane_authority
from run_lib import (
    atomic_write_json,
    atomic_write_text,
    git_base_commit,
    git_show,
    git_status_entries,
    parse_utc,
    path_allowed,
    run_git,
    utc_now,
    validate_contract,
)
from semantic_protocol import (
    TIER_ORDER,
    load_base_json,
    load_policy_bundle,
    validate_approval,
    validate_policy_snapshot,
    validate_proposal,
    validate_semantic_output,
)
from validate_frontmatter import validate_page
from wiki_lib import parse_frontmatter


APPLY_MODE = "authorised-autonomous-apply"


@dataclass(frozen=True)
class ApplyCandidate:
    base_commit: str
    lane: str
    introduction_commit: str
    proposal: dict[str, Any]
    approval_id: str | None


@dataclass(frozen=True)
class CandidateRejection:
    proposal_id: str
    reason: str


@dataclass(frozen=True)
class CandidateSelection:
    base_commit: str
    lane: str
    candidate: ApplyCandidate | None
    rejected: tuple[CandidateRejection, ...]


def _committed_json_paths(root: Path, base: str, directory: str) -> list[str]:
    listing = run_git(root, "ls-tree", "-r", "--name-only", base, "--", directory).stdout
    parent = PurePosixPath(directory)
    return sorted(
        relative
        for relative in listing.splitlines()
        if PurePosixPath(relative).parent == parent and relative.endswith(".json")
    )


def _proposal_introduction(root: Path, base: str, relative: str) -> str:
    output = run_git(
        root,
        "log",
        "--format=%H",
        "--diff-filter=A",
        base,
        "--",
        relative,
    ).stdout.splitlines()
    if not output:
        raise ContractError("proposal has no committed introduction commit")
    return output[0]


def _base_text_or_missing(root: Path, commit: str, relative: str) -> str | None:
    listing = run_git(root, "ls-tree", "--name-only", commit, "--", relative).stdout.splitlines()
    if relative not in listing:
        return None
    return git_show(commit, relative, root)


def _select_apply_lane(
    root: Path,
    base: str,
    manifest: dict[str, Any],
    policy: dict[str, Any],
    authority: dict[str, Any],
    now: datetime,
) -> tuple[str, list[str]]:
    matches: list[tuple[str, list[str]]] = []
    for lane in sorted(set(authority["lanes"]).intersection({"semantic", "synthesize"})):
        validate_authority(authority, policy, lane, APPLY_MODE, now)
        selected = select_lane_contract(root, lane, base)
        if manifest["lane_contract_version"] != selected["contract"]["schema_version"]:
            raise ContractError("base manifest lane_contract_version does not match the selected lane contract")
        if closure_profile(selected["contract"], APPLY_MODE) != "autonomous-semantic-apply":
            continue
        matches.append(
            (lane, validate_lane_authority(selected["contract"], authority, APPLY_MODE))
        )
    if not matches:
        raise ContractError("authority has no authorised autonomous-apply lane")
    if len(matches) != 1:
        raise ContractError("authority must select exactly one autonomous-apply lane")
    return matches[0]


def _preflight_payload(
    root: Path,
    proposal: dict[str, Any],
    authority: dict[str, Any],
    effective_paths: list[str],
) -> None:
    payload = proposal.get("apply_payload")
    if not isinstance(payload, dict) or payload.get("kind") != "target-content":
        raise ContractError("authorised apply requires an exact target-content payload")
    if proposal["affected_pages"] != [item["path"] for item in payload["files"]]:
        raise ContractError("proposal affected_pages order must match its exact payload files")
    expected_changed_paths = len(set(proposal["affected_pages"])) + 1
    if expected_changed_paths > authority["budgets"]["max_changed_paths"]:
        raise ContractError("proposal exceeds authority changed-path budget")
    with tempfile.TemporaryDirectory(prefix="rb-wiki-apply-preflight-") as temporary:
        temporary_root = Path(temporary)
        for item in payload["files"]:
            relative = item["path"]
            if PurePosixPath(relative).as_posix() != relative:
                raise ContractError(f"proposal target is not a canonical repository path: {relative}")
            if not path_allowed(relative, effective_paths):
                raise ContractError(f"proposal target is outside authority writable path scope: {relative}")
            destination = root / relative
            unsafe = symlink_component(destination, root)
            if unsafe is not None:
                raise ContractError(
                    f"proposal target traverses a symlink: {unsafe.relative_to(root).as_posix()}"
                )
            safe_path(root, relative, allow_missing=True)
            temporary_page = temporary_root.joinpath(*PurePosixPath(relative).parts)
            temporary_page.parent.mkdir(parents=True, exist_ok=True)
            temporary_page.write_text(item["content"], encoding="utf-8", newline="\n")
            errors = validate_page(
                temporary_page,
                contract_root=root,
                label=relative,
            )
            if errors:
                raise ContractError("final page frontmatter is invalid: " + "; ".join(errors))
            frontmatter, _body, error = parse_frontmatter(temporary_page, root)
            if error:
                raise ContractError(f"final page frontmatter is invalid: {relative}: {error}")
            page_type = frontmatter.get("type")
            if page_type not in authority["page_types"]:
                raise ContractError(
                    f"proposal page type is outside authority scope: {relative} ({page_type})"
                )


def _validate_original_handoff(
    root: Path,
    base: str,
    proposal: dict[str, Any],
    consequence: dict[str, Any],
) -> None:
    relative = f"reports/semantic/{proposal['run_id']}.json"
    output = load_base_json(base, relative, "semantic-output", root)
    validate_semantic_output(output, proposal["run_id"], proposal, root)
    for field in (
        "agent_findings",
        "deterministic_evidence",
        "uncertainties",
        "contradictions",
        "checks_performed",
    ):
        if output[field] != proposal[field]:
            raise ContractError(f"original semantic handoff {field} differs from the proposal")
    if output["proposed_changes"] != proposal["affected_pages"]:
        raise ContractError("original semantic handoff does not identify the exact proposed paths")
    if output["applied_changes"]:
        raise ContractError("original semantic handoff is already in an applied state")
    expected_approval = bool(consequence["tiers"][proposal["consequence_tier"]]["approval_required"])
    if output["approval_required"] != expected_approval:
        raise ContractError("original semantic handoff has an invalid approval-required state")


def _validate_application_state(
    root: Path,
    base: str,
    introduction: str,
    proposal: dict[str, Any],
) -> None:
    payload = proposal["apply_payload"]
    matches: list[bool] = []
    committed_now: dict[str, str | None] = {}
    for item in payload["files"]:
        relative = item["path"]
        current = _base_text_or_missing(root, base, relative)
        committed_now[relative] = current
        matches.append(current == item["content"])
    if all(matches):
        raise ContractError("proposal is already fully applied")
    if any(matches):
        raise ContractError("proposal is partially applied")
    stale = [
        relative
        for relative in committed_now
        if run_git(
            root,
            "log",
            "--format=%H",
            f"{introduction}..{base}",
            "--",
            relative,
        ).stdout.splitlines()
    ]
    if stale:
        raise ContractError(
            "target changed since proposal introduction: " + ", ".join(sorted(stale))
        )


def _select_approval(
    root: Path,
    base: str,
    proposal: dict[str, Any],
    consequence: dict[str, Any],
    domain: dict[str, Any],
    now: datetime,
) -> str | None:
    if not consequence["tiers"][proposal["consequence_tier"]]["approval_required"]:
        return None
    valid: list[tuple[datetime, str]] = []
    invalid: list[str] = []
    for relative in _committed_json_paths(root, base, "reports/approvals"):
        approval_id = Path(relative).stem
        try:
            approval = load_base_json(
                base,
                relative,
                "approval-record",
                root,
                expected_identity=("approval_id", approval_id),
            )
        except (ContractError, RunError) as exc:
            invalid.append(f"{approval_id}: {exc}")
            continue
        if approval["proposal_id"] != proposal["proposal_id"]:
            continue
        try:
            validate_approval(approval, proposal, consequence, domain, now=now, root=root)
        except (ContractError, RunError) as exc:
            invalid.append(f"{approval_id}: {exc}")
            continue
        valid.append((parse_utc(approval["issued_at"]), approval_id))
    if not valid:
        detail = "; ".join(invalid) if invalid else "none found"
        raise ContractError("proposal has no valid committed approval: " + detail)
    return min(valid)[1]


def _validate_candidate(
    root: Path,
    base: str,
    relative: str,
    lane: str,
    policy: dict[str, Any],
    authority: dict[str, Any],
    effective_paths: list[str],
    consequence: dict[str, Any],
    domain: dict[str, Any],
    now: datetime,
) -> ApplyCandidate:
    proposal_id = Path(relative).stem
    proposal = load_base_json(
        base,
        relative,
        "synthesis-proposal",
        root,
        expected_identity=("proposal_id", proposal_id),
    )
    validate_proposal(proposal, root, consequence=consequence, domain=domain)
    validate_policy_snapshot(proposal, policy, consequence, root)
    if TIER_ORDER[proposal["consequence_tier"]] > TIER_ORDER[authority["consequence_tier"]]:
        raise ContractError("proposal consequence tier exceeds authority consequence tier")
    _preflight_payload(root, proposal, authority, effective_paths)
    _validate_original_handoff(root, base, proposal, consequence)
    introduction = _proposal_introduction(root, base, relative)
    _validate_application_state(root, base, introduction, proposal)
    approval_id = _select_approval(root, base, proposal, consequence, domain, now)
    return ApplyCandidate(base, lane, introduction, proposal, approval_id)


def select_authorised_candidate(
    root: Path,
    authority_id: str,
    *,
    now: datetime | None = None,
) -> CandidateSelection:
    """Return at most one valid committed proposal in reproducible order."""
    entries = git_status_entries(root)
    if entries:
        paths = ", ".join(sorted({item["path"] for item in entries}))
        raise RunError("authorised apply requires a clean committed base; unexpected paths: " + paths)
    base = git_base_commit(root)
    manifest, policy, authority = load_base_policy(base, authority_id, root)
    current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    lane, effective_paths = _select_apply_lane(
        root, base, manifest, policy, authority, current
    )
    consequence, domain = load_policy_bundle(root, base)
    candidates: list[ApplyCandidate] = []
    rejected: list[CandidateRejection] = []
    for relative in _committed_json_paths(root, base, "reports/proposals"):
        proposal_id = Path(relative).stem
        try:
            candidates.append(
                _validate_candidate(
                    root,
                    base,
                    relative,
                    lane,
                    policy,
                    authority,
                    effective_paths,
                    consequence,
                    domain,
                    current,
                )
            )
        except (ContractError, RunError, OSError, UnicodeError) as exc:
            rejected.append(CandidateRejection(proposal_id, str(exc)))
    candidates.sort(key=lambda item: (parse_utc(item.proposal["created_at"]), item.proposal["proposal_id"]))
    return CandidateSelection(base, lane, candidates[0] if candidates else None, tuple(rejected))


def preflight_session_candidate(session: dict[str, Any], root: Path) -> ApplyCandidate:
    """Revalidate and return the session's own base-bound proposal context."""
    record = session["record"]
    if record["mode"] != APPLY_MODE or record["state"] != "running":
        raise RunError("authorised apply payload writing requires a running apply session")
    base = record["base_commit"]
    if git_base_commit(root) != base:
        raise RunError("HEAD changed after the authorised apply session started")
    current_entries = git_status_entries(root)
    if record["initial_snapshot"] or current_entries:
        raise RunError("authorised apply session requires an unchanged clean committed base")

    manifest, policy, authority = load_base_policy(base, record["authority_id"], root)
    validate_authority(authority, policy, record["lane"], APPLY_MODE)
    selected_lane = select_lane_contract(root, record["lane"], base)
    if manifest["lane_contract_version"] != selected_lane["contract"]["schema_version"]:
        raise RunError("session lane contract version differs from its committed base")
    effective_paths = validate_lane_authority(selected_lane["contract"], authority, APPLY_MODE)
    if (
        record.get("wiki_id") != manifest["wiki_id"]
        or session.get("policy") != policy
        or session.get("authority") != authority
        or session.get("lane_contract") != selected_lane["binding"]
        or record["lane_contract"] != selected_lane["binding"]
        or record["writable_paths"] != effective_paths
    ):
        raise RunError("authorised apply session scope differs from its committed base")

    proposal = session.get("semantic_context", {}).get("proposal")
    if not isinstance(proposal, dict):
        raise RunError("authorised apply session has no base-bound proposal context")
    if session.get("proposal_id") != proposal.get("proposal_id"):
        raise RunError("authorised apply session proposal identity is inconsistent")
    relative = f"reports/proposals/{proposal['proposal_id']}.json"
    consequence, domain = load_policy_bundle(root, base)
    candidate = _validate_candidate(
        root,
        base,
        relative,
        record["lane"],
        policy,
        authority,
        effective_paths,
        consequence,
        domain,
        datetime.now(timezone.utc),
    )
    if candidate.proposal != proposal:
        raise RunError("session proposal context differs from the reloaded committed proposal")
    semantic_context = session["semantic_context"]
    if (
        semantic_context.get("consequence_policy") != consequence
        or semantic_context.get("domain_policy") != domain
    ):
        raise RunError("session semantic policy context differs from the committed base")
    if candidate.approval_id != session.get("approval_id"):
        raise RunError("session approval differs from the deterministic committed approval selection")
    expected_approval = None
    if candidate.approval_id is not None:
        expected_approval = load_base_json(
            base,
            f"reports/approvals/{candidate.approval_id}.json",
            "approval-record",
            root,
            expected_identity=("approval_id", candidate.approval_id),
        )
    if semantic_context.get("approval") != expected_approval:
        raise RunError("session approval context differs from the committed base")
    return ApplyCandidate(
        candidate.base_commit,
        candidate.lane,
        candidate.introduction_commit,
        proposal,
        candidate.approval_id,
    )


def build_applied_semantic_output(
    run_id: str,
    proposal: dict[str, Any],
    *,
    root: Path | None = None,
) -> dict[str, Any]:
    output = {
        "schema_version": "rb-wiki-semantic-output/0.2",
        "run_id": run_id,
        "proposal_id": proposal["proposal_id"],
        "agent": proposal["agent"],
        "policy_snapshot": proposal["policy_snapshot"],
        "source_ids": proposal["source_ids"],
        "agent_findings": proposal["agent_findings"],
        "deterministic_evidence": proposal["deterministic_evidence"],
        "uncertainties": proposal["uncertainties"],
        "contradictions": proposal["contradictions"],
        "checks_performed": proposal["checks_performed"],
        "proposed_changes": proposal["affected_pages"],
        "applied_changes": proposal["affected_pages"],
        "approval_required": False,
        "created_at": utc_now(),
    }
    contract_root = root or Path(__file__).resolve().parents[1]
    validate_contract(output, "semantic-output", contract_root)
    validate_semantic_output(output, run_id, proposal, contract_root)
    if output["applied_changes"] != proposal["affected_pages"]:
        raise ContractError("applied_changes must exactly equal proposal affected_pages")
    return output


def write_session_payload(root: Path, run_id: str, candidate: ApplyCandidate) -> None:
    """Write only preflighted target bytes and the validated run semantic output."""
    proposal = candidate.proposal
    output = build_applied_semantic_output(run_id, proposal, root=root)
    for item in proposal["apply_payload"]["files"]:
        atomic_write_text(root / item["path"], item["content"], root)
    atomic_write_json(root / "reports" / "semantic" / f"{run_id}.json", output, root)
