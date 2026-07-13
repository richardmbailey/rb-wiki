#!/usr/bin/env python3
"""Read-only compatibility and operational health inspection for an RB Wiki."""

from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.dont_write_bytecode = True

from capabilities import capability_snapshot, reconcile_capabilities
from provenance import validate_provenance
from authority import load_runtime_policy
from run_lib import (
    ROOT,
    ContractError,
    RunError,
    load_lock_owner,
    parse_utc,
    require_contract_dependencies,
    utc_now,
    validate_contract,
    validate_run_record,
)
from semantic_protocol import load_policy_bundle
from lane_runtime import validate_lane_contracts
from source_registry import load_registry_document
from run_store import TRANSACTION_STAGES, load_receipt, load_transaction
from fs_safety import checked_root, enumerate_regular_files, safe_path, symlink_component

TERMINAL = {"completed", "blocked", "failed", "cancelled", "manual-commit-required", "approval-required"}


def diagnostic(
    diagnostic_id: str,
    status: str,
    severity: str,
    evidence: list[str],
    recommended_action: str = "",
) -> dict[str, Any]:
    return {
        "diagnostic_id": diagnostic_id,
        "status": status,
        "severity": severity,
        "evidence": evidence,
        "recommended_action": recommended_action,
    }


def process_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except (ProcessLookupError, ValueError):
        return False
    except PermissionError:
        return True
    return True


def git_governance_status(root: Path) -> dict[str, Any]:
    try:
        completed = subprocess.run(
            ["git", "status", "--porcelain=v1", "--", "wiki-manifest.yml", "schema", "tools"],
            cwd=root,
            text=True,
            capture_output=True,
            check=False,
            timeout=30,
        )
    except subprocess.TimeoutExpired:
        return diagnostic(
            "governance-dirt",
            "warn",
            "high",
            ["Git governance inspection exceeded 30 seconds."],
            "Inspect the worktree and Git process state before managed mutation.",
        )
    if completed.returncode:
        return diagnostic("governance-dirt", "info", "low", ["Wiki is not inside an inspectable Git worktree."])
    paths = [line[3:] for line in completed.stdout.splitlines() if len(line) > 3]
    return diagnostic(
        "governance-dirt",
        "warn" if paths else "pass",
        "high" if paths else "info",
        paths or ["Committed governance files are clean."],
        "Review and commit or restore governance changes before scheduled/autonomous work." if paths else "",
    )


