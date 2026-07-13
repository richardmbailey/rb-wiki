#!/usr/bin/env python3
"""Policy-authorised, single-writer RB Wiki run controller."""

from __future__ import annotations

import argparse
import json
import os
import re
import secrets
import socket
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any

from agent_provenance import validate_agent_provenance, validate_check_evidence_reference
from fs_safety import enumerate_regular_files
from errors import CommittedRecoveryRequired
from git_transaction import advance as advance_git_transaction
from git_transaction import discover_branch_movement, inject_fault, refresh_index_for_recovery, verify_recovery_evidence
from git_transaction import scoped_auto_commit
from run_store import (
    load_receipt,
    load_session_envelope,
    load_transaction,
    prune_ephemeral_records,
    save_receipt,
    save_durable_record,
    save_runtime_record,
    save_session_envelope,
)
from capabilities import capability_snapshot
from authority import load_authority, load_base_policy, load_runtime_policy, validate_authority
from lane_runtime import (
    CONTROLLER_CHECK_IDS,
    closure_profile,
    required_external_checks,
    select_lane_contract,
    validate_lane_closure,
    validate_lane_authority,
    validate_lane_binding,
    validate_lane_changes,
)
from run_lib import (
    ROOT,
    TERMINAL_STATES,
    ContractError,
    LockHeldError,
    MutationLock,
    RunError,
    atomic_write_json,
    atomic_write_text,
    content_manifest_hash,
    ensure_safe_parent,
    git_base_commit,
    git_repository_root,
    git_status_entries,
    git_status_paths,
    git_worktree_count,
    load_lock_owner,
    new_run_id,
    parse_utc,
    path_allowed,
    path_fingerprints,
    require_transition,
    render_run_markdown,
    run_git_env,
    symlink_component,
    unexpected_paths,
    utc_now,
    utc_after,
    validate_contract,
    validate_run_record,
)
from wiki_lib import parse_frontmatter
from semantic_protocol import (
    TIER_ORDER,
    load_base_json,
    load_json_contract,
    load_policy_bundle,
    validate_approval,
    validate_policy_snapshot,
    validate_proposal,
)


def new_record(
    run_id: str,
    wiki_id: str,
    lane: str,
    mode: str,
    authority_id: str,
    writable_paths: list[str],
    lane_contract: dict[str, Any],
    root: Path = ROOT,
    agent_provenance: dict[str, Any] | None = None,
) -> dict[str, Any]:
    now = utc_now()
    return {
        "schema_version": "rb-wiki-run-record/0.2",
        "run_id": run_id,
        "wiki_id": wiki_id,
        "lane": lane,
        "mode": mode,
        "authority_id": authority_id,
        "lane_contract": lane_contract,
        "state": "created",
        "result": None,
        "started_at": now,
        "updated_at": now,
        "finished_at": None,
        "heartbeat_at": None,
        "lease_expires_at": None,
        "base_commit": None,
        "initial_status": [],
        "initial_snapshot": [],
        "final_snapshot": [],
        "changed_paths": [],
        "writable_paths": writable_paths,
        "checks": [],
        "capabilities": capability_snapshot(root),
        "agent_provenance": validate_agent_provenance(agent_provenance, root),
        "material": False,
        "report_class": "ephemeral-telemetry",
        "durable_record": None,
        "commit_hash": None,
        "content_manifest": None,
        "transaction": None,
        "transaction_stage": None,
        "next_action": "Wait for the controller to complete preflight.",
        "error": None,
    }


def update_record(record: dict[str, Any], journal: Path, root: Path, **changes: Any) -> None:
    record.update(changes)
    record["updated_at"] = utc_now()
    save_runtime_record(record, root)


def finish_record(
    record: dict[str, Any], journal: Path, root: Path, state: str, result: str, error: str | None = None
) -> None:
    next_actions = {
        "completed": "No action required.",
        "blocked": "Resolve the reported blocker, then start a new run.",
        "failed": "Inspect the run record and recover any material changes before retrying.",
        "cancelled": "No action required unless the work should be restarted.",
        "manual-commit-required": "Review and commit the reconciled paths manually.",
        "approval-required": "Commit the proposal, record a separate approval, then start a new apply run.",
        "committed-recovery-required": "Run the authenticated recover command; do not retry the work or move the branch.",
    }
    update_record(
        record,
        journal,
        root,
        state=state,
        result=result,
        error=error,
        finished_at=utc_now(),
        next_action=next_actions.get(state, "Inspect the run record."),
    )


def persist_durable_record(record: dict[str, Any], root: Path) -> None:
    if record["lane"] == "governance":
        record["report_class"] = "durable-governance"
    elif record["state"] in {"failed", "cancelled", "committed-recovery-required"}:
        record["report_class"] = "durable-failure-recovery"
    elif record["state"] in {"manual-commit-required", "approval-required"}:
        record["report_class"] = "durable-approval"
    else:
        record["report_class"] = "durable-mutation"
    durable = root / "reports" / "runs" / f"{record['run_id']}.json"
    record["durable_record"] = durable.relative_to(root).as_posix()
    latest = {
        "schema_version": "rb-wiki-latest/0.2",
        "run_id": record["run_id"],
        "state": record["state"],
        "result": record["result"],
        "updated_at": record["updated_at"],
        "material": record["material"],
        "report_class": record["report_class"],
        "durable_record": record["durable_record"],
        "error": record["error"],
        "blockers": [record["error"]] if record["state"] in {"blocked", "failed"} and record["error"] else [],
        "overdue_actions": [],
        "capabilities": record["capabilities"],
    }
    save_durable_record(record, latest, root)


def transaction_relative_path(run_id: str) -> str:
    return f".wiki_state/transactions/{run_id}.json"


def mark_committed_recovery_required(
    record: dict[str, Any], journal: Path, root: Path, error: CommittedRecoveryRequired
) -> None:
    update_record(
        record,
        journal,
        root,
        state="committed-recovery-required",
        result="committed-recovery-required",
        finished_at=None,
        commit_hash=error.commit_hash,
        transaction=transaction_relative_path(record["run_id"]),
        transaction_stage=error.stage,
        error=str(error),
        next_action=(
            f"Run: python3 tools/wiki_run.py recover --run-id {record['run_id']} --token <run-token>"
        ),
    )


def publish_commit_receipt(root: Path, transaction: dict[str, Any]) -> dict[str, Any]:
    run_id = transaction["run_id"]
    path = root / ".wiki_state" / "receipts" / f"{run_id}.json"
    if path.exists():
        receipt = load_receipt(root, run_id)
    else:
        receipt = {
            "schema_version": "rb-wiki-commit-receipt/0.2",
            "run_id": run_id,
            "base_commit": transaction["base_commit"],
            "branch_ref": transaction["branch_ref"],
            "commit_hash": transaction["commit_hash"],
            "tree_hash": transaction["tree_hash"],
            "changed_paths": transaction["expected_paths"],
            "content_manifest": transaction["content_manifest"],
            "verified_at": utc_now(),
        }
        save_receipt(receipt, root)
    expected = {
        "run_id": run_id,
        "base_commit": transaction["base_commit"],
        "branch_ref": transaction["branch_ref"],
        "commit_hash": transaction["commit_hash"],
        "tree_hash": transaction["tree_hash"],
        "changed_paths": transaction["expected_paths"],
        "content_manifest": transaction["content_manifest"],
    }
    if any(receipt.get(key) != value for key, value in expected.items()):
        raise RunError("commit receipt does not match the Git transaction")
    return receipt


def run_maintenance(root: Path, timeout_seconds: int, full: bool = False) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["RB_WIKI_RUN_CONTROLLER"] = "1"
    command = [sys.executable, "tools/lint.py", "--full"] if full else [
        sys.executable,
        "tools/lint.py",
        "--quick",
        "--no-report",
    ]
    completed = subprocess.run(
        command,
        cwd=root,
        env=env,
        text=True,
        capture_output=True,
        check=False,
        timeout=timeout_seconds,
    )
    return completed.returncode, (completed.stdout + completed.stderr).strip()


