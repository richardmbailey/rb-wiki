"""Recoverable scoped Git transactions for managed wiki runs."""

from __future__ import annotations

import hashlib
import os
import subprocess
from pathlib import Path
from typing import Any

from errors import CommittedRecoveryRequired, RunError
from run_lib import content_manifest_hash, ensure_safe_parent, git_base_commit, run_git_env, utc_now
from run_store import TRANSACTION_STAGES, save_transaction


def inject_fault(stage: str) -> None:
    requested = {item.strip() for item in os.environ.get("RB_WIKI_FAULT_STAGE", "").split(",") if item.strip()}
    if stage in requested:
        raise OSError(f"injected fault at {stage}")


def advance(transaction: dict[str, Any], stage: str, root: Path, **changes: Any) -> None:
    current = TRANSACTION_STAGES.index(transaction["stage"])
    target = TRANSACTION_STAGES.index(stage)
    if target < current or target > current + 1:
        raise RunError(f"invalid Git transaction transition: {transaction['stage']} -> {stage}")
    transaction.update(changes, stage=stage, updated_at=utc_now(), error=None)
    save_transaction(transaction, root)


def _preflight(root: Path, base_commit: str, paths: list[str], expected_manifest: str) -> str:
    if git_base_commit(root) != base_commit:
        raise RunError("HEAD changed since run start")
    branch_result = run_git_env(root, ["symbolic-ref", "-q", "HEAD"], {}, check=False)
    if branch_result.returncode != 0:
        raise RunError("scoped-auto is unavailable on detached HEAD")
    if run_git_env(root, ["diff", "--cached", "--quiet"], {}, check=False).returncode != 0:
        raise RunError("scoped-auto requires a clean real index")
    if run_git_env(root, ["rev-parse", "-q", "--verify", "MERGE_HEAD"], {}, check=False).returncode == 0:
        raise RunError("scoped-auto is unavailable during an unresolved merge")
    sparse = run_git_env(root, ["config", "--bool", "core.sparseCheckout"], {}, check=False)
    if sparse.returncode == 0 and sparse.stdout.strip() == "true":
        raise RunError("scoped-auto is unavailable in a sparse checkout")
    if (root / ".gitmodules").exists():
        raise RunError("scoped-auto is unavailable when submodules are configured")
    if content_manifest_hash(paths, root) != expected_manifest:
        raise RunError("content manifest changed before commit preparation")
    return branch_result.stdout.strip()


def scoped_auto_commit(
    root: Path,
    base_commit: str,
    paths: list[str],
    run_id: str,
    identity: dict[str, str],
    expected_manifest: str,
) -> tuple[str, str]:
    """Commit exactly paths and journal every irreversible Git boundary."""
    branch_ref = _preflight(root, base_commit, paths, expected_manifest)
    now = utc_now()
    transaction: dict[str, Any] = {
        "schema_version": "rb-wiki-git-transaction/0.2",
        "run_id": run_id,
        "stage": "prepared",
        "base_commit": base_commit,
        "branch_ref": branch_ref,
        "expected_paths": sorted(set(paths)),
        "content_manifest": expected_manifest,
        "commit_hash": None,
        "tree_hash": None,
        "branch_head": None,
        "created_at": now,
        "updated_at": now,
        "error": None,
    }
    save_transaction(transaction, root)
    inject_fault("before-index-create")
    index_path = root / ".wiki_state" / "indexes" / f"{run_id}.index"
    ensure_safe_parent(index_path, root)
    index_path.parent.mkdir(parents=True, exist_ok=True)
    if index_path.exists():
        raise RunError("temporary run index already exists")
    index_env = {"GIT_INDEX_FILE": str(index_path)}
    branch_moved = False
    try:
        run_git_env(root, ["read-tree", base_commit], index_env)
        inject_fault("after-index-create")
        run_git_env(root, ["add", "-A", "--", *paths], index_env)
        inject_fault("after-staging")
        staged_output = run_git_env(
            root, ["diff", "--cached", "--name-only", "-z", base_commit], index_env
        ).stdout
        staged = sorted(path for path in staged_output.split("\0") if path)
        if staged != sorted(set(paths)):
            raise RunError(f"temporary index path mismatch: expected {sorted(set(paths))}, got {staged}")
        tree_hash = run_git_env(root, ["write-tree"], index_env).stdout.strip()
        inject_fault("after-tree-write")
        commit_env = {
            **index_env,
            "GIT_AUTHOR_NAME": identity["name"],
            "GIT_AUTHOR_EMAIL": identity["email"],
            "GIT_COMMITTER_NAME": identity["name"],
            "GIT_COMMITTER_EMAIL": identity["email"],
        }
        message = f"RB Wiki managed run {run_id}\n\nRB-Wiki-Run: {run_id}\n"
        commit = run_git_env(
            root, ["commit-tree", tree_hash, "-p", base_commit, "-m", message], commit_env, check=False
        )
        if commit.returncode != 0:
            raise RunError(f"git commit-tree failed: {commit.stderr.strip()}")
        commit_hash = commit.stdout.strip()
        advance(transaction, "commit-created", root, commit_hash=commit_hash, tree_hash=tree_hash)
        inject_fault("after-commit-create")
        cas = run_git_env(root, ["update-ref", branch_ref, commit_hash, base_commit], {}, check=False)
        if cas.returncode != 0:
            raise RunError("branch compare-and-swap failed; HEAD was not moved")
        branch_moved = True
        advance(transaction, "branch-moved", root, branch_head=commit_hash)
        inject_fault("after-cas")
        run_git_env(root, ["read-tree", commit_hash], {})
        advance(transaction, "index-refreshed", root)
        inject_fault("after-index-refresh")
        return commit_hash, tree_hash
    except Exception as exc:
        if branch_moved:
            transaction["error"] = str(exc)
            transaction["updated_at"] = utc_now()
            try:
                save_transaction(transaction, root)
            except Exception:
                pass
            raise CommittedRecoveryRequired(
                f"commit {transaction['commit_hash']} moved {branch_ref}; recovery is required: {exc}",
                str(transaction["commit_hash"]),
                str(transaction["tree_hash"]),
                transaction["stage"],
            ) from exc
        raise
    finally:
        if index_path.exists():
            index_path.unlink()


