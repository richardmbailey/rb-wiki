#!/usr/bin/env python3
"""Cron-friendly entrypoints for LLM-wiki inbox and maintenance runs."""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True

from ingest import SUPPORTED_SUFFIXES, ingest_one, write_ingest_report
from authorised_apply import (
    preflight_session_candidate,
    select_authorised_candidate,
    write_session_payload,
)
from authority import load_runtime_policy
from run_lib import ContractError, RunError, git_base_commit
from semantic_protocol import load_base_json, validate_acquisition
from run_store import load_runtime_record
from wiki_run import execute_run, finish_session, load_session, start_session, terminate_session
from wiki_lib import ROOT


TERMINAL_EXIT_CODES = {
    "completed": 0,
    "blocked": 2,
    "failed": 1,
    "cancelled": 1,
    "manual-commit-required": 3,
    "approval-required": 4,
}


def inject_cron_fault(stage: str) -> None:
    requested = {
        item.strip() for item in os.environ.get("RB_WIKI_CRON_FAULT_STAGE", "").split(",") if item.strip()
    }
    if stage in requested:
        raise OSError(f"injected cron fault at {stage}")

def inbox_files() -> list[Path]:
    inbox = ROOT / "inbox"
    return sorted(path for path in inbox.iterdir() if path.is_file() and path.name != ".gitkeep")


def root_relative(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return path.name


def fail_owned_session(run_id: str, token: str, error: Exception) -> int:
    """Preserve an existing terminal/recovery outcome or fail one live session once."""
    try:
        try:
            current = load_session(run_id, ROOT)["record"]
        except Exception:
            current = load_runtime_record(ROOT, run_id)
        if current["state"] == "committed-recovery-required":
            print(
                f"recovery required: {run_id} ({current['commit_hash']}); {current['next_action']}",
                file=sys.stderr,
            )
            return 5
        if current["state"] in TERMINAL_EXIT_CODES:
            print(
                f"{current['state']}: {run_id} ({error}); {current['next_action']}",
                file=sys.stderr,
            )
            return TERMINAL_EXIT_CODES[current["state"]]
        record = terminate_session(ROOT, run_id, token, "failed", str(error))
        inject_cron_fault("after-terminate")
        inject_cron_fault("terminal-report-rendering")
        print(f"failed: {record['run_id']} ({error}); {record['next_action']}", file=sys.stderr)
        return 1
    except Exception as termination_error:
        print(
            f"failed: {run_id} ({error}); terminal reporting failed: {termination_error}",
            file=sys.stderr,
        )
        return 1


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
            code, record = finish_session(ROOT, run_id, token, [])
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
        inject_cron_fault("controller-lint")
        inject_cron_fault("finish")
        code, record = finish_session(ROOT, run_id, token, [])
        inject_cron_fault("terminal-report-rendering")
        quick_lint = next(item for item in record["checks"] if item["check_id"] == "quick-lint")
        print(f"{record['state']}: {run_id}; {quick_lint['summary']}")
        return code
    except Exception as exc:
        return fail_owned_session(run_id, token, exc)
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


def apply_once(authority_id: str) -> int:
    """Select and apply at most one eligible committed proposal."""
    selection = select_authorised_candidate(ROOT, authority_id)
    for rejected in selection.rejected:
        print(f"rejected proposal {rejected.proposal_id}: {rejected.reason}", file=sys.stderr)
    candidate = selection.candidate
    if candidate is None:
        if selection.rejected:
            print("failed: no eligible committed proposal", file=sys.stderr)
            return 1
        print("completed: no committed proposals are waiting for this authority")
        return 0
    envelope = start_session(
        ROOT,
        candidate.lane,
        "authorised-autonomous-apply",
        authority_id,
        candidate.proposal["proposal_id"],
        candidate.approval_id,
    )
    run_id, token = envelope["run_id"], envelope["run_token"]
    try:
        inject_cron_fault("apply-after-session-start")
        session_candidate = preflight_session_candidate(load_session(run_id, ROOT), ROOT)
        inject_cron_fault("apply-before-write")
        write_session_payload(ROOT, run_id, session_candidate)
        inject_cron_fault("apply-after-write")
        inject_cron_fault("apply-finish")
        code, record = finish_session(ROOT, run_id, token, [])
        inject_cron_fault("terminal-report-rendering")
        print(
            f"{record['state']}: {run_id}; proposal {candidate.proposal['proposal_id']}; "
            f"{record['next_action']}"
        )
        return code
    except Exception as exc:
        return fail_owned_session(run_id, token, exc)


def main(argv: list[str]) -> int:
    if len(argv) < 2 or argv[1] not in {"apply", "inbox", "nightly", "weekly"}:
        print(
            "usage: python3 tools/wiki_cron.py "
            "apply --authority ID | inbox --authority ID [--acquisition-id ID] | "
            "nightly --authority ID | weekly --authority ID"
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
    try:
        if argv[1] == "apply":
            return apply_once(argv[3])
        return maintenance(argv[3], full=argv[1] == "weekly")
    except (ContractError, RunError, OSError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