def execute_run(
    root: Path, lane: str, mode: str, authority_id: str, *, full: bool = False
) -> tuple[int, dict[str, Any]]:
    if full and lane != "maintain":
        raise RunError("full maintenance is available only for the maintain lane")
    manifest, policy = load_runtime_policy(root)
    authority = load_authority(authority_id, root)
    validate_authority(authority, policy, lane, mode)
    selected_lane = select_lane_contract(root, lane)
    if manifest["lane_contract_version"] != selected_lane["contract"]["schema_version"]:
        raise ContractError("manifest lane_contract_version does not match the selected lane contract")
    effective_paths = validate_lane_authority(selected_lane["contract"], authority, mode)

    run_id = new_run_id()
    record = new_record(
        run_id,
        manifest["wiki_id"],
        lane,
        mode,
        authority_id,
        effective_paths,
        selected_lane["binding"],
        root,
    )
    journal = root / ".wiki_state" / "runs" / f"{run_id}.json"
    update_record(record, journal, root)
    lock = MutationLock(root, run_id, lane, mode)
    exit_code = 1
    retain_lock = False

    try:
        try:
            lock.acquire()
        except LockHeldError as exc:
            owner_note = f"; owner={exc.owner}" if exc.owner else ""
            finish_record(record, journal, root, "blocked", "blocked", f"{exc}{owner_note}")
            return 2, record

        update_record(record, journal, root, state="locked")
        if git_repository_root(root) != root.resolve():
            finish_record(
                record,
                journal,
                root,
                "blocked",
                "blocked",
                "the wiki base must be the Git worktree root for scheduled mutation in v0.2",
            )
            return 2, record
        if git_worktree_count(root) != 1:
            finish_record(
                record,
                journal,
                root,
                "blocked",
                "blocked",
                "multiple Git worktrees are unsupported for scheduled mutation in v0.2",
            )
            return 2, record

        base_commit = git_base_commit(root)
        initial_snapshot = git_status_entries(root)
        initial_status = sorted({entry["path"] for entry in initial_snapshot})
        update_record(
            record,
            journal,
            root,
            state="preflight",
            base_commit=base_commit,
            initial_status=initial_status,
            initial_snapshot=initial_snapshot,
        )
        if initial_status:
            finish_record(
                record,
                journal,
                root,
                "blocked",
                "blocked",
                "scheduled-propose requires a clean Git base; unexpected paths: " + ", ".join(initial_status),
            )
            return 2, record

        base_manifest, base_policy, base_authority = load_base_policy(base_commit, authority_id, root)
        base_lane = select_lane_contract(root, lane, base_commit)
        if base_manifest["lane_contract_version"] != base_lane["contract"]["schema_version"]:
            raise ContractError("base manifest lane_contract_version does not match the selected lane contract")
        validate_authority(base_authority, base_policy, lane, mode, datetime.now(timezone.utc))
        base_effective_paths = validate_lane_authority(base_lane["contract"], base_authority, mode)
        if full and not path_allowed("reports/lint/example.json", base_authority["writable_paths"]):
            raise ContractError("full maintenance authority must allow reports/lint/**")
        if (
            base_manifest != manifest
            or base_policy != policy
            or base_authority != authority
            or base_lane != selected_lane
        ):
            raise ContractError("working policy does not match the recorded clean base")

        heartbeat = utc_now()
        lease = utc_after(base_policy["lease_seconds"])
        update_record(
            record,
            journal,
            root,
            state="running",
            writable_paths=base_effective_paths,
            lane_contract=base_lane["binding"],
            heartbeat_at=heartbeat,
            lease_expires_at=lease,
        )
        lock.update_lease(heartbeat, lease)
        timeout_seconds = min(
            base_authority["budgets"]["max_runtime_seconds"], base_policy["limits"]["max_runtime_seconds"]
        )
        try:
            code, output = run_maintenance(root, timeout_seconds, full)
        except subprocess.TimeoutExpired as exc:
            code, output = 124, f"maintenance exceeded {timeout_seconds} seconds: {exc}"
        record["checks"].append(
            {
                "check_id": "quick-lint",
                "status": "pass" if code == 0 else "fail",
                "summary": output[-4000:] if output else "no subprocess output",
                "provenance": "controller-executed",
                "exit_code": code,
            }
        )
        final_snapshot = git_status_entries(root)
        lane_paths = sorted({entry["path"] for entry in final_snapshot})
        record["material"] = bool(lane_paths)
        update_record(
            record, journal, root, state="validating", changed_paths=lane_paths, final_snapshot=final_snapshot
        )

        validate_lane_changes(base_lane["contract"], mode, lane_paths)
        outside = unexpected_paths(lane_paths, base_effective_paths)
        too_many = len(lane_paths) > min(
            base_policy["limits"]["max_changed_files"], base_authority["budgets"]["max_changed_paths"]
        )
        if code != 0 or outside or too_many:
            reasons: list[str] = []
            if code != 0:
                reasons.append(f"{'full' if full else 'quick'} maintenance failed")
            if outside:
                reasons.append("changed paths outside authority: " + ", ".join(outside))
            if too_many:
                reasons.append("changed-file budget exceeded")
            finish_record(record, journal, root, "failed", "failed", "; ".join(reasons))
            if record["material"]:
                persist_durable_record(record, root)
                final_paths = git_status_paths(root)
                record["changed_paths"] = final_paths
                outside = unexpected_paths(final_paths, base_effective_paths)
                if outside:
                    record["error"] += "; durable closure paths outside authority: " + ", ".join(outside)
                update_record(record, journal, root)
                persist_durable_record(record, root)
            return 1, record

        if not record["material"]:
            finish_record(record, journal, root, "completed", "no-op")
            return 0, record

        if base_authority["commit_policy"] != "scoped-auto":
            finish_record(
                record,
                journal,
                root,
                "manual-commit-required",
                "manual-commit-required",
            )
            persist_durable_record(record, root)
            final_paths = git_status_paths(root)
            outside = unexpected_paths(final_paths, base_effective_paths)
            if outside:
                finish_record(
                    record,
                    journal,
                    root,
                    "failed",
                    "failed",
                    "durable closure paths outside authority: " + ", ".join(outside),
                )
                persist_durable_record(record, root)
                return 1, record
            record["changed_paths"] = final_paths
            record["content_manifest"] = content_manifest_hash(final_paths, root)
            update_record(record, journal, root)
            persist_durable_record(record, root)
            return 3, record

        finish_record(record, journal, root, "completed", "success")
        record["transaction"] = transaction_relative_path(run_id)
        record["transaction_stage"] = "prepared"
        persist_durable_record(record, root)
        commit_paths = git_status_paths(root)
        outside = unexpected_paths(commit_paths, base_effective_paths)
        if outside:
            finish_record(
                record,
                journal,
                root,
                "failed",
                "failed",
                "durable closure paths outside authority: " + ", ".join(outside),
            )
            persist_durable_record(record, root)
            return 1, record
        record["changed_paths"] = commit_paths
        record["content_manifest"] = content_manifest_hash(commit_paths, root)
        update_record(record, journal, root)
        persist_durable_record(record, root)
        commit_hash, _tree_hash = scoped_auto_commit(
            root,
            base_commit,
            commit_paths,
            run_id,
            base_authority["commit_identity"],
            record["content_manifest"],
        )
        transaction = load_transaction(root, run_id)
        record["commit_hash"] = commit_hash
        record["transaction_stage"] = transaction["stage"]
        update_record(record, journal, root)
        inject_fault("after-run-record-update")
        publish_commit_receipt(root, transaction)
        advance_git_transaction(transaction, "receipt-written", root)
        inject_fault("after-receipt-write")
        advance_git_transaction(transaction, "reconciled", root)
        record["transaction_stage"] = transaction["stage"]
        update_record(record, journal, root)
        inject_fault("before-lock-release")
        return 0, record
    except CommittedRecoveryRequired as exc:
        retain_lock = True
        mark_committed_recovery_required(record, journal, root, exc)
        return 5, record
    except (ContractError, RunError, OSError, subprocess.SubprocessError) as exc:
        try:
            transaction = load_transaction(root, run_id)
        except Exception:
            transaction = None
        if transaction is not None and transaction["stage"] in {
            "branch-moved", "index-refreshed", "receipt-written", "reconciled"
        }:
            retain_lock = True
            recovery = CommittedRecoveryRequired(
                f"commit {transaction['commit_hash']} moved {transaction['branch_ref']}; recovery is required: {exc}",
                transaction["commit_hash"],
                transaction["tree_hash"],
                transaction["stage"],
            )
            mark_committed_recovery_required(record, journal, root, recovery)
            return 5, record
        current_paths: list[str] = []
        try:
            current_paths = git_status_paths(root)
        except RunError:
            pass
        record["material"] = bool(current_paths)
        record["changed_paths"] = current_paths
        finish_record(record, journal, root, "failed", "failed", str(exc))
        if record["material"]:
            persist_durable_record(record, root)
        return 1, record
    finally:
        if lock.acquired and not retain_lock:
            try:
                lock.release()
            except RunError as exc:
                record["error"] = f"{record.get('error') or ''}; lock cleanup incomplete: {exc}".strip("; ")
                record["state"] = "failed"
                record["result"] = "failed"
                record["finished_at"] = utc_now()
                update_record(record, journal, root)
                if record["material"]:
                    persist_durable_record(record, root)
                raise RunError(str(record["error"])) from exc