def lock_status(root: Path, now: datetime) -> dict[str, Any]:
    lock = root / ".wiki_state" / "mutation.lock"
    unsafe = symlink_component(lock, root)
    if unsafe is not None:
        return diagnostic(
            "mutation-lock",
            "fail",
            "critical",
            [f"Mutation lock path traverses a symlink: {unsafe}"],
            "Preserve the path and inspect it manually; do not follow or remove it automatically.",
        )
    if not lock.exists():
        return diagnostic("mutation-lock", "pass", "info", ["No mutation lock is present."])
    try:
        owner = json.loads((lock / "owner.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return diagnostic("mutation-lock", "fail", "critical", [f"Lock owner metadata is unreadable: {exc}"], "Use the audited break-lock procedure after confirming no writer is alive.")
    if not isinstance(owner, dict):
        return diagnostic("mutation-lock", "fail", "critical", ["Lock owner metadata is not an object."], "Preserve the lock and inspect it manually.")
    if owner.get("schema_version") == "rb-wiki-mutation-lock/0.2":
        try:
            validate_contract(owner, "mutation-lock", root)
        except ContractError as exc:
            return diagnostic(
                "mutation-lock", "fail", "critical", [f"Current lock contract is invalid: {exc}"],
                "Preserve the lock and use audited recovery after inspecting the owner record.",
            )
    pid = owner.get("pid")
    run_id = owner.get("run_id")
    if (
        not isinstance(pid, int)
        or isinstance(pid, bool)
        or not isinstance(run_id, str)
        or not run_id
        or Path(run_id).name != run_id
        or "/" in run_id
        or "\\" in run_id
    ):
        return diagnostic(
            "mutation-lock",
            "fail",
            "critical",
            ["Lock owner metadata has an invalid pid or run_id."],
            "Preserve the lock and use audited manual recovery after inspecting the owner record.",
        )
    alive = owner.get("host") == socket.gethostname() and process_alive(pid)
    session_path = root / ".wiki_state" / "sessions" / f"{run_id}.json"
    stale_lease = False
    unsafe_session = symlink_component(session_path, root)
    if unsafe_session is not None:
        stale_lease = True
    elif session_path.is_file():
        try:
            session = json.loads(session_path.read_text(encoding="utf-8"))
            validate_contract(session, "runtime-session", ROOT)
            validate_run_record(session.get("record"), ROOT)
            lease = session.get("record", {}).get("lease_expires_at") or owner.get("lease_expires_at")
            stale_lease = bool(lease and now >= parse_utc(lease))
        except (OSError, json.JSONDecodeError, ContractError):
            stale_lease = True
    status = "info" if alive and not stale_lease else "warn"
    return diagnostic(
        "mutation-lock",
        status,
        "info" if status == "info" else "high",
        [f"run_id={owner.get('run_id')}", f"same-host process alive={alive}", f"lease stale={stale_lease}"],
        "Inspect the owner/session; never remove a lock based on age alone." if status == "warn" else "",
    )


def incomplete_runs(root: Path) -> dict[str, Any]:
    found: list[str] = []
    runs_dir = root / ".wiki_state" / "runs"
    unsafe = symlink_component(runs_dir, root)
    if unsafe is not None:
        found.append(f"runtime journal path traverses a symlink: {unsafe}")
        paths: list[Path] = []
    else:
        paths = sorted(runs_dir.glob("*.json"))
    for path in paths:
        if path.is_symlink():
            found.append(f"{path.name}: symlink is unsafe")
            continue
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
            validate_run_record(record, ROOT)
        except (OSError, json.JSONDecodeError, ContractError) as exc:
            found.append(f"{path.name}: invalid or unreadable: {exc}")
            continue
        if record.get("state") not in TERMINAL:
            found.append(f"{path.name}: {record.get('state', 'unknown')}")
    return diagnostic(
        "incomplete-runs",
        "warn" if found else "pass",
        "high" if found else "info",
        found or ["No incomplete run journals found."],
        "Inspect the session/lock and explicitly finish, fail, or recover the run." if found else "",
    )


def filesystem_boundary_status(root: Path) -> dict[str, Any]:
    errors: list[str] = []
    try:
        checked_root(root)
        for relative in ["tools", "schema", "sources", "wiki", "reports"]:
            safe_path(root, relative, final_type="directory")
    except ContractError as exc:
        errors.append(str(exc))
    return diagnostic(
        "filesystem-boundaries",
        "fail" if errors else "pass",
        "critical" if errors else "info",
        errors or ["Operational roots and primary parents are real in-root directories."],
        "Replace symlinked or escaped operational parents before running migration or mutation." if errors else "",
    )


def resolution_link_status(root: Path) -> dict[str, Any]:
    errors: list[str] = []
    try:
        paths = enumerate_regular_files(root, "reports/resolutions", ".json")
    except ContractError as exc:
        if "missing" in str(exc):
            paths = []
        else:
            errors.append(str(exc))
            paths = []
    for path in paths:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            validate_contract(data, "resolution-record", ROOT)
        except (OSError, json.JSONDecodeError, ContractError) as exc:
            errors.append(f"{path.name}: invalid resolution record: {exc}")
            continue
        commit = data.get("commit_hash")
        if commit is not None:
            result = subprocess.run(
                ["git", "cat-file", "-t", commit], cwd=root, text=True,
                capture_output=True, check=False, timeout=30,
            )
            if result.returncode or result.stdout.strip() != "commit":
                errors.append(f"{path.name}: commit link is missing or not a commit")
        original = root / ".wiki_state" / "runs" / f"{data['run_id']}.json"
        unsafe_original = symlink_component(original, root)
        if unsafe_original is not None:
            errors.append(f"{path.name}: original run path traverses a symlink")
            continue
        if not original.is_file():
            original = root / "reports" / "runs" / f"{data['run_id']}.json"
            unsafe_original = symlink_component(original, root)
            if unsafe_original is not None:
                errors.append(f"{path.name}: durable run path traverses a symlink")
                continue
        try:
            original_data = json.loads(original.read_text(encoding="utf-8"))
            validate_run_record(original_data, ROOT)
        except (OSError, json.JSONDecodeError, ContractError) as exc:
            errors.append(f"{path.name}: original run record is unavailable or invalid: {exc}")
            continue
        if original_data.get("state") != data.get("original_state"):
            errors.append(f"{path.name}: original run state no longer matches the resolution")
    return diagnostic(
        "resolution-links",
        "warn" if errors else "pass",
        "high" if errors else "info",
        errors or ["Resolution records link to valid original runs and commit objects."],
        "Review or replace invalid resolution evidence; never rewrite the original run outcome." if errors else "",
    )


def transaction_recovery_status(root: Path) -> dict[str, Any]:
    evidence: list[str] = []
    transactions = root / ".wiki_state" / "transactions"
    unsafe = symlink_component(transactions, root)
    if unsafe is not None:
        return diagnostic(
            "transaction-recovery",
            "fail",
            "critical",
            [f"Transaction directory traverses a symlink: {unsafe}"],
            "Preserve the directory and inspect it without following the symlink.",
        )
    for path in sorted(transactions.glob("*.json")):
        run_id = path.stem
        try:
            transaction = load_transaction(root, run_id)
        except (ContractError, RunError, OSError) as exc:
            evidence.append(f"{run_id}: invalid transaction: {exc}")
            continue
        stage = transaction["stage"]
        session_path = root / ".wiki_state" / "sessions" / path.name
        receipt_path = root / ".wiki_state" / "receipts" / path.name
        lock_owner = root / ".wiki_state" / "mutation.lock" / "owner.json"
        lock_retained = False
        try:
            lock_retained = load_lock_owner(lock_owner, root).get("run_id") == run_id
        except (OSError, ContractError):
            pass
        if TRANSACTION_STAGES.index(stage) >= TRANSACTION_STAGES.index("branch-moved"):
            branch = subprocess.run(
                ["git", "rev-parse", transaction["branch_ref"]],
                cwd=root,
                text=True,
                capture_output=True,
                check=False,
                timeout=30,
            )
            if branch.returncode or branch.stdout.strip() != transaction["commit_hash"]:
                evidence.append(f"{run_id}: branch evidence is missing or divergent")
                continue
        elif stage == "commit-created":
            branch = subprocess.run(
                ["git", "rev-parse", transaction["branch_ref"]], cwd=root, text=True,
                capture_output=True, check=False, timeout=30,
            )
            if branch.returncode == 0 and branch.stdout.strip() == transaction["commit_hash"]:
                evidence.append(
                    f"{run_id}: branch points at the created commit but the transaction stage was not persisted"
                )
                continue
        if stage == "branch-moved":
            evidence.append(f"{run_id}: branch moved; index refresh and receipt are pending")
        elif stage == "index-refreshed":
            evidence.append(f"{run_id}: index refreshed; commit receipt is missing")
        elif stage == "receipt-written":
            evidence.append(f"{run_id}: receipt exists; session reconciliation is incomplete")
        elif stage == "reconciled":
            try:
                if symlink_component(session_path, root) is not None:
                    raise OSError("session path traverses a symlink")
                session = json.loads(session_path.read_text(encoding="utf-8"))
                validate_contract(session, "runtime-session", ROOT)
                validate_run_record(session.get("record"), ROOT)
                state = session.get("record", {}).get("state")
            except (OSError, json.JSONDecodeError, ContractError):
                state = "unreadable"
            if state != "completed" or lock_retained:
                evidence.append(
                    f"{run_id}: transaction reconciled but session={state}, lock-retained={lock_retained}"
                )
        elif lock_retained:
            evidence.append(f"{run_id}: pre-commit transaction {stage} retains the mutation lock")
        if receipt_path.exists():
            try:
                receipt = load_receipt(root, run_id)
                if receipt.get("commit_hash") != transaction.get("commit_hash"):
                    evidence.append(f"{run_id}: receipt commit differs from transaction")
            except (ContractError, RunError, OSError) as exc:
                evidence.append(f"{run_id}: invalid receipt: {exc}")
    return diagnostic(
        "transaction-recovery",
        "warn" if evidence else "pass",
        "high" if evidence else "info",
        evidence or ["No incomplete Git transactions found."],
        (
            "For a branch-moved session run the exact recover command in its run record; "
            "do not rerun work or move the branch."
            if evidence else ""
        ),
    )


def incomplete_ingest(root: Path) -> dict[str, Any]:
    found: list[str] = []
    try:
        for entry in load_registry_document(root / "sources" / "_source_registry.yml")["sources"]:
            if entry["ingest_state"] not in {"validated", "inbox-archived"}:
                found.append(f"{entry['source_id']}: registry state {entry['ingest_state']}")
    except Exception as exc:
        found.append(f"registry unreadable: {exc}")
    sources_state = root / ".wiki_state" / "sources"
    unsafe = symlink_component(sources_state, root)
    if unsafe is not None:
        found.append(f"source transition path traverses a symlink: {unsafe}")
        paths: list[Path] = []
    else:
        paths = sorted(sources_state.glob("*.json"))
    for path in paths:
        if path.is_symlink():
            found.append(f"{path.name}: transition journal symlink is unsafe")
            continue
        try:
            transition = json.loads(path.read_text(encoding="utf-8"))
            validate_contract(transition, "source-transition", ROOT)
        except (OSError, json.JSONDecodeError, ContractError) as exc:
            found.append(f"{path.name}: transition journal invalid or unreadable: {exc}")
            continue
        if transition.get("outcome") != "complete":
            found.append(f"{path.name}: {transition.get('outcome')} at {transition.get('next_transition')}")
    return diagnostic(
        "incomplete-ingest",
        "warn" if found else "pass",
        "high" if found else "info",
        found or ["No incomplete source transitions found."],
        "Resume the digest through a controller-owned ingest session." if found else "",
    )


def report_backlog(root: Path) -> dict[str, Any]:
    lint_dir = root / "reports" / "lint"
    unsafe_dir = symlink_component(lint_dir, root)
    if unsafe_dir is not None:
        return diagnostic(
            "report-backlog",
            "fail",
            "critical",
            [f"Lint report path traverses a symlink: {unsafe_dir}"],
            "Restore reports/lint as a real in-wiki directory before running maintenance.",
        )
    report_candidates = list(lint_dir.glob("*.json"))
    unsafe = [path for path in report_candidates if path.is_symlink()]
    if unsafe:
        return diagnostic(
            "report-backlog",
            "warn",
            "medium",
            [f"Lint report is a symlink: {path.name}" for path in unsafe],
            "Remove the unsafe report path and regenerate lint output.",
        )
    reports = sorted(report_candidates, key=lambda path: path.stat().st_mtime)
    if not reports:
        return diagnostic("report-backlog", "info", "low", ["No structured lint report exists yet."], "Run full lint when review is desired.")
    try:
        latest = json.loads(reports[-1].read_text(encoding="utf-8"))
        validate_contract(latest, "lint-report", ROOT)
        queues = latest.get("queues", {})
        items = [f"{name}: {', '.join(values)}" for name, values in queues.items() if values]
    except (OSError, json.JSONDecodeError, ContractError) as exc:
        return diagnostic("report-backlog", "warn", "medium", [f"Latest lint report is unreadable: {exc}"], "Regenerate lint output.")
    return diagnostic(
        "report-backlog",
        "warn" if items else "pass",
        "medium" if items else "info",
        items or ["Latest structured lint report has no blockers or overdue actions."],
        "Process typed queues by outcome, severity, and disposition." if items else "",
    )


def proposal_capability_status(root: Path, active: dict[str, Any]) -> dict[str, Any]:
    """Diagnose proposal snapshots without trusting or executing target-wiki code."""
    try:
        paths = enumerate_regular_files(root, "reports/proposals", ".json")
    except ContractError as exc:
        return diagnostic(
            "proposal-capability-snapshots", "fail", "high", [str(exc)],
            "Repair the unsafe proposal path before semantic apply.",
        )
    errors: list[str] = []
    for path in paths:
        relative = path.relative_to(root).as_posix()
        try:
            if path.stat().st_size > 1024 * 1024:
                raise ContractError("proposal exceeds the 1 MiB diagnostic limit")
            proposal = json.loads(path.read_text(encoding="utf-8"))
            validate_contract(proposal, "synthesis-proposal", ROOT)
        except (OSError, json.JSONDecodeError, ContractError) as exc:
            errors.append(f"{relative}: invalid proposal: {exc}")
            continue
        if proposal["policy_snapshot"]["capabilities"] != active:
            errors.append(f"{relative}: capability snapshot is stale")
    return diagnostic(
        "proposal-capability-snapshots", "fail" if errors else "pass", "high" if errors else "info",
        errors or [f"{len(paths)} proposal capability snapshot(s) reconcile."],
        "Regenerate or explicitly migrate stale proposals; never apply them silently." if errors else "",
    )


def build_report(root: Path = ROOT, now: datetime | None = None) -> dict[str, Any]:
    current = now or datetime.now(timezone.utc)
    diagnostics: list[dict[str, Any]] = []
    wiki_id = "unknown-wiki"
    manifest: dict[str, Any] = {"enabled_capabilities": []}
    dependencies_available = True
    try:
        require_contract_dependencies()
        diagnostics.append(diagnostic("dependencies", "pass", "info", ["PyYAML and jsonschema are available."]))
    except RunError as exc:
        dependencies_available = False
        diagnostics.append(diagnostic("dependencies", "fail", "critical", [str(exc)], "Install the declared package dependencies."))
    try:
        manifest, _policy = load_runtime_policy(root)
        wiki_id = manifest["wiki_id"]
        load_policy_bundle(root)
        validate_lane_contracts(root)
        diagnostics.append(diagnostic("versions-and-policy", "pass", "info", ["Manifest, policy hierarchy, and lane contracts validate as v0.2."]))
        overrides = manifest["local_overrides"]
        missing = [path for path in overrides if not (root / path).exists()]
        diagnostics.append(
            diagnostic(
                "local-overrides",
                "warn" if missing else "info",
                "medium" if missing else "info",
                ([f"Declared override: {path}" for path in overrides] or ["No local overrides declared."])
                + [f"Missing override path: {path}" for path in missing],
                "Reconcile missing override declarations before migration." if missing else "",
            )
        )
    except (ContractError, RunError, OSError, KeyError) as exc:
        diagnostics.append(diagnostic("versions-and-policy", "fail", "critical", [str(exc)], "Run migration dry-run and review policy divergence."))
    diagnostics.extend(
        [
            git_governance_status(root),
            filesystem_boundary_status(root),
            lock_status(root, current),
            incomplete_runs(root),
            transaction_recovery_status(root),
            incomplete_ingest(root),
            resolution_link_status(root),
        ]
    )
    try:
        errors = validate_provenance(root=root, contract_root=ROOT)
    except (ContractError, RunError, OSError, KeyError) as exc:
        errors = [str(exc)]
    diagnostics.append(
        diagnostic(
            "provenance",
            "fail" if errors else "pass",
            "critical" if errors else "info",
            errors or ["Registry, raw evidence, References, and citations reconcile."],
            "Repair deterministic provenance before semantic use." if errors else "",
        )
    )
    capabilities = capability_snapshot(root)
    try:
        validate_contract(capabilities, "capability-snapshot", ROOT)
        capability_errors = reconcile_capabilities(manifest, capabilities)
    except (ContractError, RunError, UnboundLocalError) as exc:
        capability_errors = [str(exc)]
    diagnostics.append(
        diagnostic(
            "capability-contract",
            "fail" if capability_errors else "pass",
            "critical" if capability_errors else "info",
            capability_errors or ["Manifest and executable capability registry reconcile."],
            "Remove unknown claims or restore and validate the required implementation/dependency." if capability_errors else "",
        )
    )
    registry_only = sorted(
        set(capabilities["capabilities"]).difference(manifest.get("enabled_capabilities", []))
    )
    diagnostics.append(
        diagnostic(
            "registry-only-capabilities", "info", "info",
            registry_only or ["Every registry capability is manifest-enabled."],
        )
    )
    unavailable = sorted(name for name, value in capabilities["capabilities"].items() if not value["available"])
    diagnostics.append(diagnostic("unavailable-capabilities", "info", "info", unavailable or ["All declared capabilities are available."]))
    diagnostics.append(proposal_capability_status(root, capabilities))
    diagnostics.append(report_backlog(root))
    overall = "blocked" if any(item["status"] == "fail" for item in diagnostics) else "attention" if any(item["status"] == "warn" for item in diagnostics) else "healthy"
    report = {
        "schema_version": "rb-wiki-doctor-report/0.2",
        "created_at": current.replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "wiki_id": wiki_id,
        "overall": overall,
        "diagnostics": diagnostics,
        "capabilities": capabilities,
    }
    if dependencies_available:
        validate_contract(report, "doctor-report", ROOT)
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Read-only RB Wiki doctor")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args(argv)
    report = build_report(args.root.absolute())
    if args.json:
        print(json.dumps(report, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    else:
        print(f"RB Wiki doctor: {report['overall']}")
        for item in report["diagnostics"]:
            print(f"[{item['status'].upper()}] {item['diagnostic_id']}: {'; '.join(item['evidence'])}")
    return 1 if report["overall"] == "blocked" else 0


if __name__ == "__main__":
    sys.exit(main())
