#!/usr/bin/env python3
"""Shared policy, record, Git, and single-writer helpers for managed runs."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import socket
import subprocess
import sys
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path, PurePosixPath
from typing import Any

from contracts import (
    MAX_YAML_BYTES,
    load_json_contract,
    load_yaml_contract,
    load_yaml_text,
    require_contract_dependencies,
    validate_contract,
)
from errors import CommittedRecoveryRequired, ContractError, DependencyError, RunError
from fs_safety import ensure_safe_parent, symlink_component

ROOT = Path(__file__).resolve().parents[1]
STATE_DIR = ROOT / ".wiki_state"
GIT_TIMEOUT_SECONDS = 120


class LockHeldError(RunError):
    """The mutation lock already exists."""

    def __init__(self, message: str, owner: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.owner = owner


TERMINAL_STATES = {"completed", "blocked", "failed", "cancelled", "manual-commit-required", "approval-required"}
STATE_TRANSITIONS = {
    "created": {"locked", "blocked", "failed"},
    "locked": {"preflight", "blocked", "failed"},
    "preflight": {"running", "blocked", "failed"},
    "running": {"validating", "cancelled", "failed"},
    "validating": {"completed", "manual-commit-required", "approval-required", "committed-recovery-required", "failed"},
    "committed-recovery-required": {"completed", "failed"},
}


def require_transition(current: str, target: str) -> None:
    if current in TERMINAL_STATES or target not in STATE_TRANSITIONS.get(current, set()):
        raise RunError(f"invalid run-state transition: {current} -> {target}")


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def utc_after(seconds: int, now: datetime | None = None) -> str:
    current = now or datetime.now(timezone.utc)
    return (current + timedelta(seconds=seconds)).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_utc(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ContractError(f"invalid UTC timestamp: {value}") from exc
    if parsed.tzinfo is None:
        raise ContractError(f"timestamp must include a timezone: {value}")
    return parsed.astimezone(timezone.utc)


def new_run_id() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{stamp}-{uuid.uuid4().hex[:12]}"


def canonical_json(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"


def atomic_write_text(path: Path, text: str, root: Path) -> None:
    ensure_safe_parent(path, root)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        with temporary.open("x", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        fsync_directory(path.parent)
    finally:
        if temporary.exists():
            temporary.unlink()


def atomic_write_json(path: Path, data: Any, root: Path) -> None:
    atomic_write_text(path, canonical_json(data), root)


def fsync_directory(path: Path) -> None:
    """Persist directory-entry changes where the local filesystem supports it."""
    try:
        descriptor = os.open(path, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(descriptor)
    except OSError:
        # Some filesystems do not support directory fsync; file content was already fsynced.
        pass
    finally:
        os.close(descriptor)


def validate_safe_paths(paths: list[str], label: str) -> None:
    for value in paths:
        path = PurePosixPath(value)
        if path.is_absolute() or ".." in path.parts or "\\" in value or value in {"", "."}:
            raise ContractError(f"unsafe {label} path: {value}")


def run_git(root: Path, *args: str, text: bool = True) -> subprocess.CompletedProcess[Any]:
    try:
        completed = subprocess.run(
            ["git", *args],
            cwd=root,
            capture_output=True,
            text=text,
            check=False,
            timeout=GIT_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired as exc:
        raise RunError(f"git {' '.join(args)} exceeded {GIT_TIMEOUT_SECONDS} seconds") from exc
    if completed.returncode != 0:
        stderr = completed.stderr.strip() if text else completed.stderr.decode("utf-8", "replace").strip()
        raise RunError(f"git {' '.join(args)} failed: {stderr}")
    return completed


def run_git_env(
    root: Path, args: list[str], env_overrides: dict[str, str], check: bool = True
) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env.update(env_overrides)
    try:
        completed = subprocess.run(
            ["git", *args],
            cwd=root,
            env=env,
            text=True,
            capture_output=True,
            check=False,
            timeout=GIT_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired as exc:
        raise RunError(f"git {' '.join(args)} exceeded {GIT_TIMEOUT_SECONDS} seconds") from exc
    if check and completed.returncode != 0:
        raise RunError(f"git {' '.join(args)} failed: {completed.stderr.strip()}")
    return completed


def git_base_commit(root: Path = ROOT) -> str:
    return run_git(root, "rev-parse", "HEAD").stdout.strip()


def git_worktree_count(root: Path = ROOT) -> int:
    output = run_git(root, "worktree", "list", "--porcelain").stdout
    return sum(1 for line in output.splitlines() if line.startswith("worktree "))


def git_repository_root(root: Path = ROOT) -> Path:
    return Path(run_git(root, "rev-parse", "--show-toplevel").stdout.strip()).resolve()


def git_status_paths(root: Path = ROOT) -> list[str]:
    output = run_git(root, "status", "--porcelain=v1", "--untracked-files=all", "-z", text=False).stdout
    entries = output.decode("utf-8", "surrogateescape").split("\0")
    paths: list[str] = []
    index = 0
    while index < len(entries):
        entry = entries[index]
        index += 1
        if not entry:
            continue
        status = entry[:2]
        path = entry[3:]
        paths.append(path)
        if status[0] in {"R", "C"} and index < len(entries):
            original_path = entries[index]
            index += 1
            paths.append(original_path)
    return sorted(set(paths))


def git_status_entries(root: Path = ROOT) -> list[dict[str, str]]:
    output = run_git(root, "status", "--porcelain=v1", "--untracked-files=all", "-z", text=False).stdout
    fields = output.decode("utf-8", "surrogateescape").split("\0")
    entries: list[dict[str, str]] = []
    index = 0
    while index < len(fields):
        field = fields[index]
        index += 1
        if not field:
            continue
        status, path = field[:2], field[3:]
        entries.append({"status": status, "path": path})
        if status[0] in {"R", "C"} and index < len(fields):
            entries.append({"status": "OR", "path": fields[index]})
            index += 1
    return sorted(entries, key=lambda item: (item["path"], item["status"]))


def path_fingerprints(paths: list[str], root: Path = ROOT) -> dict[str, str]:
    fingerprints: dict[str, str] = {}
    for relative in paths:
        path = root / relative
        if path.is_symlink():
            fingerprints[relative] = "symlink:" + os.readlink(path)
        elif path.is_file():
            fingerprints[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
        elif path.exists():
            fingerprints[relative] = "non-file"
        else:
            fingerprints[relative] = "missing"
    return fingerprints


def content_manifest_hash(paths: list[str], root: Path = ROOT) -> str:
    items: list[str] = []
    for relative in sorted(path for path in paths if not path.startswith("reports/")):
        path = root / relative
        digest = hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() and not path.is_symlink() else "deleted"
        items.append(f"{relative}\0{digest}")
    return hashlib.sha256("\n".join(items).encode("utf-8")).hexdigest()


def git_show(base: str, relative_path: str, root: Path = ROOT) -> str:
    return run_git(root, "show", f"{base}:{relative_path}").stdout


def path_allowed(path: str, patterns: list[str]) -> bool:
    candidate = PurePosixPath(path)
    for pattern in patterns:
        if pattern.endswith("/**"):
            prefix = pattern[:-3].rstrip("/")
            if path == prefix or path.startswith(prefix + "/"):
                return True
        elif candidate.match(pattern):
            return True
    return False


def unexpected_paths(paths: list[str], patterns: list[str]) -> list[str]:
    return sorted(path for path in paths if not path_allowed(path, patterns))


@dataclass
class MutationLock:
    root: Path
    run_id: str
    lane: str
    mode: str
    lock_dir: Path | None = None
    acquired: bool = False

    def __post_init__(self) -> None:
        self.lock_dir = self.root / ".wiki_state" / "mutation.lock"

    @property
    def owner_path(self) -> Path:
        assert self.lock_dir is not None
        return self.lock_dir / "owner.json"

    def acquire(self) -> None:
        assert self.lock_dir is not None
        ensure_safe_parent(self.lock_dir, self.root)
        self.lock_dir.parent.mkdir(parents=True, exist_ok=True)
        try:
            self.lock_dir.mkdir()
        except FileExistsError as exc:
            owner: dict[str, Any] | None = None
            diagnostic = "mutation lock is held"
            if self.owner_path.is_file():
                try:
                    owner = json.loads(self.owner_path.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError):
                    diagnostic = "mutation lock is held with unreadable owner metadata"
            else:
                diagnostic = "mutation lock is held but owner metadata is incomplete; manual recovery is required"
            raise LockHeldError(diagnostic, owner) from exc
        metadata = {
            "schema_version": "rb-wiki-mutation-lock/0.2",
            "run_id": self.run_id,
            "pid": os.getpid(),
            "host": socket.gethostname(),
            "lane": self.lane,
            "mode": self.mode,
            "acquired_at": utc_now(),
            "heartbeat_at": None,
            "lease_expires_at": None,
        }
        try:
            validate_contract(metadata, "mutation-lock", self.root)
            atomic_write_json(self.owner_path, metadata, self.root)
        except Exception:
            # The directory deliberately remains: an incomplete lock is still held.
            raise
        self.acquired = True

    def update_lease(self, heartbeat_at: str, lease_expires_at: str) -> None:
        if not self.acquired:
            raise RunError("cannot update lease for an unowned mutation lock")
        self.update_owned_lease(self.root, self.run_id, heartbeat_at, lease_expires_at)

    def release(self) -> None:
        if not self.acquired:
            return
        assert self.lock_dir is not None
        unsafe = symlink_component(self.lock_dir, self.root)
        if unsafe is not None:
            raise RunError(f"cannot safely release mutation lock through symlink: {unsafe}")
        try:
            owner = load_lock_owner(self.owner_path, self.root)
        except (OSError, ContractError) as exc:
            raise RunError("cannot safely release mutation lock: owner metadata is missing or unreadable") from exc
        if owner.get("run_id") != self.run_id:
            raise RunError("cannot safely release mutation lock: ownership changed")
        shutil.rmtree(self.lock_dir)
        self.acquired = False

    @classmethod
    def release_owned(cls, root: Path, run_id: str) -> None:
        lock_dir = root / ".wiki_state" / "mutation.lock"
        unsafe = symlink_component(lock_dir, root)
        if unsafe is not None:
            raise RunError(f"cannot safely release mutation lock through symlink: {unsafe}")
        owner_path = lock_dir / "owner.json"
        try:
            owner = load_lock_owner(owner_path, root)
        except (OSError, ContractError) as exc:
            raise RunError("cannot safely release mutation lock: owner metadata is missing or unreadable") from exc
        if owner.get("run_id") != run_id:
            raise RunError("cannot safely release mutation lock: run does not own it")
        shutil.rmtree(lock_dir)

    @classmethod
    def update_owned_lease(
        cls, root: Path, run_id: str, heartbeat_at: str, lease_expires_at: str
    ) -> None:
        owner_path = root / ".wiki_state" / "mutation.lock" / "owner.json"
        unsafe = symlink_component(owner_path, root)
        if unsafe is not None:
            raise RunError(f"cannot update mutation lock lease through symlink: {unsafe}")
        try:
            owner = load_lock_owner(owner_path, root)
        except (OSError, ContractError) as exc:
            raise RunError("cannot update mutation lock lease: owner metadata is unreadable") from exc
        if owner.get("run_id") != run_id:
            raise RunError("cannot update mutation lock lease: run does not own it")
        owner["heartbeat_at"] = heartbeat_at
        owner["lease_expires_at"] = lease_expires_at
        validate_contract(owner, "mutation-lock", root)
        atomic_write_json(owner_path, owner, root)


def load_lock_owner(path: Path, root: Path) -> dict[str, Any]:
    """Load current lock metadata, or bounded legacy metadata for diagnosis only."""
    unsafe = symlink_component(path, root)
    if unsafe is not None:
        raise ContractError(f"mutation lock owner path traverses a symlink: {unsafe}")
    try:
        if path.stat().st_size > 64 * 1024:
            raise ContractError("mutation lock owner metadata exceeds 64 KiB")
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ContractError(f"invalid mutation lock JSON: {exc}") from exc
    if not isinstance(raw, dict):
        raise ContractError("mutation lock owner metadata must be an object")
    if raw.get("schema_version") == "rb-wiki-mutation-lock/0.2":
        return load_json_contract(path, "mutation-lock", root)
    run_id, pid = raw.get("run_id"), raw.get("pid")
    if not isinstance(run_id, str) or not run_id or not isinstance(pid, int) or pid < 1:
        raise ContractError("legacy mutation lock metadata is incomplete")
    return raw


def validate_run_record(record: dict[str, Any], root: Path = ROOT) -> None:
    validate_contract(record, "run-record", root)
    transaction = record["transaction"]
    stage = record["transaction_stage"]
    if (transaction is None) != (stage is None):
        raise ContractError("run transaction path and stage must either both be present or both be null")
    if transaction is not None and transaction != f".wiki_state/transactions/{record['run_id']}.json":
        raise ContractError("run transaction path must bind to the run ID")
    if record["commit_hash"] is not None and transaction is None:
        raise ContractError("run commit hash requires a bound transaction")
    if stage in {"branch-moved", "index-refreshed", "receipt-written", "reconciled"} and record["commit_hash"] is None:
        raise ContractError("post-branch transaction stage requires a commit hash")
    # A tracked report is deliberately staged before its future commit identity
    # exists, while the ignored runtime journal advances through the remaining
    # transaction stages.  The final receipt supplies the non-self-referential
    # commit evidence, so a completed report may validly describe that prepared
    # snapshot or a transient post-branch stage.
    if record["commit_hash"] is not None and record["state"] not in {"completed", "committed-recovery-required"}:
        raise ContractError("commit evidence is inconsistent with the run state")
    recovery = record["state"] == "committed-recovery-required"
    if recovery != (record["result"] == "committed-recovery-required"):
        raise ContractError("committed recovery state and result must agree")
    if recovery:
        if record["finished_at"] is not None:
            raise ContractError("committed recovery is non-terminal and cannot have finished_at")
        if record["commit_hash"] is None or stage not in {
            "branch-moved", "index-refreshed", "receipt-written", "reconciled"
        }:
            raise ContractError("committed recovery requires branch-moved commit evidence")


def render_run_markdown(record: dict[str, Any]) -> str:
    """Render a compact human-readable view of the canonical JSON record."""
    lines = [
        f"# Managed Wiki Run {record['run_id']}",
        "",
        f"- State: `{record['state']}`",
        f"- Result: `{record['result']}`",
        f"- Lane/mode: `{record['lane']}` / `{record['mode']}`",
        f"- Authority: `{record['authority_id']}`",
        f"- Report class: `{record['report_class']}`",
        f"- Base commit: `{record['base_commit'] or 'unavailable'}`",
        f"- Started: `{record['started_at']}`",
        f"- Finished: `{record['finished_at'] or 'not finished'}`",
        "",
        "## Changed paths",
        "",
    ]
    paths = record["changed_paths"]
    lines.extend([f"- `{path}`" for path in paths] if paths else ["- None."])
    lines.extend(["", "## Checks", ""])
    checks = record["checks"]
    lines.extend(
        [f"- `{check['check_id']}`: **{check['status']}** — {check['summary']}" for check in checks]
        if checks
        else ["- None recorded."]
    )
    if record["error"]:
        lines.extend(["", "## Error", "", str(record["error"])])
    return "\n".join(lines).rstrip() + "\n"