def session_path(run_id: str, root: Path = ROOT) -> Path:
    if not run_id or any(character not in "0123456789TZ-abcdef" for character in run_id):
        raise RunError("invalid run ID")
    return root / ".wiki_state" / "sessions" / f"{run_id}.json"


def save_session(session: dict[str, Any], root: Path = ROOT) -> None:
    save_session_envelope(session, root)


def load_session(run_id: str, root: Path = ROOT) -> dict[str, Any]:
    return load_session_envelope(root, run_id)


def require_token(session: dict[str, Any], token: str) -> None:
    expected = session.get("run_token")
    if not isinstance(expected, str) or not secrets.compare_digest(expected, token):
        raise RunError("run token mismatch")


def allowed_initial_inputs(entries: list[dict[str, str]], input_roots: list[str], root: Path) -> bool:
    allowed_parents = {(root / item).resolve() for item in input_roots}
    for entry in entries:
        path = root / entry["path"]
        if entry["status"] != "??" or path.is_symlink() or path.parent.resolve() not in allowed_parents:
            return False
    return True


def transition_session(
    session: dict[str, Any], target: str, journal: Path, root: Path, **changes: Any
) -> None:
    record = session["record"]
    require_transition(record["state"], target)
    update_record(record, journal, root, state=target, **changes)
    save_session(session, root)


def validate_artifact_id(value: str | None, label: str) -> str:
    if not value or any(character not in "abcdefghijklmnopqrstuvwxyz0123456789-" for character in value):
        raise RunError(f"{label} must use lowercase letters, digits, and hyphens")
    return value


def start_session(
    root: Path,
    lane: str,
    mode: str,
    authority_id: str,
    proposal_id: str | None = None,
    approval_id: str | None = None,
    agent_provenance: dict[str, Any] | None = None,
) -> dict[str, Any]:
    manifest, policy = load_runtime_policy(root)
    authority = load_authority(authority_id, root)
    validate_authority(authority, policy, lane, mode)
    selected_lane = select_lane_contract(root, lane)
    if manifest["lane_contract_version"] != selected_lane["contract"]["schema_version"]:
        raise ContractError("manifest lane_contract_version does not match the selected lane contract")
    effective_paths = validate_lane_authority(selected_lane["contract"], authority, mode)
    run_id = new_run_id()
    # Prefix opaque credentials so argparse can never mistake a leading "-"
    # from token_urlsafe() for another command-line option.
    token = f"run_{secrets.token_urlsafe(32)}"
    record = new_record(
        run_id,
        manifest["wiki_id"],
        lane,
        mode,
        authority_id,
        effective_paths,
        selected_lane["binding"],
        root,
        agent_provenance,
    )
    journal = root / ".wiki_state" / "runs" / f"{run_id}.json"
    update_record(record, journal, root)
    lock = MutationLock(root, run_id, lane, mode)
    try:
        try:
            lock.acquire()
        except LockHeldError as exc:
            finish_record(record, journal, root, "blocked", "blocked", str(exc))
            raise
        require_transition(record["state"], "locked")
        update_record(record, journal, root, state="locked")
        if git_repository_root(root) != root.resolve():
            raise RunError("the wiki base must be the Git worktree root")
        if git_worktree_count(root) != 1:
            raise RunError("multiple Git worktrees are unsupported in v0.2")
        base = git_base_commit(root)
        entries = git_status_entries(root)
        paths = sorted({entry["path"] for entry in entries})
        if mode in {"scheduled-propose", "authorised-autonomous-apply"} and entries:
            if not allowed_initial_inputs(entries, authority["input_roots"], root):
                raise RunError("dirty base contains paths outside declared direct untracked inputs")
        base_manifest, base_policy, base_authority = load_base_policy(base, authority_id, root)
        base_lane = select_lane_contract(root, lane, base)
        if base_manifest["lane_contract_version"] != base_lane["contract"]["schema_version"]:
            raise ContractError("base manifest lane_contract_version does not match the selected lane contract")
        if mode in {"scheduled-propose", "authorised-autonomous-apply"}:
            if (base_manifest, base_policy, base_authority, base_lane) != (
                manifest,
                policy,
                authority,
                selected_lane,
            ):
                raise ContractError("working authority or manifest does not match the clean base")
        validate_authority(base_authority, base_policy, lane, mode)
        base_effective_paths = validate_lane_authority(base_lane["contract"], base_authority, mode)
        semantic_context: dict[str, Any] = {}
        if closure_profile(base_lane["contract"], mode) == "autonomous-semantic-apply":
            proposal_id = validate_artifact_id(proposal_id, "proposal ID")
            consequence, domain = load_policy_bundle(root, base)
            proposal = load_base_json(
                base,
                f"reports/proposals/{proposal_id}.json",
                "synthesis-proposal",
                root,
                expected_identity=("proposal_id", proposal_id),
            )
            validate_proposal(proposal, root, consequence=consequence, domain=domain)
            validate_policy_snapshot(proposal, base_policy, consequence, root)
            if TIER_ORDER[proposal["consequence_tier"]] > TIER_ORDER[base_authority["consequence_tier"]]:
                raise ContractError("proposal consequence tier exceeds authority maximum")
            approval = None
            if proposal["consequence_tier"] == "high-consequence":
                approval_id = validate_artifact_id(approval_id, "approval ID")
                approval = load_base_json(
                    base,
                    f"reports/approvals/{approval_id}.json",
                    "approval-record",
                    root,
                    expected_identity=("approval_id", approval_id),
                )
                validate_approval(approval, proposal, consequence, domain, root=root)
            elif approval_id is not None:
                raise RunError("approval ID is accepted only for high-consequence apply")
            semantic_context = {
                "proposal": proposal,
                "approval": approval,
                "consequence_policy": consequence,
                "domain_policy": domain,
            }
        record["wiki_id"] = base_manifest["wiki_id"]
        record["writable_paths"] = base_effective_paths
        record["lane_contract"] = base_lane["binding"]
        now = datetime.now(timezone.utc)
        require_transition(record["state"], "preflight")
        update_record(
            record,
            journal,
            root,
            state="preflight",
            base_commit=base,
            initial_status=paths,
            initial_snapshot=entries,
        )
        require_transition(record["state"], "running")
        update_record(
            record,
            journal,
            root,
            state="running",
            heartbeat_at=utc_now(),
            lease_expires_at=utc_after(base_policy["lease_seconds"], now),
            next_action="Perform only the actions and paths in the run envelope; heartbeat every 60 seconds.",
        )
        session = {
            "schema_version": "rb-wiki-session/0.2",
            "record": record,
            "run_token": token,
            "authority": base_authority,
            "policy": base_policy,
            "lane_contract": base_lane["binding"],
            "initial_entries": entries,
            "initial_fingerprints": path_fingerprints(paths, root),
            "initial_raw_fingerprints": path_fingerprints(
                sorted(
                    path.relative_to(root).as_posix()
                    for path in enumerate_regular_files(root, "sources/raw")
                ),
                root,
            ),
            "semantic_context": semantic_context,
            "proposal_id": proposal_id,
            "approval_id": approval_id,
        }
        lock.update_lease(record["heartbeat_at"], record["lease_expires_at"])
        save_session(session, root)
        envelope = {
            "schema_version": "rb-wiki-run-envelope/0.2",
            "run_id": run_id,
            "run_token": token,
            "lane": lane,
            "mode": mode,
            "permitted_actions": base_authority["actions"],
            "input_roots": base_authority["input_roots"],
            "writable_paths": base_effective_paths,
            "page_types": base_authority["page_types"],
            "required_checks": required_external_checks(base_lane["contract"], base_authority, mode),
            "lane_contract": base_lane["binding"],
            "consequence_tier": base_authority["consequence_tier"],
            "expires_at": base_authority["expires_at"],
            "lease_expires_at": record["lease_expires_at"],
            "stop_conditions": {
                "budgets": base_authority["budgets"],
                "validation_failure": True,
                "authority_expiry": base_authority["expires_at"],
            },
            "commit_policy": base_authority["commit_policy"],
            "proposal_id": proposal_id,
            "approval_id": approval_id,
            "capabilities": record["capabilities"],
            "capability_digest": record["capabilities"]["digest_sha256"],
            "agent_provenance": record["agent_provenance"],
            "artifact_handoffs": {
                "proposal": f"reports/proposals/{proposal_id}.json" if proposal_id else None,
                "approval": f"reports/approvals/{approval_id}.json" if approval_id else None,
            },
        }
        validate_contract(envelope, "run-envelope", root)
        return envelope
    except LockHeldError:
        lock.release()
        raise
    except Exception as exc:
        finish_record(record, journal, root, "failed", "failed", str(exc))
        lock.release()
        raise


