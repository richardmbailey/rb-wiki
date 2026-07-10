#!/usr/bin/env python3
"""Ingest supported source files from inbox into the source registry."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

from pdf_extract import PdfExtractionResult, ensure_pdf_text_derivative, is_pdf_path
from source_registry import add_source
from wiki_lib import REPORTS_DIR, ROOT, now_utc, run_timestamp_utc, today_utc, unique_sibling_path

SUPPORTED_SUFFIXES = {".md", ".markdown", ".txt", ".text", ".pdf"}


def title_from_source_id(source_id: str) -> str:
    parts = source_id.split("-")
    if len(parts) > 3 and all(part.isdigit() for part in parts[:3]):
        parts = parts[3:]
    return " ".join(part.capitalize() for part in parts)


def iter_input_files(paths: list[Path]) -> list[Path]:
    files: list[Path] = []
    for path in paths:
        if path.is_dir():
            files.extend(sorted(item for item in path.iterdir() if item.is_file() and item.name != ".gitkeep"))
        elif path.is_file():
            files.append(path)
    return files


def is_direct_inbox_file(path: Path) -> bool:
    inbox = (ROOT / "inbox").resolve()
    resolved = path.resolve()
    return resolved.parent == inbox


def display_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(ROOT).as_posix()
    except ValueError:
        return path.name


def processed_target(path: Path) -> Path:
    processed_dir = ROOT / "inbox" / "processed" / today_utc()
    processed_dir.mkdir(parents=True, exist_ok=True)
    target = processed_dir / path.name
    if not target.exists():
        return target
    stem = path.stem
    suffix = path.suffix
    index = 2
    while True:
        candidate = processed_dir / f"{stem}-{index}{suffix}"
        if not candidate.exists():
            return candidate
        index += 1


def move_processed_inbox_file(path: Path) -> Path | None:
    if not path.exists() or not is_direct_inbox_file(path):
        return None
    target = processed_target(path)
    shutil.move(str(path), str(target))
    return target


def create_reference_page(
    entry: dict[str, str],
    source_path: Path,
    pdf_extraction: PdfExtractionResult | None = None,
) -> tuple[Path, bool]:
    reference_path = ROOT / entry["reference_path"]
    if reference_path.exists():
        return reference_path, False

    title = title_from_source_id(entry["source_id"])
    timestamp = now_utc()
    date = today_utc()
    source_display = display_path(source_path)
    if pdf_extraction:
        description = f"Reference page for the ingested PDF source `{source_path.name}`."
        derived_field = f'derived_text: "{pdf_extraction.derived_path}"'
        extraction_fields = f"""extraction_status: "{pdf_extraction.status}"
extraction_method: "{pdf_extraction.method}"
extracted_text_chars: {pdf_extraction.char_count}"""
        extraction_section = f"""# Extraction Status

- Status: `{pdf_extraction.status}`
- Method: `{pdf_extraction.method}`
- Extracted text: `{pdf_extraction.derived_path or 'not available'}`
- Note: {pdf_extraction.note}

The PDF in `sources/raw/` remains the immutable source. Extracted text is a generated derivative for search and review only.
"""
    else:
        description = f"Reference page for the ingested source `{source_path.name}`."
        derived_field = 'derived_text: ""'
        extraction_fields = ""
        extraction_section = ""
    body = f"""---
type: Reference
title: "{title}"
description: "{description}"
resource: "{entry['raw_path']}"
tags: [reference, needs-review]
timestamp: {timestamp}

created: {date}
status: needs-review
profile: llm-wiki-profile/0.1
sources: []
confidence: low
source_id: "{entry['source_id']}"
source_type: {entry['source_type']}
hash_sha256: "{entry['hash_sha256']}"
date_published: unknown
date_ingested: {entry['date_ingested']}
authors: []
{derived_field}
{extraction_fields}
---

{description}

{extraction_section}

# Source Summary

Needs review. The raw source has been preserved and registered, but no source-level summary has been written yet.

# Key Claims

- Needs review.

# Extracted Concepts

- Needs review.

# Extracted Entities

- Needs review.

# Useful Passages

Needs review.

# Links Into Wiki

- [Wiki Overview](/overview.md)

# Change History

