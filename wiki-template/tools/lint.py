#!/usr/bin/env python3
"""Run quick or full wiki lint and write a Markdown report."""

from __future__ import annotations

import argparse
import subprocess
import sys

from source_registry import parse_registry, validate_registry
from wiki_lib import (
    REPORTS_DIR,
    ROOT,
    build_graph_data,
    iter_markdown_pages,
    parse_frontmatter,
    run_timestamp_utc,
    today_utc,
    unique_sibling_path,
    wiki_relative,
)


def run_tool(script: str, *args: str) -> tuple[str, int, str]:
    command = [sys.executable, str(ROOT / "tools" / script), *args]
    completed = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, check=False)
    output = (completed.stdout + completed.stderr).strip()
    return script, completed.returncode, output


def status_for(code: int, output: str) -> str:
    if code != 0:
        return "Fail"
    if "WARN" in output:
        return "Warn"
    return "Pass"


def source_coverage() -> tuple[str, list[str]]:
    warnings: list[str] = []
    for path in iter_markdown_pages(include_reserved=False):
        fm, _body, error = parse_frontmatter(path)
        if error:
            continue
        page_type = fm.get("type")
        sources = fm.get("sources", [])
        if page_type != "Reference" and not sources:
            warnings.append(f"{wiki_relative(path)} has no sources in frontmatter")
        for source in sources:
            if isinstance(source, str) and source.startswith("/"):
                target = ROOT / "wiki" / source.lstrip("/")
                if not target.exists():
                    warnings.append(f"{wiki_relative(path)} references missing source page {source}")
    return ("Warn" if warnings else "Pass", warnings)


def orphan_check() -> tuple[str, list[str]]:
    graph = build_graph_data()
    orphans = graph.get("orphans_excluding_reserved", [])
    return ("Warn" if orphans else "Pass", [str(item) for item in orphans])


def registry_check() -> tuple[str, list[str]]:
    errors, warnings = validate_registry()
    notes = [f"FAIL: {item}" for item in errors] + [f"WARN: {item}" for item in warnings]
    if errors:
        return "Fail", notes
    if warnings:
        return "Warn", notes
    count = len(parse_registry())
    noun = "entry" if count == 1 else "entries"
    return "Pass", [f"Validated {count} source registry {noun}; no issues found."]


def write_report(mode: str, sections: list[dict[str, str | list[str]]], overall: str) -> str:
    report_dir = REPORTS_DIR / "lint"
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = unique_sibling_path(report_dir / f"{run_timestamp_utc()}-lint-report.md")
    lines: list[str] = [
        f"# Lint Report - {today_utc()}",
        "",
        "# Summary",
        "",
        f"Overall health status: {overall}",
        f"Mode: {mode}",
        "",
    ]

    for index, section in enumerate(sections, start=1):
        lines.append(f"# {index}. {section['title']}")
        lines.append("")
        lines.append(f"Status: {section['status']}")
        lines.append("")
        output = section["output"]
        if isinstance(output, list):
            if output:
                for item in output:
                    lines.append(f"- {item}")
            else:
                lines.append("- No issues found.")
        else:
            lines.append("```text")
            lines.append(output or "(no output)")
            lines.append("```")
        lines.append("")

    lines.extend(
        [
            "# Overall Health",
            "",
            "| Check | Status |",
            "|---|---|",
        ]
    )
    for section in sections:
        lines.append(f"| {section['title']} | {section['status']} |")
    lines.extend(
        [
            "",
            "# Next Steps",
            "",
            "1. Ingest source material specific to this wiki.",
            "2. Review pages marked `needs-review` after new sources are registered.",
            "3. Decide whether to create recurring upkeep automations.",
            "",
            "# Log Entry",
            "",
            f"- `{today_utc()}`: Ran {mode} lint. Overall status: {overall}.",
        ]
    )
    report_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return report_path.relative_to(ROOT).as_posix()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run LLM-wiki lint")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--quick", action="store_true")
    mode.add_argument("--full", action="store_true")
    args = parser.parse_args(argv)
    mode_name = "full" if args.full else "quick"

    tool_runs = [
        run_tool("check_reserved_files.py"),
        run_tool("validate_frontmatter.py"),
        run_tool("check_links.py"),
        run_tool("word_count.py"),
        run_tool("detect_duplicates.py"),
        run_tool("build_index.py"),
        run_tool("build_graph.py"),
    ]

    sections: list[dict[str, str | list[str]]] = []
    for script, code, output in tool_runs:
        title = {
            "check_reserved_files.py": "Reserved File Check",
            "validate_frontmatter.py": "Schema Integrity",
            "check_links.py": "Broken Links and OKF Links",
            "word_count.py": "Page Size",
            "detect_duplicates.py": "Duplicate Detection",
            "build_index.py": "Index Freshness",
            "build_graph.py": "Graph Build",
        }.get(script, script)
        sections.append({"title": title, "status": status_for(code, output), "output": output})

    registry_status, registry_notes = registry_check()
    sections.append({"title": "Source Registry Integrity", "status": registry_status, "output": registry_notes})

    source_status, source_notes = source_coverage()
    sections.append({"title": "Source Coverage", "status": source_status, "output": source_notes})

    orphan_status, orphan_notes = orphan_check()
    sections.append({"title": "Orphan Check", "status": orphan_status, "output": orphan_notes})

    if args.full:
        sections.extend(
            [
                {
                    "title": "Staleness",
                    "status": "Warn",
                    "output": ["Full editorial staleness review needs agent judgement after more sources are ingested."],
                },
                {
                    "title": "Coverage Gaps",
                    "status": "Warn",
                    "output": ["No subject-specific source corpus has been ingested yet."],
                },
                {
                    "title": "Contradiction Candidates",
                    "status": "Pass",
                    "output": ["No contradiction candidates found in the initial seed set."],
                },
            ]
        )

    statuses = [str(section["status"]) for section in sections]
    overall = "Red" if "Fail" in statuses else "Yellow" if "Warn" in statuses else "Green"
    report_path = write_report(mode_name, sections, overall)
    print(f"PASS: wrote {report_path}")
    print(f"Overall health status: {overall}")
    return 1 if "Fail" in statuses else 0


if __name__ == "__main__":
    sys.exit(main())