def heartbeat_session(root: Path, run_id: str, token: str, now: datetime | None = None) -> dict[str, Any]:
    session = load_session(run_id, root)
    require_token(session, token)
    record = session["record"]
    if record["state"] != "running":
        raise RunError(f"cannot heartbeat a run in state {record['state']}")
    current = now or datetime.now(timezone.utc)
    record["heartbeat_at"] = current.replace(microsecond=0).isoformat().replace("+00:00", "Z")
    record["lease_expires_at"] = utc_after(session["policy"]["lease_seconds"], current)
    journal = root / ".wiki_state" / "runs" / f"{run_id}.json"
    update_record(record, journal, root)
    MutationLock.update_owned_lease(root, run_id, record["heartbeat_at"], record["lease_expires_at"])
    save_session(session, root)
    return {"run_id": run_id, "state": record["state"], "lease_expires_at": record["lease_expires_at"]}


def status_session(root: Path, run_id: str, now: datetime | None = None) -> dict[str, Any]:
    session = load_session(run_id, root)
    record = dict(session["record"])
    current = now or datetime.now(timezone.utc)
    lease = parse_utc(record["lease_expires_at"]) if record.get("lease_expires_at") else None
    record["lease_stale"] = bool(lease and current >= lease and record["state"] == "running")
    return record


def parse_checks(values: list[str], root: Path | None = None) -> list[dict[str, Any]]:
    if len(values) > 64:
        raise RunError("at most 64 external checks may be reported")
    checks: list[dict[str, Any]] = []
    seen: set[str] = set()
    for value in values:
        if "=" not in value:
            raise RunError("checks must use CHECK_ID=pass|warn|fail[@reports/LOCAL_ARTIFACT]")
        check_id, status_and_evidence = value.split("=", 1)
        status, separator, evidence_ref = status_and_evidence.partition("@")
        if re.fullmatch(r"[a-z0-9][a-z0-9-]{1,62}", check_id) is None:
            raise RunError(f"invalid check ID: {check_id or '<empty>'}")
        if check_id in seen:
            raise RunError(f"duplicate check ID: {check_id}")
        if check_id in CONTROLLER_CHECK_IDS:
            raise RunError(f"external agent may not report controller-owned check: {check_id}")
        if status not in {"pass", "warn", "fail"}:
            raise RunError(f"invalid check status: {status}")
        if separator:
            evidence_ref = validate_check_evidence_reference(evidence_ref, root)
        seen.add(check_id)
        check = {
            "check_id": check_id,
            "status": status,
            "summary": "reported by external agent",
            "provenance": "external-attestation",
        }
        if separator:
            check["evidence_ref"] = evidence_ref
        checks.append(check)
    return checks


def enforce_page_scope(paths: list[str], allowed_types: list[str], root: Path) -> None:
    for relative in paths:
        if not relative.startswith("wiki/") or relative in {"wiki/index.md", "wiki/log.md"}:
            continue
        path = root / relative
        if not path.exists():
            raise RunError(f"substantive page deletion is not authorised in Phase 2: {relative}")
        frontmatter, _body, error = parse_frontmatter(path)
        if error or frontmatter.get("type") not in allowed_types:
            raise RunError(f"page-type scope violation: {relative}")


