#!/usr/bin/env python3
"""Crash-safe, digest-keyed, idempotent source ingestion transitions."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import uuid
from pathlib import Path
from typing import Any

from pdf_extract import PdfExtractionResult, ensure_pdf_text_derivative, is_pdf_path
from provenance import validate_provenance
from authority import load_runtime_policy
from run_lib import (
    STATE_DIR,
    RunError,
    atomic_write_json,
    atomic_write_text,
    ensure_safe_parent,
    fsync_directory,
    symlink_component,
    utc_now,
    validate_contract,
)
from source_registry import SOURCE_FORMAT_CAPABILITIES, parse_registry, source_type_for, stable_source_id, upsert_entry
from wiki_lib import REPORTS_DIR, ROOT, now_utc, sha256_file, slugify, today_utc
from fs_safety import enumerate_regular_files

SUPPORTED_SUFFIXES = {suffix for suffix, capability in SOURCE_FORMAT_CAPABILITIES.items() if capability == "ingest"}
TRANSITIONS = ["captured", "raw-preserved", "registered", "reference-created", "validated", "inbox-archived"]
SAFE_FILENAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._ -]{0,199}$")
SAFE_DIGEST = re.compile(r"^[a-f0-9]{64}$")


class InjectedFailure(RuntimeError):
    pass


def journal_path(digest: str) -> Path:
    if not SAFE_DIGEST.fullmatch(digest):
        raise RunError("invalid source digest; expected 64 lowercase hexadecimal characters")
    return STATE_DIR / "sources" / f"{digest}.json"


def save_journal(record: dict[str, Any]) -> None:
    record["updated_at"] = utc_now()
    validate_contract(record, "source-transition", ROOT)
    atomic_write_json(journal_path(record["digest"]), record, ROOT)


def load_journal(digest: str) -> dict[str, Any]:
    path = journal_path(digest)
    unsafe = symlink_component(path, ROOT)
    if unsafe is not None:
        raise RunError(f"source transition journal path traverses a symlink: {unsafe}")
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RunError(f"cannot load source transition journal {digest}: {exc}") from exc
    validate_contract(record, "source-transition", ROOT)
    return record


def next_transition(record: dict[str, Any]) -> str | None:
    completed = set(record["completed_transitions"])
    return next((state for state in TRANSITIONS if state not in completed), None)


def complete_transition(record: dict[str, Any], state: str, fault_after: str | None) -> None:
    if state not in record["completed_transitions"]:
        record["completed_transitions"].append(state)
    record.update(state=state, outcome="in-progress", failed_transition=None, error=None)
    record.setdefault("last_run_transitions", []).append(state)
    record["next_transition"] = next_transition(record)
    save_journal(record)
    if fault_after == state:
        raise InjectedFailure(f"injected failure after {state}")


def validate_input(path: Path, max_file_bytes: int, allow_preservation_only: bool = False) -> tuple[int, int, str]:
    inbox_path = ROOT / "inbox"
    if inbox_path.is_symlink() or not inbox_path.is_dir():
        raise RunError("inbox/ must be a real directory beneath the wiki root")
    inbox = inbox_path.resolve()
    if path.is_symlink() or not path.is_file():
        raise RunError("input must be a regular non-symlink file")
    if path.resolve().parent != inbox:
        raise RunError("input must be a direct file beneath inbox/")
    if not SAFE_FILENAME.fullmatch(path.name):
        raise RunError("input filename contains unsafe characters or is too long")
    if path.suffix.lower() not in SUPPORTED_SUFFIXES and not allow_preservation_only:
        raise RunError(f"unsupported source type: {path.suffix.lower() or '<none>'}")
    stat = path.stat()
    if stat.st_size > max_file_bytes:
        raise RunError(f"input exceeds the {max_file_bytes}-byte size limit")
    return stat.st_size, stat.st_mtime_ns, sha256_file(path)


def capture(
    path: Path, parent_run_id: str, max_file_bytes: int, allow_preservation_only: bool = False
) -> dict[str, Any]:
    size, mtime_ns, digest = validate_input(path, max_file_bytes, allow_preservation_only)
    path = path.resolve()
    existing_entries = parse_registry()
    existing_journal = journal_path(digest)
    if existing_journal.exists():
        record = load_journal(digest)
        record["resume_count"] = int(record.get("resume_count", 0)) + 1
        record["last_run_transitions"] = []
        if path.exists() and (
            record.get("input_path") != path.relative_to(ROOT).as_posix()
            or "inbox-archived" in record["completed_transitions"]
        ):
            record.update(
                input_path=path.relative_to(ROOT).as_posix(),
                input_size=size,
                input_mtime_ns=mtime_ns,
                processed_path=None,
                planned_processed_path=None,
                parent_run_id=parent_run_id,
            )
            record["completed_transitions"] = [
                state for state in record["completed_transitions"] if state != "inbox-archived"
            ]
            record["state"] = record["completed_transitions"][-1]
            record.update(
                outcome="in-progress", failed_transition=None, error=None,
                next_transition=next_transition(record),
            )
            save_journal(record)
        return record
    source_id = stable_source_id(path, digest, existing_entries)
    suffix = path.suffix.lower() or ".txt"
    record = {
        "schema_version": "rb-wiki-source-transition/0.2",
        "digest": digest,
        "parent_run_id": parent_run_id,
        "input_path": path.relative_to(ROOT).as_posix(),
        "input_size": size,
        "input_mtime_ns": mtime_ns,
        "source_id": source_id,
        "suffix": suffix,
        "raw_path": f"sources/raw/{source_id}{suffix}",
        "reference_path": f"wiki/references/{source_id}.md",
        "derivative_path": None,
        "processed_path": None,
        "planned_processed_path": None,
        "access_level": (
            "preservation-only"
            if suffix not in SUPPORTED_SUFFIXES
            else "raw-only" if suffix == ".pdf" else "full-text"
        ),
        "state": "captured",
        "outcome": "in-progress",
        "completed_transitions": ["captured"],
        "failed_transition": None,
        "error": None,
        "next_transition": "raw-preserved",
        "captured_at": utc_now(),
        "updated_at": utc_now(),
        "resume_count": 0,
        "last_run_transitions": ["captured"],
    }
    save_journal(record)
    return record


def current_input(record: dict[str, Any]) -> Path | None:
    input_path = ROOT / record["input_path"]
    if symlink_component(input_path, ROOT) is None and input_path.is_file():
        return input_path
    planned = record.get("planned_processed_path")
    if planned:
        processed = ROOT / planned
        if symlink_component(processed, ROOT) is None and processed.is_file():
            return processed
    return None


def preserve_raw(record: dict[str, Any]) -> bool:
    raw = ROOT / record["raw_path"]
    ensure_safe_parent(raw, ROOT)
    if raw.exists():
        if raw.is_symlink() or not raw.is_file() or sha256_file(raw) != record["digest"]:
            raise RunError("existing raw path is not the captured immutable evidence")
        return False
    source = current_input(record)
    if source is None:
        raise RunError("captured input is unavailable; raw preservation cannot resume")
    before = source.stat()
    if before.st_size != record["input_size"] or sha256_file(source) != record["digest"]:
        raise RunError("captured input identity changed before raw preservation")
    raw.parent.mkdir(parents=True, exist_ok=True)
    temporary = raw.parent / f".{raw.name}.{uuid.uuid4().hex}.tmp"
    try:
        with source.open("rb") as reader, temporary.open("xb") as writer:
            while chunk := reader.read(1024 * 1024):
                writer.write(chunk)
            writer.flush()
            os.fsync(writer.fileno())
        if (
            os.environ.get("RB_WIKI_FAULT_INJECTION") == "1"
            and os.environ.get("RB_WIKI_TEST_MUTATE_INPUT_DURING_COPY") == "1"
        ):
            with source.open("ab") as mutator:
                mutator.write(b"changed-during-copy")
        after = source.stat()
        if (
            after.st_size != record["input_size"]
            or after.st_mtime_ns != record["input_mtime_ns"]
            or sha256_file(source) != record["digest"]
            or sha256_file(temporary) != record["digest"]
        ):
            raise RunError("captured input changed during raw preservation; recovery is required")
        try:
            os.link(temporary, raw)
        except FileExistsError:
            if sha256_file(raw) != record["digest"]:
                raise RunError("raw destination collision with different content")
        fsync_directory(raw.parent)
        return True
    finally:
        if temporary.exists():
            temporary.unlink()


def registry_entry(record: dict[str, Any], state: str) -> dict[str, Any]:
    return {
        "source_id": record["source_id"],
        "raw_path": record["raw_path"],
        "reference_path": record["reference_path"],
        "hash_sha256": record["digest"],
        "source_type": source_type_for(Path(record["raw_path"])),
        "date_ingested": record["captured_at"][:10],
        "date_published": "unknown",
        "status": "active",
        "ingest_state": state,
        "access_level": record["access_level"],
        "processed_path": record.get("processed_path"),
        "derivative_path": record.get("derivative_path"),
    }


def update_registry(record: dict[str, Any], state: str) -> dict[str, Any]:
    entry, _created = upsert_entry(registry_entry(record, state))
    return entry


def title_from_source_id(source_id: str) -> str:
    parts = source_id.split("-")
    return " ".join(part.capitalize() for part in (parts[3:] if len(parts) > 3 else parts))


def reference_text(record: dict[str, Any], extraction: PdfExtractionResult | None) -> str:
    title = title_from_source_id(record["source_id"])
    description = f"Reference page for the preserved source `{Path(record['input_path']).name}`."
    extraction_status = extraction.status if extraction else "not-applicable"
    extraction_note = extraction.note if extraction else "The source is directly text-readable."
    next_action = (
        "Obtain text through OCR or manual review before semantic integration."
        if record["access_level"] == "raw-only"
        else "Review and integrate the source semantically."
    )
    return f'''---
type: Reference
title: "{title}"
description: "{description}"
resource: "{record['raw_path']}"
tags: [reference, needs-review]
timestamp: {now_utc()}

created: {today_utc()}
status: needs-review
profile: llm-wiki-profile/0.2
sources: []
confidence: low
review_state: pending
review_priority: normal
consequence_tier: ordinary
source_id: "{record['source_id']}"
source_type: {source_type_for(Path(record['raw_path']))}
hash_sha256: "{record['digest']}"
date_published: unknown
date_ingested: {record['captured_at'][:10]}
authors: []
source_access_level: {record['access_level']}
derived_text: "{record.get('derivative_path') or ''}"
extraction_status: "{extraction_status}"
integration_state: unintegrated
assessment_state: unassessed
validated_at: {now_utc()}
---

{description}

# Access And Extraction

- Access level: `{record['access_level']}`
- Extraction status: `{extraction_status}`
- Note: {extraction_note}
- Next action: {next_action}

# Source Summary

Needs review. Raw evidence is preserved and provenance-validated; semantic integration is pending.

# Key Claims

- Needs review.

# Links Into Wiki

- [Wiki Overview](/overview.md)
'''


def create_reference(record: dict[str, Any]) -> bool:
    extraction: PdfExtractionResult | None = None
    if record["suffix"] == ".pdf":
        extraction = ensure_pdf_text_derivative(registry_entry(record, "registered"), ROOT / record["raw_path"])
        if extraction.derived_path:
            record["derivative_path"] = extraction.derived_path
        if extraction.status in {"failed", "no-text"}:
            record["access_level"] = "raw-only"
        else:
            record["access_level"] = "full-text"
    reference = ROOT / record["reference_path"]
    if reference.exists():
        return False
    atomic_write_text(reference, reference_text(record, extraction), ROOT)
    return True


def planned_archive(record: dict[str, Any]) -> Path:
    if record.get("planned_processed_path"):
        return ROOT / record["planned_processed_path"]
    source = ROOT / record["input_path"]
    directory = ROOT / "inbox" / "processed" / today_utc()
    ensure_safe_parent(directory / "placeholder", ROOT)
    directory.mkdir(parents=True, exist_ok=True)
    candidate = directory / source.name
    index = 2
    while candidate.exists():
        candidate = directory / f"{source.stem}-{index}{source.suffix}"
        index += 1
    record["planned_processed_path"] = candidate.relative_to(ROOT).as_posix()
    save_journal(record)
    return candidate


def archive_input(record: dict[str, Any]) -> bool:
    source = ROOT / record["input_path"]
    unsafe_source = symlink_component(source, ROOT)
    if unsafe_source is not None:
        raise RunError(f"inbox input path traverses a symlink: {unsafe_source}")
    target = planned_archive(record)
    if target.exists():
        if target.is_symlink() or sha256_file(target) != record["digest"]:
            raise RunError("planned processed destination contains different content")
        if source.exists():
            if sha256_file(source) != record["digest"]:
                raise RunError("inbox identity changed before archive completion")
            source.unlink()
            fsync_directory(source.parent)
        record["processed_path"] = target.relative_to(ROOT).as_posix()
        return False
    if not source.is_file() or source.is_symlink() or sha256_file(source) != record["digest"]:
        raise RunError("captured inbox input is unavailable or changed before archival")
    target.parent.mkdir(parents=True, exist_ok=True)
    os.link(source, target)
    fsync_directory(target.parent)
    source.unlink()
    fsync_directory(source.parent)
    record["processed_path"] = target.relative_to(ROOT).as_posix()
    return True


def run_transitions(record: dict[str, Any], fault_after: str | None = None) -> dict[str, Any]:
    try:
        entries = parse_registry()
        matching = next((entry for entry in entries if entry["hash_sha256"] == record["digest"]), None)
        if "raw-preserved" in record["completed_transitions"] and not (ROOT / record["raw_path"]).is_file():
            cutoff = TRANSITIONS.index("raw-preserved")
            record["completed_transitions"] = record["completed_transitions"][:cutoff]
        elif "registered" in record["completed_transitions"] and matching is None:
            cutoff = TRANSITIONS.index("registered")
            record["completed_transitions"] = record["completed_transitions"][:cutoff]
        elif "reference-created" in record["completed_transitions"] and not (ROOT / record["reference_path"]).is_file():
            cutoff = TRANSITIONS.index("reference-created")
            record["completed_transitions"] = record["completed_transitions"][:cutoff]
        record["state"] = record["completed_transitions"][-1]
        record.update(
            outcome="in-progress", failed_transition=None, error=None,
            next_transition=next_transition(record),
        )
        if "raw-preserved" not in record["completed_transitions"]:
            preserve_raw(record)
            complete_transition(record, "raw-preserved", fault_after)
        if "registered" not in record["completed_transitions"]:
            update_registry(record, "registered")
            complete_transition(record, "registered", fault_after)
        if "reference-created" not in record["completed_transitions"]:
            create_reference(record)
            update_registry(record, "reference-created")
            complete_transition(record, "reference-created", fault_after)
        if "validated" not in record["completed_transitions"]:
            errors = validate_provenance(record["source_id"])
            if errors:
                raise RunError("; ".join(errors))
            update_registry(record, "validated")
            complete_transition(record, "validated", fault_after)
        if "inbox-archived" not in record["completed_transitions"]:
            archive_input(record)
            update_registry(record, "inbox-archived")
            complete_transition(record, "inbox-archived", fault_after)
        final_errors = validate_provenance(record["source_id"])
        if final_errors:
            raise RunError("; ".join(final_errors))
        record.update(outcome="complete", next_transition=None, error=None, failed_transition=None)
        update_registry(record, "inbox-archived")
        save_journal(record)
        return record
    except Exception as exc:
        retry = next_transition(record) or TRANSITIONS[-1]
        record.update(
            outcome="recovery-required",
            failed_transition=retry,
            next_transition=retry,
            error=str(exc),
        )
        save_journal(record)
        if "registered" in record["completed_transitions"]:
            update_registry(record, "recovery-required")
        raise


def ingest_one(
    path: Path,
    parent_run_id: str,
    max_file_bytes: int,
    fault_after: str | None = None,
    allow_preservation_only: bool = False,
) -> dict[str, Any]:
    record = capture(path, parent_run_id, max_file_bytes, allow_preservation_only)
    if fault_after == "captured" and record["completed_transitions"] == ["captured"]:
        try:
            raise InjectedFailure("injected failure after captured")
        except InjectedFailure as exc:
            record.update(
                outcome="recovery-required", failed_transition="raw-preserved",
                next_transition="raw-preserved", error=str(exc),
            )
            save_journal(record)
            raise
    return run_transitions(record, fault_after)


def resume_digest(digest: str, fault_after: str | None = None) -> dict[str, Any]:
    record = load_journal(digest)
    record["resume_count"] = int(record.get("resume_count", 0)) + 1
    record["last_run_transitions"] = []
    save_journal(record)
    return run_transitions(record, fault_after)


def input_files(values: list[str]) -> list[Path]:
    files: list[Path] = []
    for value in values:
        path = Path(value)
        if path.is_dir() and not path.is_symlink() and path.resolve() == (ROOT / "inbox").resolve():
            files.extend(sorted(item for item in path.iterdir() if item.name != ".gitkeep"))
        else:
            files.append(path)
    return files


def write_ingest_report(
    run_id: str, results: list[dict[str, Any]], failures: list[str], acquisition_id: str | None = None
) -> Path:
    by_digest = {item["digest"]: item for item in results}
    state_sources = STATE_DIR / "sources"
    journal_paths = (
        enumerate_regular_files(ROOT, ".wiki_state/sources", ".json")
        if state_sources.exists() or state_sources.is_symlink()
        else []
    )
    for path in journal_paths:
        try:
            item = json.loads(path.read_text(encoding="utf-8"))
            validate_contract(item, "source-transition", ROOT)
        except (OSError, json.JSONDecodeError, RunError) as exc:
            raise RunError(f"cannot build ingest report from invalid transition {path.name}: {exc}") from exc
        if item.get("parent_run_id") == run_id:
            by_digest[item["digest"]] = item
    report_records = [by_digest[key] for key in sorted(by_digest)]
    report = {
        "schema_version": "rb-wiki-ingest-report/0.2",
        "run_id": run_id,
        "acquisition_id": acquisition_id,
        "created_at": utc_now(),
        "sources": [
            {
                "source_id": item["source_id"],
                "digest": item["digest"],
                "state": item["state"],
                "outcome": item["outcome"],
                "transitions": item["completed_transitions"],
                "artifacts": [item["raw_path"], item["reference_path"], item.get("derivative_path")],
                "processed_path": item.get("processed_path"),
                "next_action": item.get("next_transition") or (
                    "semantic integration required" if item["access_level"] == "raw-only" else "review source"
                ),
                "resumed": item.get("resume_count", 0) > 0,
                "transitions_this_run": item.get("last_run_transitions", []),
                "error": item.get("error"),
            }
            for item in report_records
        ],
        "failures": failures,
    }
    path = REPORTS_DIR / "ingest" / f"{run_id}.json"
    validate_contract(report, "ingest-report", ROOT)
    atomic_write_json(path, report, ROOT)
    return path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Recoverably ingest direct inbox sources")
    parser.add_argument("paths", nargs="*")
    parser.add_argument("--resume-digest")
    parser.add_argument("--run-id", default=os.environ.get("RB_WIKI_RUN_ID", f"manual-{uuid.uuid4().hex[:12]}"))
    parser.add_argument("--fault-after", choices=TRANSITIONS)
    args = parser.parse_args(argv)
    if os.environ.get("RB_WIKI_RUN_CONTROLLER") != "1":
        print("FAIL: mutating ingest must run through wiki_cron.py or an active wiki_run.py session")
        return 2
    if args.fault_after and os.environ.get("RB_WIKI_FAULT_INJECTION") != "1":
        parser.error("fault injection is disabled outside an explicit test environment")
    _manifest, policy = load_runtime_policy(ROOT)
    limits = policy.get("ingest_limits", {"max_files": 20, "max_file_bytes": 104857600})
    if args.resume_digest:
        try:
            record = resume_digest(args.resume_digest, args.fault_after)
        except Exception as exc:
            print(f"FAIL: {exc}")
            return 1
        print(json.dumps(record, sort_keys=True))
        return 0
    files = input_files(args.paths)
    if len(files) > limits["max_files"]:
        print(f"FAIL: input count exceeds {limits['max_files']}")
        return 1
    results: list[dict[str, Any]] = []
    failures: list[str] = []
    for path in files:
        try:
            results.append(
                ingest_one(
                    path,
                    args.run_id,
                    limits["max_file_bytes"],
                    args.fault_after,
                    allow_preservation_only=os.environ.get("RB_WIKI_ALLOW_PRESERVATION_ONLY") == "1",
                )
            )
        except Exception as exc:
            failures.append(f"{path}: {exc}")
    report = write_ingest_report(args.run_id, results, failures)
    print(f"wrote {report.relative_to(ROOT).as_posix()}")
    for failure in failures:
        print(f"FAIL: {failure}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
