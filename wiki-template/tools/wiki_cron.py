#!/usr/bin/env python3
"""Cron-friendly entrypoints for LLM-wiki inbox and maintenance runs."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

sys.dont_write_bytecode = True

from ingest import SUPPORTED_SUFFIXES, ingest_one, write_ingest_report
from authority import load_runtime_policy
from run_lib import ContractError, RunError, git_base_commit
from semantic_protocol import load_base_json, validate_acquisition
from run_store import load_runtime_record
from wiki_run import execute_run, finish_session, load_session, start_session, terminate_session
from wiki_lib import ROOT


def inject_cron_fault(stage: str) -> None:
    requested = {
        item.strip() for item in os.environ.get("RB_WIKI_CRON_FAULT_STAGE", "").split(",") if item.strip()
    }
    if stage in requested:
        raise OSError(f"injected cron fault at {stage}")

def run_tool(*args: str) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    try:
        completed = subprocess.run(
            [sys.executable, *args],
            cwd=ROOT,
            env=env,
            text=True,
            capture_output=True,
            check=False,
            timeout=300,
        )
    except subprocess.TimeoutExpired as exc:
        return 124, f"{' '.join(args)} exceeded 300 seconds: {exc}"
    return completed.returncode, (completed.stdout + completed.stderr).strip()


def inbox_files() -> list[Path]:
    inbox = ROOT / "inbox"
    return sorted(path for path in inbox.iterdir() if path.is_file() and path.name != ".gitkeep")


def root_relative(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return path.name


def acquisition_handoff(acquisition_id: str | None) -> list[str] | None:
    if acquisition_id is None:
        return None
    if not acquisition_id or any(character not in "abcdefghijklmnopqrstuvwxyz0123456789-" for character in acquisition_id):
        raise ContractError("acquisition ID must use lowercase letters, digits, and hyphens")
    record = load_base_json(
        git_base_commit(ROOT),
        f"reports/acquisitions/{acquisition_id}.json",
        "acquisition-result",
        ROOT,
        expected_identity=("acquisition_id", acquisition_id),
    )
    validate_acquisition(record, record["run_id"], ROOT)
    if record["acquisition_id"] != acquisition_id or record["preservation_state"] != "inbox-staged":
        raise ContractError("acquisition handoff identity/state is not ready for ingest")
    candidates = {item["candidate_id"]: item for item in record["candidates"]}
    names: list[str] = []
    for candidate_id in record["selected"]:
        locator = candidates[candidate_id]["locator"]
        if not locator.startswith("inbox:"):
            raise ContractError("selected acquisition locator must use inbox:FILENAME")
        name = locator.removeprefix("inbox:")
        if not name or Path(name).name != name or "/" in name or "\\" in name:
            raise ContractError("selected acquisition locator is not a safe direct inbox filename")
        names.append(name)
    return sorted(names)


def inbox_sweep(authority_id: str, acquisition_id: str | None = None) -> int:
    inject_cron_fault("acquisition-handoff-load")
    expected_names = acquisition_handoff(acquisition_id)
    envelope = start_session(ROOT, "ingest", "scheduled-propose", authority_id)
    run_id, token = envelope["run_id"], envelope["run_token"]
    previous_controller = os.environ.get("RB_WIKI_RUN_CONTROLLER")
    os.environ["RB_WIKI_RUN_CONTROLLER"] = "1"
    try:
        inject_cron_fault("after-session-start")
        inject_cron_fault("policy-load")
        _manifest, policy = load_runtime_policy(ROOT)
        limits = policy["ingest_limits"]
        inject_cron_fault("inbox-enumeration")
        files = inbox_files()
        if expected_names is not None and sorted(path.name for path in files) != expected_names:
            raise RunError(
                "acquisition handoff mismatch: inbox files do not exactly match the committed selection"
            )
        if not files:
            inject_cron_fault("empty-inbox-finish")
            code, record = finish_session(ROOT, run_id, token, ["quick-lint=pass"])
            inject_cron_fault("terminal-report-rendering")
            print(f"{record['state']}: {run_id}; inbox is empty")
            return code
        results: list[dict] = []
        failures: list[str] = []
        if len(files) > limits["max_files"]:
            failures.append(f"inbox file count exceeds {limits['max_files']}")
        else:
            for path in files:
                allow_preservation = "preserve-unsupported" in envelope["permitted_actions"]
                if path.suffix.lower() not in SUPPORTED_SUFFIXES and not allow_preservation:
                    failures.append(
                        f"{path.relative_to(ROOT).as_posix()}: unsupported capability for suffix {path.suffix or '<none>'}"
                    )
                    continue
                try:
                    inject_cron_fault("per-file-ingest")
                    results.append(
                        ingest_one(
                            path,
                            run_id,
                            limits["max_file_bytes"],
                            allow_preservation_only=allow_preservation,
                        )
                    )
                except Exception as exc:
                    failures.append(f"{path.relative_to(ROOT).as_posix()}: {exc}")
        inject_cron_fault("report-write")
        write_ingest_report(run_id, results, failures, acquisition_id)
        if failures:
            raise RunError("; ".join(failures))
        inject_cron_fault("lint-subprocess")
        lint_code, lint_output = run_tool("tools/lint.py", "--quick", "--no-report")
        check = "quick-lint=pass" if lint_code == 0 else "quick-lint=fail"
        inject_cron_fault("finish")
        code, record = finish_session(ROOT, run_id, token, [check])
        inject_cron_fault("terminal-report-rendering")
        print(f"{record['state']}: {run_id}; {lint_output}")
        return code
    except Exception as exc:
        try:
            try:
                current = load_session(run_id, ROOT)["record"]
            except Exception:
                current = load_runtime_record(ROOT, run_id)
            if current["state"] == "committed-recovery-required":
                print(f"recovery required: {run_id} ({current['commit_hash']})", file=sys.stderr)
                return 5
            if current["state"] in {
                "completed", "blocked", "failed", "cancelled", "manual-commit-required", "approval-required"
            }:
                print(f"{current['state']}: {run_id} ({exc})", file=sys.stderr)
                return 0 if current["state"] == "completed" else 1
            record = terminate_session(ROOT, run_id, token, "failed", str(exc))
            inject_cron_fault("after-terminate")
            inject_cron_fault("terminal-report-rendering")
            print(f"failed: {record['run_id']} ({exc})")
        except Exception as termination_error:
            print(f"failed: {run_id} ({exc}); terminal reporting failed: {termination_error}", file=sys.stderr)
        return 1
    finally:
        if previous_controller is None:
            os.environ.pop("RB_WIKI_RUN_CONTROLLER", None)
        else:
            os.environ["RB_WIKI_RUN_CONTROLLER"] = previous_controller


def maintenance(authority_id: str, full: bool = False) -> int:
    code, record = execute_run(
        ROOT,
        "maintain",
        "scheduled-propose",
        authority_id,
        full=full,
    )
    print(f"{record['state']}: {record['run_id']} ({record['result']})")
    if record.get("error"):
        print(record["error"], file=sys.stderr)
    return code


def main(argv: list[str]) -> int:
    if len(argv) < 2 or argv[1] not in {"inbox", "nightly", "weekly"}:
        print(
            "usage: python3 tools/wiki_cron.py "
            "inbox --authority ID [--acquisition-id ID] | nightly --authority ID | weekly --authority ID"
        )
        return 1
    if argv[1] == "inbox":
        if len(argv) not in {4, 6} or argv[2] != "--authority" or (len(argv) == 6 and argv[4] != "--acquisition-id"):
            print("FAIL: inbox requires --authority ID and optionally --acquisition-id ID")
            return 1
        return inbox_sweep(argv[3], argv[5] if len(argv) == 6 else None)
    if len(argv) != 4 or argv[2] != "--authority":
        print(f"FAIL: {argv[1]} requires --authority ID")
        return 1
    return maintenance(argv[3], full=argv[1] == "weekly")


if __name__ == "__main__":
    sys.exit(main(sys.argv))