def validate_runtime_session_against_base(
    session: dict[str, Any], root: Path, now: datetime
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Reload committed authority and semantic handoffs before trusting closure state."""
    record = session["record"]
    manifest, policy, authority = load_base_policy(record["base_commit"], record["authority_id"], root)
    if manifest["wiki_id"] != record["wiki_id"]:
        raise RunError("runtime session wiki identity differs from the recorded base")
    if session.get("policy") != policy or session.get("authority") != authority:
        raise RunError("runtime session authority or policy differs from the recorded base")
    validate_authority(authority, policy, record["lane"], record["mode"], now)
    selected_lane = select_lane_contract(root, record["lane"], record["base_commit"])
    if manifest["lane_contract_version"] != selected_lane["contract"]["schema_version"]:
        raise RunError("runtime lane contract version differs from the recorded base manifest")
    validate_lane_binding(record["lane_contract"], selected_lane)
    if session.get("lane_contract") != selected_lane["binding"]:
        raise RunError("runtime session lane contract differs from the recorded base")
    effective_paths = validate_lane_authority(selected_lane["contract"], authority, record["mode"])
    if record["writable_paths"] != effective_paths:
        raise RunError("runtime session writable paths differ from the lane-bounded base authority")

    if closure_profile(selected_lane["contract"], record["mode"]) == "autonomous-semantic-apply":
        proposal_id = validate_artifact_id(session.get("proposal_id"), "proposal ID")
        consequence, domain = load_policy_bundle(root, record["base_commit"])
        proposal = load_base_json(
            record["base_commit"],
            f"reports/proposals/{proposal_id}.json",
            "synthesis-proposal",
            root,
            expected_identity=("proposal_id", proposal_id),
        )
        validate_proposal(proposal, root, consequence=consequence, domain=domain)
        validate_policy_snapshot(proposal, policy, consequence, root)
        if TIER_ORDER[proposal["consequence_tier"]] > TIER_ORDER[authority["consequence_tier"]]:
            raise ContractError("proposal consequence tier exceeds authority maximum")
        approval = None
        if proposal["consequence_tier"] == "high-consequence":
            approval_id = validate_artifact_id(session.get("approval_id"), "approval ID")
            approval = load_base_json(
                record["base_commit"],
                f"reports/approvals/{approval_id}.json",
                "approval-record",
                root,
                expected_identity=("approval_id", approval_id),
            )
            validate_approval(approval, proposal, consequence, domain, now=now, root=root)
        expected_context = {
            "proposal": proposal,
            "approval": approval,
            "consequence_policy": consequence,
            "domain_policy": domain,
        }
        if session.get("semantic_context") != expected_context:
            raise RunError("runtime semantic context differs from the recorded base artifacts")
        session["semantic_context"] = expected_context
    return authority, policy, selected_lane["contract"]


def validate_declared_input_snapshots(session: dict[str, Any], root: Path) -> None:
    """Keep direct untracked inputs content-immutable, allowing only validated ingest archival."""
    record = session["record"]
    authority = session["authority"]
    declared = sorted(
        path
        for path in record["initial_status"]
        if any(PurePosixPath(path).parent.as_posix() == item for item in authority["input_roots"])
    )
    if not declared:
        return
    current = path_fingerprints(declared, root)
    journals: list[dict[str, Any]] = []
    sources_state = root / ".wiki_state" / "sources"
    if record["lane"] == "ingest" and (sources_state.exists() or sources_state.is_symlink()):
        for path in enumerate_regular_files(root, ".wiki_state/sources", ".json"):
            try:
                source_record = json.loads(path.read_text(encoding="utf-8"))
                validate_contract(source_record, "source-transition", root)
            except (OSError, json.JSONDecodeError, ContractError):
                continue
            if source_record.get("parent_run_id") == record["run_id"]:
                journals.append(source_record)
    for relative in declared:
        expected = session["initial_fingerprints"][relative]
        if current[relative] == expected:
            continue
        archived = False
        if record["lane"] == "ingest" and current[relative] == "missing":
            for source_record in journals:
                if (
                    source_record.get("input_path") == relative
                    and source_record.get("digest") == expected
                    and source_record.get("outcome") == "complete"
                    and "inbox-archived" in source_record.get("completed_transitions", [])
                ):
                    processed = source_record.get("processed_path")
                    if isinstance(processed, str):
                        archived = path_fingerprints([processed], root).get(processed) == expected
                    break
        if not archived:
            raise RunError(f"declared input content changed after snapshot: {relative}")


def finish_session(root: Path, run_id: str, token: str, check_values: list[str]) -> tuple[int, dict[str, Any]]:
    session = load_session(run_id, root)
    require_token(session, token)
    checks = parse_checks(check_values, root)
    record = session["record"]
    journal = root / ".wiki_state" / "runs" / f"{run_id}.json"
    if git_base_commit(root) != record["base_commit"]:
        raise RunError("HEAD changed since run start")
    authority, policy, lane_contract = validate_runtime_session_against_base(
        session, root, datetime.now(timezone.utc)
    )
    validate_declared_input_snapshots(session, root)
    transition_session(session, "validating", journal, root)
    final_entries = git_status_entries(root)
    final_paths = sorted({entry["path"] for entry in final_entries})
    record["final_snapshot"] = final_entries
    initial_paths = set(record["initial_status"])
    changed = sorted(set(final_paths).difference(initial_paths))
    final_initial_fingerprints = path_fingerprints(sorted(initial_paths), root)
    declared_inputs = {
        path
        for path in initial_paths
        if any(PurePosixPath(path).parent.as_posix() == input_root for input_root in authority["input_roots"])
    }
    overlap = sorted(
        path
        for path in initial_paths
        if path not in declared_inputs
        and final_initial_fingerprints.get(path) != session["initial_fingerprints"].get(path)
    )
    if overlap:
        raise RunError("run changed protected initial paths: " + ", ".join(overlap))
    raw_before = session.get("initial_raw_fingerprints", {})
    raw_after = path_fingerprints(sorted(raw_before), root)
    raw_changed = sorted(path for path in raw_before if raw_after.get(path) != raw_before[path])
    if raw_changed:
        raise RunError("pre-existing raw evidence is not append-only: " + ", ".join(raw_changed))
    for relative in final_paths:
        candidate = root / relative
        if candidate.is_symlink() or not candidate.resolve().is_relative_to(root.resolve()):
            raise RunError(f"unsafe changed path or resolved escape: {relative}")
    validate_lane_changes(lane_contract, record["mode"], changed)
    outside = unexpected_paths(changed, record["writable_paths"])
    if outside:
        raise RunError("changed paths outside authority: " + ", ".join(outside))
    governance = [
        path for path in changed if path == "wiki-manifest.yml" or path.startswith(("schema/", "tools/"))
    ]
    if governance and not authority["governance_maintenance"]:
        raise RunError("governance-maintenance scope is required for: " + ", ".join(governance))
    enforce_page_scope(changed, authority["page_types"], root)
    semantic_proposal, approval_required = validate_lane_closure(
        lane_contract, record["mode"], root, run_id, changed, policy, authority, session
    )
    reported = {check["check_id"]: check["status"] for check in checks}
    missing = sorted(
        check
        for check in required_external_checks(lane_contract, authority, record["mode"])
        if check not in reported
    )
    if missing:
        raise RunError("required checks were not reported: " + ", ".join(missing))
    if any(status == "fail" for status in reported.values()):
        raise RunError("validation failure prevents closure")
    if semantic_proposal is not None:
        controller_checks = ["semantic-output"]
        if semantic_proposal.get("apply_payload") is not None:
            controller_checks.append("proposal-payload")
        if record["mode"] == "authorised-autonomous-apply" and semantic_proposal["consequence_tier"] == "high-consequence":
            controller_checks.append("approval-binding")
        for check_id in controller_checks:
            checks.append(
                {
                    "check_id": check_id,
                    "status": "pass",
                    "summary": "validated by run controller",
                    "provenance": "controller-executed",
                }
            )
    required_controller = set(lane_contract["required_checks_by_mode"][record["mode"]]).intersection(
        CONTROLLER_CHECK_IDS
    )
    performed_controller = {
        check["check_id"] for check in checks if check.get("provenance") == "controller-executed"
    }
    if "provenance" in required_controller and "provenance" not in performed_controller:
        from provenance import validate_provenance

        provenance_errors = validate_provenance(root=root, contract_root=root)
        if provenance_errors:
            raise RunError("provenance validation failed: " + "; ".join(provenance_errors))
        checks.append(
            {
                "check_id": "provenance",
                "status": "pass",
                "summary": "validated by run controller",
                "provenance": "controller-executed",
            }
        )
        performed_controller.add("provenance")
    missing_controller = sorted(required_controller.difference(performed_controller))
    if missing_controller:
        raise RunError("lane controller checks were not performed: " + ", ".join(missing_controller))
    if semantic_proposal is not None and record["mode"] == "authorised-autonomous-apply":
        consequence = session["semantic_context"]["consequence_policy"]
        required = set(consequence["tiers"][semantic_proposal["consequence_tier"]]["required_checks"])
        performed = {item["check_id"] for item in checks} | set(semantic_proposal["checks_performed"])
        missing_policy_checks = sorted(required.difference(performed))
        if missing_policy_checks:
            raise RunError("consequence policy checks were not performed: " + ", ".join(missing_policy_checks))
    if len(changed) > authority["budgets"]["max_changed_paths"]:
        raise RunError("changed-path budget exhausted")
    acquired = [path for path in changed if path.startswith("sources/raw/")]
    if len(acquired) > authority["budgets"]["max_acquired_sources"]:
        raise RunError("acquired-source budget exhausted")
    if acquired:
        from source_registry import load_registry_document

        acquired_set = set(acquired)
        preservation_only = [
            entry["source_id"]
            for entry in load_registry_document(root / "sources" / "_source_registry.yml", root)["sources"]
            if entry["raw_path"] in acquired_set and entry["access_level"] == "preservation-only"
        ]
        if preservation_only and "preserve-unsupported" not in authority["actions"]:
            raise RunError(
                "preservation-only sources require preserve-unsupported authority: "
                + ", ".join(preservation_only)
            )
    elapsed = (datetime.now(timezone.utc) - parse_utc(record["started_at"])).total_seconds()
    if elapsed > authority["budgets"]["max_runtime_seconds"]:
        raise RunError("maximum runtime budget exhausted")
    record["checks"] = checks
    record["changed_paths"] = changed
    record["material"] = bool(changed)
    if not changed:
        finish_record(record, journal, root, "completed", "no-op")
        save_session(session, root)
        MutationLock.release_owned(root, run_id)
        return 0, record
    record["content_manifest"] = content_manifest_hash(changed, root)
    if approval_required:
        finish_record(record, journal, root, "approval-required", "approval-required")
        persist_durable_record(record, root)
        reconciled = git_status_paths(root)
        outside = unexpected_paths(sorted(set(reconciled).difference(initial_paths)), record["writable_paths"])
        if outside:
            raise RunError("approval closure paths outside authority: " + ", ".join(outside))
        record["changed_paths"] = sorted(set(reconciled).difference(initial_paths))
        persist_durable_record(record, root)
        update_record(record, journal, root)
        save_session(session, root)
        MutationLock.release_owned(root, run_id)
        return 4, record
    if authority["commit_policy"] != "scoped-auto":
        finish_record(record, journal, root, "manual-commit-required", "manual-commit-required")
        persist_durable_record(record, root)
        reconciled = git_status_paths(root)
        outside = unexpected_paths(sorted(set(reconciled).difference(initial_paths)), record["writable_paths"])
        if outside:
            raise RunError("closure report paths outside authority: " + ", ".join(outside))
        record["changed_paths"] = sorted(set(reconciled).difference(initial_paths))
        persist_durable_record(record, root)
        update_record(record, journal, root)
        save_session(session, root)
        MutationLock.release_owned(root, run_id)
        return 3, record
    completion_time = utc_now()
    record.update(
        state="completed",
        result="success",
        finished_at=completion_time,
        updated_at=completion_time,
        next_action="No action required.",
        error=None,
    )
    record["transaction"] = transaction_relative_path(run_id)
    record["transaction_stage"] = "prepared"
    persist_durable_record(record, root)
    commit_paths = git_status_paths(root)
    outside = unexpected_paths(commit_paths, record["writable_paths"])
    if outside:
        raise RunError("pre-commit report introduced paths outside authority: " + ", ".join(outside))
    record["changed_paths"] = commit_paths
    record["content_manifest"] = content_manifest_hash(commit_paths, root)
    persist_durable_record(record, root)
    try:
        commit_hash, _tree_hash = scoped_auto_commit(
            root,
            record["base_commit"],
            commit_paths,
            run_id,
            authority["commit_identity"],
            record["content_manifest"],
        )
        transaction = load_transaction(root, run_id)
        record["commit_hash"] = commit_hash
        record["transaction_stage"] = transaction["stage"]
        update_record(record, journal, root)
        inject_fault("after-run-record-update")
        publish_commit_receipt(root, transaction)
        advance_git_transaction(transaction, "receipt-written", root)
        record["transaction_stage"] = transaction["stage"]
        update_record(record, journal, root)
        inject_fault("after-receipt-write")
        save_session(session, root)
        inject_fault("after-session-save")
        advance_git_transaction(transaction, "reconciled", root)
        record["transaction_stage"] = transaction["stage"]
        update_record(record, journal, root)
        save_session(session, root)
        inject_fault("before-lock-release")
        MutationLock.release_owned(root, run_id)
        return 0, record
    except CommittedRecoveryRequired as exc:
        mark_committed_recovery_required(record, journal, root, exc)
        save_session(session, root)
        return 5, record
    except Exception as exc:
        try:
            transaction = load_transaction(root, run_id)
        except Exception:
            raise exc
        if transaction["stage"] not in {"branch-moved", "index-refreshed", "receipt-written", "reconciled"}:
            raise exc
        recovery = CommittedRecoveryRequired(
            f"commit {transaction['commit_hash']} moved {transaction['branch_ref']}; recovery is required: {exc}",
            transaction["commit_hash"],
            transaction["tree_hash"],
            transaction["stage"],
        )
        mark_committed_recovery_required(record, journal, root, recovery)
        save_session(session, root)
        return 5, record


def terminate_session(root: Path, run_id: str, token: str, target: str, reason: str) -> dict[str, Any]:
    session = load_session(run_id, root)
    require_token(session, token)
    record = session["record"]
    if record["state"] == "committed-recovery-required":
        raise RunError("a committed recovery run cannot be terminated; recover or record an audited resolution")
    if record["state"] in TERMINAL_STATES:
        raise RunError(f"run is already terminal in state {record['state']}")
    journal = root / ".wiki_state" / "runs" / f"{run_id}.json"
    current_paths = git_status_paths(root)
    record["final_snapshot"] = git_status_entries(root)
    record["changed_paths"] = sorted(set(current_paths).difference(record["initial_status"]))
    record["material"] = bool(record["changed_paths"])
    result = "cancelled" if target == "cancelled" else "failed"
    finish_record(record, journal, root, target, result, reason)
    if record["material"]:
        persist_durable_record(record, root)
        reconciled = git_status_paths(root)
        record["changed_paths"] = sorted(set(reconciled).difference(record["initial_status"]))
        persist_durable_record(record, root)
        update_record(record, journal, root)
    save_session(session, root)
    MutationLock.release_owned(root, run_id)
    return record


def recover_run(
    root: Path, run_id: str, *, token: str | None = None, authority_id: str | None = None
) -> tuple[int, dict[str, Any]]:
    """Idempotently finish bookkeeping for a branch-moved transaction."""
    runtime_session_path = session_path(run_id, root)
    session: dict[str, Any] | None
    if runtime_session_path.exists():
        if token is None:
            raise RunError("session recovery requires the original run token")
        session = load_session(run_id, root)
        require_token(session, token)
        record = session["record"]
    else:
        if authority_id is None:
            raise RunError("controller-run recovery requires --authority")
        session = None
        record = load_json_contract(
            root / ".wiki_state" / "runs" / f"{run_id}.json", "run-record", root
        )
        if record.get("authority_id") != authority_id:
            raise RunError("recovery authority does not own the original run")
        _manifest, base_policy, base_authority = load_base_policy(
            record["base_commit"], authority_id, root
        )
        validate_authority(
            base_authority, base_policy, record["lane"], record["mode"], datetime.now(timezone.utc)
        )
        if base_authority.get("commit_policy") != "scoped-auto":
            raise RunError("recovery authority is not permitted to reconcile scoped commits")
    if record["state"] not in {"committed-recovery-required", "completed"}:
        raise RunError(f"run is not eligible for committed recovery: {record['state']}")
    transaction = load_transaction(root, run_id)
    if record.get("transaction") != transaction_relative_path(run_id):
        raise RunError("run record is not bound to the recovery transaction")
    if record.get("base_commit") != transaction["base_commit"]:
        raise RunError("run record base does not match the recovery transaction")
    if record.get("commit_hash") != transaction["commit_hash"]:
        raise RunError("run record commit does not match the recovery transaction")
    if record.get("content_manifest") != transaction["content_manifest"]:
        raise RunError("run record content manifest does not match the recovery transaction")
    if transaction["stage"] == "commit-created":
        discover_branch_movement(root, transaction)
    if transaction["stage"] not in {"branch-moved", "index-refreshed", "receipt-written", "reconciled"}:
        raise RunError(f"transaction has no durable branch-movement evidence: {transaction['stage']}")
    refresh_index_for_recovery(root, transaction)
    transaction = load_transaction(root, run_id)
    verify_recovery_evidence(root, transaction)
    publish_commit_receipt(root, transaction)
    if transaction["stage"] == "index-refreshed":
        advance_git_transaction(transaction, "receipt-written", root)
    journal = root / ".wiki_state" / "runs" / f"{run_id}.json"
    update_record(
        record,
        journal,
        root,
        state="completed",
        result="success",
        finished_at=record.get("finished_at") or utc_now(),
        commit_hash=transaction["commit_hash"],
        transaction_stage=transaction["stage"],
        error=None,
        next_action="No action required.",
    )
    if session is not None:
        save_session(session, root)
    if transaction["stage"] == "receipt-written":
        advance_git_transaction(transaction, "reconciled", root)
        update_record(record, journal, root, transaction_stage="reconciled")
        if session is not None:
            save_session(session, root)
    lock_dir = root / ".wiki_state" / "mutation.lock"
    if lock_dir.exists():
        MutationLock.release_owned(root, run_id)
    return 0, record


def recover_session(root: Path, run_id: str, token: str) -> tuple[int, dict[str, Any]]:
    return recover_run(root, run_id, token=token)


def process_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except (ProcessLookupError, ValueError, OverflowError):
        return False
    except PermissionError:
        return True
    return True


def break_lock(root: Path, authority_id: str, actor: str, reason: str) -> dict[str, Any]:
    if not actor.strip() or not reason.strip() or len(actor) > 256 or len(reason) > 2000:
        raise RunError("break-lock requires non-empty actor and reason")
    base = git_base_commit(root)
    manifest, policy, authority = load_base_policy(base, authority_id, root)
    if not authority["governance_maintenance"] or "governance-maintenance" not in authority["actions"]:
        raise RunError("break-lock requires governance-maintenance authority")
    validate_authority(authority, policy, "governance", "manual-assist")
    selected_lane = select_lane_contract(root, "governance", base)
    if manifest["lane_contract_version"] != selected_lane["contract"]["schema_version"]:
        raise ContractError("base manifest lane_contract_version does not match governance contract")
    effective_paths = validate_lane_authority(selected_lane["contract"], authority, "manual-assist")
    lock_dir = root / ".wiki_state" / "mutation.lock"
    unsafe_lock = symlink_component(lock_dir, root)
    if unsafe_lock is not None:
        raise RunError(f"break-lock refuses a symlinked lock path: {unsafe_lock}")
    owner_path = lock_dir / "owner.json"
    try:
        owner = load_lock_owner(owner_path, root)
    except (OSError, ContractError) as exc:
        raise RunError("break-lock requires readable owner metadata") from exc
    if owner.get("host") != socket.gethostname():
        raise RunError("cannot verify process liveness for a lock owned by another host")
    pid = owner.get("pid")
    if not isinstance(pid, int):
        raise RunError("lock owner has no valid process ID")
    if process_alive(pid):
        raise RunError("refusing to break a lock whose same-host owner process is alive")
    existing_run = owner.get("run_id")
    if isinstance(existing_run, str):
        try:
            existing = status_session(root, existing_run)
        except RunError:
            existing = None
        if existing and existing["state"] == "running" and not existing["lease_stale"]:
            raise RunError("refusing to break an active session before its lease expires")

    initial_snapshot = git_status_entries(root)
    initial_paths = sorted({entry["path"] for entry in initial_snapshot})
    audit_id = new_run_id()
    record = new_record(
        audit_id,
        manifest["wiki_id"],
        "governance",
        "manual-assist",
        authority_id,
        effective_paths,
        selected_lane["binding"],
        root,
    )
    observed_owner = {
        key: owner.get(key)
        for key in (
            "schema_version", "run_id", "pid", "host", "lane", "mode",
            "acquired_at", "heartbeat_at", "lease_expires_at",
        )
        if key in owner
    }
    record.update(
        state="running",
        result=None,
        base_commit=base,
        material=True,
        next_action="Lock displacement is pending; do not treat this audit as complete.",
        checks=[
            {
                "check_id": "break-lock",
                "status": "pass",
                "summary": f"authorised actor={actor}; reason={reason}; observed_owner={json.dumps(observed_owner, sort_keys=True)}",
                "provenance": "controller-executed",
            }
        ],
        initial_status=initial_paths,
        initial_snapshot=initial_snapshot,
    )
    journal = root / ".wiki_state" / "runs" / f"{audit_id}.json"
    persist_durable_record(record, root)
    update_record(record, journal, root)
    destination = root / ".wiki_state" / "broken-locks" / audit_id
    ensure_safe_parent(destination / "owner.json", root)
    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.replace(lock_dir, destination)
    except OSError as exc:
        finish_record(record, journal, root, "failed", "failed", f"lock displacement failed: {exc}")
        record["final_snapshot"] = git_status_entries(root)
        record["changed_paths"] = sorted(
            {entry["path"] for entry in record["final_snapshot"]}.difference(initial_paths)
        )
        persist_durable_record(record, root)
        raise RunError(f"lock displacement failed; original lock remains in place: {exc}") from exc
    record.update(
        state="completed",
        result="success",
        finished_at=utc_now(),
        next_action="Review the displaced lock evidence and recover the interrupted run.",
    )
    record["final_snapshot"] = git_status_entries(root)
    record["changed_paths"] = sorted(
        {entry["path"] for entry in record["final_snapshot"]}.difference(initial_paths)
    )
    persist_durable_record(record, root)
    update_record(record, journal, root)
    return record


def record_resolution(
    root: Path, run_id: str, authority_id: str, actor: str, reason: str, commit_hash: str | None
) -> dict[str, Any]:
    if not actor.strip() or len(actor) > 256 or not reason.strip() or len(reason) > 2000:
        raise RunError("resolution actor/reason must be non-empty and within contract limits")
    session_path(run_id, root)  # validates the identifier without requiring a live session
    if commit_hash is not None and (len(commit_hash) not in {40, 64} or any(c not in "0123456789abcdef" for c in commit_hash)):
        raise RunError("invalid resolution commit hash")
    base = git_base_commit(root)
    _manifest, policy, authority = load_base_policy(base, authority_id, root)
    if "manual-assist" not in authority["modes"]:
        raise RunError("resolution acknowledgement requires manual-assist authority")
    validate_authority(authority, policy, authority["lanes"][0], "manual-assist")
    if not path_allowed("reports/resolutions/example.json", authority["writable_paths"]):
        raise RunError("authority does not permit resolution records")
    original_path = root / ".wiki_state" / "runs" / f"{run_id}.json"
    unsafe_original = symlink_component(original_path, root)
    if unsafe_original is not None:
        raise RunError(f"original run path traverses a symlink: {unsafe_original}")
    if not original_path.is_file():
        original_path = root / "reports" / "runs" / f"{run_id}.json"
    try:
        original = load_json_contract(original_path, "run-record", root)
    except (ContractError, OSError) as exc:
        raise RunError(f"cannot load original run {run_id}") from exc
    if original.get("state") not in {
        "manual-commit-required", "approval-required", "committed-recovery-required", "failed", "cancelled"
    }:
        raise RunError("resolution records may link only to a terminal run needing acknowledgement")
    if original["state"] == "committed-recovery-required":
        if commit_hash is None or commit_hash != original.get("commit_hash"):
            raise RunError("committed recovery resolution must name the exact recorded commit")
    commit_classification = "none"
    if commit_hash is not None:
        object_type = run_git_env(root, ["cat-file", "-t", commit_hash], {}, check=False)
        if object_type.returncode != 0 or object_type.stdout.strip() != "commit":
            raise RunError("resolution commit hash must name an existing commit object")
        ancestry = run_git_env(
            root, ["merge-base", "--is-ancestor", original["base_commit"], commit_hash], {}, check=False
        )
        if ancestry.returncode != 0:
            raise RunError("resolution commit is unrelated to the original run base")
        message = run_git_env(root, ["show", "-s", "--format=%B", commit_hash], {}).stdout
        trailers = [line.strip() for line in message.splitlines() if line.startswith("RB-Wiki-Run:")]
        if trailers and trailers != [f"RB-Wiki-Run: {run_id}"]:
            raise RunError("resolution commit claims another or ambiguous managed run")
        if original.get("commit_hash") is not None:
            if commit_hash != original["commit_hash"]:
                raise RunError("resolution commit differs from the commit recorded by the run")
            transaction = load_transaction(root, run_id)
            verify_recovery_evidence(root, transaction)
            commit_classification = "managed-reconciled"
        else:
            committed_paths = sorted(
                path for path in run_git_env(
                    root,
                    ["diff", "--name-only", original["base_commit"], commit_hash],
                    {},
                ).stdout.splitlines() if path
            )
            expected_paths = sorted(original.get("changed_paths", []))
            if expected_paths and not set(expected_paths).issubset(committed_paths):
                raise RunError("resolution commit does not contain the original changed paths")
            commit_classification = "human-acknowledgement"
    resolution = {
        "schema_version": "rb-wiki-resolution/0.2",
        "resolution_id": new_run_id(),
        "run_id": run_id,
        "authority_id": authority_id,
        "actor": actor,
        "reason": reason,
        "commit_hash": commit_hash,
        "commit_classification": commit_classification,
        "recorded_at": utc_now(),
        "original_state": original["state"],
    }
    validate_contract(resolution, "resolution-record", root)
    atomic_write_json(
        root / "reports" / "resolutions" / f"{resolution['resolution_id']}.json", resolution, root
    )
    return resolution


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run a policy-authorised RB Wiki lane")
    subparsers = parser.add_subparsers(dest="command", required=True)
    run = subparsers.add_parser("run", help="execute a managed lane")
    run.add_argument("--lane", choices=["maintain"], required=True)
    run.add_argument("--mode", choices=["scheduled-propose"], required=True)
    run.add_argument("--authority", required=True)
    run.add_argument("--full", action="store_true", help="run full lint and persist its typed report")
    start = subparsers.add_parser("start", help="start a persistent external-agent session")
    start.add_argument(
        "--lane", choices=["maintain", "acquire", "ingest", "synthesize", "semantic", "governance"], required=True
    )
    start.add_argument(
        "--mode", choices=["manual-assist", "scheduled-propose", "authorised-autonomous-apply"], required=True
    )
    start.add_argument("--authority", required=True)
    start.add_argument("--proposal-id")
    start.add_argument("--approval-id")
    start.add_argument("--agent-label")
    start.add_argument("--runtime")
    start.add_argument("--provider-model")
    start.add_argument("--prompt-policy-digest")
    start.add_argument("--trace-reference")
    heartbeat = subparsers.add_parser("heartbeat", help="renew a session lease")
    heartbeat.add_argument("--run-id", required=True)
    heartbeat.add_argument("--token", required=True)
    status = subparsers.add_parser("status", help="inspect a session without exposing its token")
    status.add_argument("--run-id", required=True)
    finish = subparsers.add_parser("finish", help="validate and close a session")
    finish.add_argument("--run-id", required=True)
    finish.add_argument("--token", required=True)
    finish.add_argument(
        "--check",
        action="append",
        default=[],
        metavar="ID=STATUS[@reports/PATH]",
        help="report an external attestation with an optional bounded local evidence reference",
    )
    recover = subparsers.add_parser("recover", help="reconcile a branch-moved scoped commit")
    recover.add_argument("--run-id", required=True)
    recovery_auth = recover.add_mutually_exclusive_group(required=True)
    recovery_auth.add_argument("--token")
    recovery_auth.add_argument("--authority")
    for name in ("cancel", "fail"):
        terminal = subparsers.add_parser(name, help=f"{name} a running session")
        terminal.add_argument("--run-id", required=True)
        terminal.add_argument("--token", required=True)
        terminal.add_argument("--reason", required=True)
    breaker = subparsers.add_parser("break-lock", help="explicitly recover a dead same-host lock")
    breaker.add_argument("--authority", required=True)
    breaker.add_argument("--actor", required=True)
    breaker.add_argument("--reason", required=True)
    resolve = subparsers.add_parser("resolve", help="link a human resolution to a terminal run")
    resolve.add_argument("--run-id", required=True)
    resolve.add_argument("--authority", required=True)
    resolve.add_argument("--actor", required=True)
    resolve.add_argument("--reason", required=True)
    resolve.add_argument("--commit")
    prune = subparsers.add_parser("prune", help="list or remove expired ephemeral run telemetry")
    prune.add_argument("--days", type=int, default=30)
    prune.add_argument("--apply", action="store_true", help="remove listed records; default is dry-run")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "start":
            provenance_values = [
                args.agent_label, args.runtime, args.provider_model,
                args.prompt_policy_digest, args.trace_reference,
            ]
            provenance = None
            if any(value is not None for value in provenance_values):
                provenance = {
                    "schema_version": "rb-wiki-agent-provenance/0.2",
                    "agent_label": args.agent_label,
                    "runtime": args.runtime,
                    "provider_model": args.provider_model,
                    "prompt_policy_digest": args.prompt_policy_digest,
                    "trace_reference": args.trace_reference,
                    "started_at": None,
                    "finished_at": None,
                    "tool_call_summary": {},
                }
            print(
                json.dumps(
                    start_session(
                        ROOT, args.lane, args.mode, args.authority, args.proposal_id, args.approval_id,
                        provenance,
                    ),
                    sort_keys=True,
                )
            )
            return 0
        if args.command == "heartbeat":
            print(json.dumps(heartbeat_session(ROOT, args.run_id, args.token), sort_keys=True))
            return 0
        if args.command == "status":
            print(json.dumps(status_session(ROOT, args.run_id), sort_keys=True))
            return 0
        if args.command == "finish":
            try:
                code, record = finish_session(ROOT, args.run_id, args.token, args.check)
            except (ContractError, RunError) as exc:
                try:
                    record = terminate_session(ROOT, args.run_id, args.token, "failed", str(exc))
                except (ContractError, RunError):
                    raise exc
                print(json.dumps(record, sort_keys=True))
                return 1
            print(json.dumps(record, sort_keys=True))
            return code
        if args.command == "recover":
            code, record = recover_run(
                ROOT, args.run_id, token=args.token, authority_id=args.authority
            )
            print(json.dumps(record, sort_keys=True))
            return code
        if args.command in {"cancel", "fail"}:
            target = "cancelled" if args.command == "cancel" else "failed"
            print(json.dumps(terminate_session(ROOT, args.run_id, args.token, target, args.reason), sort_keys=True))
            return 0 if target == "cancelled" else 1
        if args.command == "break-lock":
            print(json.dumps(break_lock(ROOT, args.authority, args.actor, args.reason), sort_keys=True))
            return 0
        if args.command == "resolve":
            print(
                json.dumps(
                    record_resolution(ROOT, args.run_id, args.authority, args.actor, args.reason, args.commit),
                    sort_keys=True,
                )
            )
            return 0
        if args.command == "prune":
            candidates = prune_ephemeral_records(ROOT, args.days, dry_run=not args.apply)
            action = "removed" if args.apply else "would remove"
            for path in candidates:
                print(f"{action}: {path}")
            print(f"{action} {len(candidates)} expired ephemeral record(s)")
            return 0
        code, record = execute_run(ROOT, args.lane, args.mode, args.authority, full=args.full)
    except LockHeldError as exc:
        print(f"BLOCKED: {exc}", file=sys.stderr)
        return 2
    except (ContractError, RunError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    print(f"{record['state']}: {record['run_id']} ({record['result']})")
    if record["error"]:
        print(record["error"], file=sys.stderr)
    return code


if __name__ == "__main__":
    sys.exit(main())
