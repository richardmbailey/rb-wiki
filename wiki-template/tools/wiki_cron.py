#!/usr/bin/env python3
"""Cron-friendly entrypoints for LLM-wiki inbox and maintenance runs."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

sys.dont_write_bytecode = True

from source_registry import parse_registry, registered_entry_complete
from wiki_lib import REPORTS_DIR, ROOT, run_timestamp_utc, sha256_file, today_utc, unique_sibling_path

SUPPORTED_SUFFIXES = {".md", ".markdown", ".txt", ".text"}


def run_tool(*args: str) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    completed = subprocess.run(
        [sys.executable, *args],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    return completed.returncode, (completed.stdout + completed.stderr).strip()


def write_report(kind: str, lines: list[str]) -> Path:
    report_dir = REPORTS_DIR / ("ingest" if kind == "inbox" else "review")
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = unique_sibling_path(report_dir / f"{run_timestamp_utc()}-{kind}.md")
    report_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return report_path


def inbox_files() -> list[Path]:
    inbox = ROOT / "inbox"
    return sorted(path for path in inbox.iterdir() if path.is_file() and path.name != ".gitkeep")


def root_relative(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
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


def move_to_processed(path: Path) -> Path:
    target = processed_target(path)
    shutil.move(str(path), str(target))
    return target


def inbox_sweep() -> int:
    registry_by_hash = {entry.get("hash_sha256"): entry for entry in parse_registry() if entry.get("hash_sha256")}
    supported: list[Path] = []
    unsupported: list[Path] = []
    duplicates: list[Path] = []

    for path in inbox_files():
        if path.suffix.lower() not in SUPPORTED_SUFFIXES:
            unsupported.append(path)
            continue
        digest = sha256_file(path)
        if digest in registry_by_hash:
            if registered_entry_complete(registry_by_hash[digest]):
                duplicates.append(path)
            else:
                supported.append(path)
            continue
        supported.append(path)

    lines = [
        f"# Inbox Sweep - {today_utc()}",
        "",
        "# Summary",
        "",
        f"- Supported files routed through ingest: {len(supported)}",
        f"- Already registered complete files moved out of inbox: {len(duplicates)}",
        f"- Unsupported files needing review: {len(unsupported)}",
        "",
    ]

    exit_code = 0
    if supported:
        command = ["tools/ingest.py", *[root_relative(path) for path in supported]]
        code, output = run_tool(*command)
        exit_code = max(exit_code, code)
        lines.extend(["# Ingest Output", "", "```text", output or "(no output)", "```", ""])
        lint_code, lint_output = run_tool("tools/lint.py", "--quick")
        exit_code = max(exit_code, lint_code)
        lines.extend(["# Quick Lint Output", "", "```text", lint_output or "(no output)", "```", ""])
    else:
        lines.extend(["# Ingest Output", "", "No new supported inbox files to ingest.", ""])

    if unsupported:
        lines.append("# Unsupported Files")
        lines.append("")
        for path in unsupported:
            lines.append(f"- `{path.relative_to(ROOT).as_posix()}`")
        lines.append("")

    if duplicates:
        lines.append("# Already Registered Complete Files Moved To Processed")
        lines.append("")
        for path in duplicates:
            moved_to = move_to_processed(path)
            lines.append(
                f"- Moved `{path.relative_to(ROOT).as_posix()}` to "
                f"`{moved_to.relative_to(ROOT).as_posix()}`."
            )
        lines.append("")

    report = write_report("inbox", lines)
    print(f"Wrote {report.relative_to(ROOT).as_posix()}")
    return exit_code


def maintenance(kind: str, full: bool = False) -> int:
    lines = [
        f"# {'Weekly Clean' if full else 'Nightly Maintenance'} - {today_utc()}",
        "",
        "# Summary",
        "",
    ]
    commands = [
        ["tools/source_registry.py", "validate"],
        ["tools/build_index.py"],
        ["tools/build_graph.py"],
        ["tools/validate_frontmatter.py"],
        ["tools/check_reserved_files.py"],
        ["tools/check_links.py"],
        ["tools/word_count.py"],
        ["tools/detect_duplicates.py"],
        ["tools/lint.py", "--full" if full else "--quick"],
    ]

    exit_code = 0
    for command in commands:
        code, output = run_tool(*command)
        exit_code = max(exit_code, code)
        lines.extend([f"## `{' '.join(command)}`", "", "```text", output or "(no output)", "```", ""])

    report = write_report(kind, lines)
    print(f"Wrote {report.relative_to(ROOT).as_posix()}")
    return exit_code


def main(argv: list[str]) -> int:
    if len(argv) != 2 or argv[1] not in {"inbox", "nightly", "weekly"}:
        print("usage: python3 tools/wiki_cron.py inbox | nightly | weekly")
        return 1
    if argv[1] == "inbox":
        return inbox_sweep()
    if argv[1] == "nightly":
        return maintenance("nightly-maintenance", full=False)
    return maintenance("weekly-clean", full=True)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