- `{date}`: Created by `tools/ingest.py` from `{source_display}`.
"""
    reference_path.parent.mkdir(parents=True, exist_ok=True)
    reference_path.write_text(body, encoding="utf-8")
    return reference_path, True


def run_tool(script: str, *args: str) -> tuple[int, str]:
    command = [sys.executable, str(ROOT / "tools" / script), *args]
    completed = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, check=False)
    output = (completed.stdout + completed.stderr).strip()
    return completed.returncode, output


def write_report(lines: list[str]) -> Path:
    report_dir = REPORTS_DIR / "ingest"
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = unique_sibling_path(report_dir / f"{run_timestamp_utc()}-ingest-report.md")
    report_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return report_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Ingest supported source files into the LLM-wiki")
    parser.add_argument("paths", nargs="+", help="Files or directories to ingest")
    parser.add_argument("--skip-validation", action="store_true")
    args = parser.parse_args(argv)

    input_files = iter_input_files([Path(item) for item in args.paths])
    report_lines = [
        f"# Ingest Report - {today_utc()}",
        "",
        "# Summary",
        "",
    ]

    processed = 0
    skipped = 0
    failed = 0
    processed_inbox_files: list[Path] = []
    for path in input_files:
        if path.suffix.lower() not in SUPPORTED_SUFFIXES:
            skipped += 1
            report_lines.append(f"- SKIP `{display_path(path)}`: unsupported suffix `{path.suffix}`.")
            continue
        try:
            entry, duplicate = add_source(path)
            pdf_extraction = None
            if is_pdf_path(path):
                pdf_extraction = ensure_pdf_text_derivative(entry, ROOT / entry["raw_path"])
                if pdf_extraction.status in {"failed", "no-text"}:
                    raise RuntimeError(f"PDF text extraction {pdf_extraction.status}: {pdf_extraction.note}")
            reference_path, created = create_reference_page(entry, path, pdf_extraction)
        except Exception as exc:
            failed += 1
            report_lines.append(f"- FAIL `{display_path(path)}`: {exc}")
            continue
        processed += 1
        state = "duplicate source" if duplicate else "new source"
        raw_state = "; restored missing raw source" if entry.pop("_raw_restored", "") == "true" else ""
        ref_state = "created reference" if created else "reference already existed"
        extraction_state = ""
        if pdf_extraction:
            extraction_state = (
                f"; PDF extraction `{pdf_extraction.status}`"
                + (f" -> `{pdf_extraction.derived_path}`" if pdf_extraction.derived_path else f": {pdf_extraction.note}")
            )
        report_lines.append(
            f"- OK `{display_path(path)}`: {state}{raw_state}; {ref_state}; "
            f"`{entry['source_id']}` -> `{entry['raw_path']}`{extraction_state}."
        )
        if is_direct_inbox_file(path):
            processed_inbox_files.append(path)

    report_lines.insert(4, f"Processed {processed} file(s); skipped {skipped} file(s); failed {failed} file(s).")
    report_lines.append("")
    report_lines.append("# Validation")
    report_lines.append("")

    exit_code = 1 if failed else 0
    if not args.skip_validation:
        validation_commands = [
            ("source_registry.py", "validate"),
            ("build_index.py",),
            ("build_graph.py",),
            ("validate_frontmatter.py",),
            ("check_reserved_files.py",),
            ("check_links.py",),
            ("word_count.py",),
            ("lint.py", "--quick"),
        ]
        for command in validation_commands:
            script, *script_args = command
            code, output = run_tool(script, *script_args)
            report_lines.append(f"## `{' '.join(command)}`")
            report_lines.append("")
            report_lines.append("```text")
            report_lines.append(output or "(no output)")
            report_lines.append("```")
            report_lines.append("")
            if code != 0:
                exit_code = code

    report_lines.append("# Processed Inbox Policy")
    report_lines.append("")
    if exit_code != 0 and processed_inbox_files:
        report_lines.append("Inbox files were not moved because ingest or validation failed.")
    elif args.skip_validation and processed_inbox_files:
        report_lines.append("Inbox files were not moved because validation was skipped.")
    elif processed_inbox_files:
        for path in processed_inbox_files:
            moved_to = move_processed_inbox_file(path)
            if moved_to:
                report_lines.append(
                    f"- Moved `{display_path(path)}` to "
                    f"`{display_path(moved_to)}`."
                )
    else:
        report_lines.append("No direct inbox files were eligible to move.")
    report_lines.append("")

    report_path = write_report(report_lines)
    print(f"PASS: wrote {report_path.relative_to(ROOT).as_posix()}")
    if skipped:
        print(f"WARN: skipped {skipped} unsupported file(s)")
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