def _commit_manifest(root: Path, commit_hash: str, paths: list[str]) -> str:
    items: list[str] = []
    for relative in sorted(path for path in paths if not path.startswith("reports/")):
        exists = subprocess.run(
            ["git", "cat-file", "-e", f"{commit_hash}:{relative}"], cwd=root, check=False,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        ).returncode == 0
        if exists:
            content = subprocess.run(
                ["git", "show", f"{commit_hash}:{relative}"], cwd=root, check=True, capture_output=True
            ).stdout
            digest = hashlib.sha256(content).hexdigest()
        else:
            digest = "deleted"
        items.append(f"{relative}\0{digest}")
    return hashlib.sha256("\n".join(items).encode("utf-8")).hexdigest()


def verify_recovery_evidence(root: Path, transaction: dict[str, Any]) -> None:
    commit_hash = transaction["commit_hash"]
    branch = run_git_env(root, ["rev-parse", transaction["branch_ref"]], {}).stdout.strip()
    if branch != commit_hash:
        raise RunError("recovery rejected: target branch no longer points at the recorded commit")
    parent = run_git_env(root, ["rev-parse", f"{commit_hash}^"], {}).stdout.strip()
    if parent != transaction["base_commit"]:
        raise RunError("recovery rejected: commit parent does not match the recorded base")
    tree = run_git_env(root, ["rev-parse", f"{commit_hash}^{{tree}}"], {}).stdout.strip()
    if tree != transaction["tree_hash"]:
        raise RunError("recovery rejected: commit tree does not match the transaction")
    message = run_git_env(root, ["show", "-s", "--format=%B", commit_hash], {}).stdout
    trailers = [line.strip() for line in message.splitlines() if line.startswith("RB-Wiki-Run:")]
    if trailers != [f"RB-Wiki-Run: {transaction['run_id']}"]:
        raise RunError("recovery rejected: commit has missing, ambiguous, or wrong run trailer")
    changed = sorted(
        path for path in run_git_env(
            root, ["diff-tree", "--no-commit-id", "--name-only", "-r", commit_hash], {}
        ).stdout.splitlines() if path
    )
    if changed != transaction["expected_paths"]:
        raise RunError("recovery rejected: committed paths differ from transaction intent")
    if _commit_manifest(root, commit_hash, changed) != transaction["content_manifest"]:
        raise RunError("recovery rejected: committed content manifest differs from transaction intent")


def discover_branch_movement(root: Path, transaction: dict[str, Any]) -> None:
    """Durably catch up a commit-created journal when CAS succeeded before its write."""
    if transaction["stage"] != "commit-created":
        return
    branch = run_git_env(root, ["rev-parse", transaction["branch_ref"]], {}).stdout.strip()
    if branch != transaction["commit_hash"]:
        raise RunError("recovery rejected: commit-created transaction has no exact branch-movement evidence")
    transaction["branch_head"] = transaction["commit_hash"]
    advance(transaction, "branch-moved", root)
    verify_recovery_evidence(root, transaction)


def refresh_index_for_recovery(root: Path, transaction: dict[str, Any]) -> None:
    discover_branch_movement(root, transaction)
    verify_recovery_evidence(root, transaction)
    if TRANSACTION_STAGES.index(transaction["stage"]) < TRANSACTION_STAGES.index("index-refreshed"):
        run_git_env(root, ["read-tree", transaction["commit_hash"]], {})
        advance(transaction, "index-refreshed", root)
