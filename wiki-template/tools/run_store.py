"""Atomic, validated persistence for managed-run recovery state."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from agent_provenance import validate_agent_provenance
from contracts import load_json_contract, validate_contract
from errors import ContractError, RunError
from run_lib import (
    atomic_write_json, atomic_write_text, ensure_safe_parent, render_run_markdown,
    parse_utc, symlink_component, validate_run_record,
)

TRANSACTION_STAGES = (
    "prepared",
    "commit-created",
    "branch-moved",
    "index-refreshed",
    "receipt-written",
    "reconciled",
)


def _runtime_path(root: Path, directory: str, run_id: str) -> Path:
    if not run_id or Path(run_id).name != run_id or "/" in run_id or "\\" in run_id:
        raise RunError("invalid run ID")
    path = root / ".wiki_state" / directory / f"{run_id}.json"
    ensure_safe_parent(path, root)
    return path


def transaction_path(root: Path, run_id: str) -> Path:
    return _runtime_path(root, "transactions", run_id)


def receipt_path(root: Path, run_id: str) -> Path:
    return _runtime_path(root, "receipts", run_id)


def session_path(root: Path, run_id: str) -> Path:
    return _runtime_path(root, "sessions", run_id)


def journal_path(root: Path, run_id: str) -> Path:
    return _runtime_path(root, "runs", run_id)


def save_runtime_record(record: dict[str, Any], root: Path) -> None:
    validate_run_record(record, root)
    validate_agent_provenance(record.get("agent_provenance"), root)
    atomic_write_json(journal_path(root, record["run_id"]), record, root)
    atomic_write_json(root / ".wiki_state" / "latest.json", record, root)


def load_runtime_record(root: Path, run_id: str) -> dict[str, Any]:
    record = load_json_contract(journal_path(root, run_id), "run-record", root)
    if record.get("run_id") != run_id:
        raise ContractError("run journal filename and run identity differ")
    validate_run_record(record, root)
    validate_agent_provenance(record.get("agent_provenance"), root)
    return record


def save_durable_record(record: dict[str, Any], latest: dict[str, Any], root: Path) -> None:
    validate_run_record(record, root)
    validate_agent_provenance(record.get("agent_provenance"), root)
    validate_contract(latest, "tracked-latest", root)
    durable = root / "reports" / "runs" / f"{record['run_id']}.json"
    atomic_write_json(durable, record, root)
    atomic_write_text(durable.with_suffix(".md"), render_run_markdown(record), root)
    atomic_write_json(root / "reports" / "latest.json", latest, root)


def save_session_envelope(session: dict[str, Any], root: Path) -> None:
    record = session.get("record")
    if not isinstance(record, dict):
        raise ContractError("runtime session has no run record")
    validate_run_record(record, root)
    validate_agent_provenance(record.get("agent_provenance"), root)
    validate_contract(session, "runtime-session", root)
    atomic_write_json(session_path(root, record["run_id"]), session, root)


def load_session_envelope(root: Path, run_id: str) -> dict[str, Any]:
    runtime_path = session_path(root, run_id)
    unsafe = symlink_component(runtime_path, root)
    if unsafe is not None:
        raise RunError(f"runtime session path traverses a symlink: {unsafe}")
    try:
        session = json.loads(runtime_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RunError(f"cannot load session {run_id}: {exc}") from exc
    if not isinstance(session, dict) or session.get("record", {}).get("run_id") != run_id:
        raise RunError("invalid session record")
    validate_contract(session, "runtime-session", root)
    validate_run_record(session["record"], root)
    validate_agent_provenance(session["record"].get("agent_provenance"), root)
    journal_record = load_runtime_record(root, run_id)
    if session["record"] != journal_record:
        raise RunError("runtime session record differs from the run journal")
    return session


def validate_transaction(transaction: dict[str, Any], root: Path) -> None:
    validate_contract(transaction, "git-transaction", root)
    stage_index = TRANSACTION_STAGES.index(transaction["stage"])
    identities = (transaction["commit_hash"], transaction["tree_hash"])
    if stage_index == 0 and identities != (None, None):
        raise ContractError("prepared transaction cannot contain commit identities")
    if stage_index >= 1 and not all(isinstance(value, str) for value in identities):
        raise ContractError("commit-created transaction requires commit and tree identities")
    if stage_index < 2 and transaction["branch_head"] is not None:
        raise ContractError("branch evidence is invalid before branch-moved")
    if stage_index >= 2 and transaction["branch_head"] != transaction["commit_hash"]:
        raise ContractError("branch-moved transaction must bind branch head to the commit")
    if transaction["expected_paths"] != sorted(set(transaction["expected_paths"])):
        raise ContractError("transaction expected_paths must be sorted and unique")


def save_transaction(transaction: dict[str, Any], root: Path) -> None:
    validate_transaction(transaction, root)
    atomic_write_json(transaction_path(root, transaction["run_id"]), transaction, root)


def load_transaction(root: Path, run_id: str) -> dict[str, Any]:
    transaction = load_json_contract(transaction_path(root, run_id), "git-transaction", root)
    if transaction.get("run_id") != run_id:
        raise ContractError("transaction filename and run identity differ")
    validate_transaction(transaction, root)
    return transaction


def save_receipt(receipt: dict[str, Any], root: Path) -> None:
    validate_contract(receipt, "commit-receipt", root)
    path = receipt_path(root, receipt["run_id"])
    if path.exists():
        if load_receipt(root, receipt["run_id"]) != receipt:
            raise RunError("commit receipt already exists with different evidence")
        return
    atomic_write_json(path, receipt, root)


def load_receipt(root: Path, run_id: str) -> dict[str, Any]:
    receipt = load_json_contract(receipt_path(root, run_id), "commit-receipt", root)
    if receipt.get("run_id") != run_id:
        raise ContractError("receipt filename and run identity differ")
    return receipt


def prune_ephemeral_records(
    root: Path, days: int = 30, *, dry_run: bool = True, now: datetime | None = None
) -> list[str]:
    """List or remove old terminal ephemeral journals without touching durable or live state."""
    if days < 1:
        raise RunError("retention days must be at least 1")
    current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    cutoff = current - timedelta(days=days)
    candidates: list[str] = []
    runs_dir = root / ".wiki_state" / "runs"
    unsafe = symlink_component(runs_dir, root)
    if unsafe is not None:
        raise RunError(f"refusing to prune runtime journals through symlink: {unsafe}")
    durable_dir = root / "reports" / "runs"
    unsafe_durable = symlink_component(durable_dir, root)
    if unsafe_durable is not None:
        raise RunError(f"refusing to inspect durable reports through symlink: {unsafe_durable}")
    for path in sorted(runs_dir.glob("*.json")):
        try:
            record = load_json_contract(path, "run-record", root)
        except (ContractError, OSError):
            continue
        if record.get("state") not in {
            "completed", "blocked", "failed", "cancelled", "manual-commit-required", "approval-required"
        }:
            continue
        if record.get("report_class") != "ephemeral-telemetry" or record.get("durable_record"):
            continue
        if (durable_dir / path.name).exists():
            continue
        finished = record.get("finished_at")
        if not isinstance(finished, str) or parse_utc(finished) >= cutoff:
            continue
        candidates.append(path.relative_to(root).as_posix())
    if not dry_run:
        for relative in candidates:
            (root / relative).unlink()
    return candidates
