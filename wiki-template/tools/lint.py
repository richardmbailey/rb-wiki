#!/usr/bin/env python3
"""Run deterministic wiki lint and emit contract-validated structured reports."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

sys.dont_write_bytecode = True

from capabilities import capability_snapshot
from provenance import validate_provenance
from authority import load_runtime_policy
from run_lib import (
    ContractError,
    atomic_write_json,
    atomic_write_text,
    parse_utc,
    validate_contract,
)
from source_registry import parse_registry, validate_registry
from wiki_lib import (
    REPORTS_DIR,
    ROOT,
    build_graph_data,
    iter_markdown_pages,
    parse_frontmatter,
    run_timestamp_utc,
    unique_sibling_path,
    wiki_relative,
)

OUTCOME_ORDER = {"pass": 0, "not_run": 0, "warn": 1, "fail": 2}
SEVERITY_ORDER = {"info": 0, "low": 1, "medium": 2, "high": 3, "critical": 4}


def check_result(
    check_id: str,
    title: str,
    outcome: str,
    severity: str = "info",
    disposition: str = "none",
    *,
    affected_paths: list[str] | None = None,
    source_ids: list[str] | None = None,
    evidence: list[str] | None = None,
    recommended_action: str = "",
) -> dict[str, Any]:
    result = {
        "check_id": check_id,
        "title": title,
        "outcome": outcome,
        "severity": severity,
        "disposition": disposition,
        "affected_paths": sorted(set(affected_paths or [])),
        "source_ids": sorted(set(source_ids or [])),
        "evidence": evidence or [],
        "recommended_action": recommended_action,
    }
    validate_contract(result, "check-result", ROOT)
    return result


def run_tool(script: str, *args: str) -> dict[str, Any]:
    command = [sys.executable, str(ROOT / "tools" / script), *args]
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    try:
        completed = subprocess.run(
            command,
            cwd=ROOT,
            env=env,
            text=True,
            capture_output=True,
            check=False,
            timeout=120,
        )
    except subprocess.TimeoutExpired:
        return check_result(
            script.removesuffix(".py").replace("_", "-"),
            script,
            "fail",
            "high",
            "fix",
            evidence=[f"{script} exceeded 120 seconds."],
            recommended_action="Inspect the deterministic tool for a hang before retrying.",
        )
    output = (completed.stdout + completed.stderr).strip()
    warned = completed.returncode == 0 and "WARN" in output
    outcome = "fail" if completed.returncode else "warn" if warned else "pass"
    details = {
        "check_reserved_files.py": ("reserved-files", "Reserved file integrity"),
        "validate_frontmatter.py": ("frontmatter", "Frontmatter integrity"),
        "check_links.py": ("local-links", "Local link integrity"),
        "word_count.py": ("page-size", "Page size"),
        "detect_duplicates.py": ("duplicates", "Deterministic duplicate detection"),
        "build_index.py": ("index-build", "Index build"),
        "build_graph.py": ("graph-build", "Graph build"),
    }
    check_id, title = details.get(script, (script.removesuffix(".py").replace("_", "-"), script))
    return check_result(
        check_id,
        title,
        outcome,
        "high" if outcome == "fail" else "medium" if outcome == "warn" else "info",
        "fix" if outcome in {"warn", "fail"} else "none",
        evidence=[output or "No issues reported."],
        recommended_action="Correct the deterministic errors and rerun lint." if outcome != "pass" else "",
    )


def registry_result() -> dict[str, Any]:
    errors, warnings = validate_registry()
    entries = parse_registry() if not errors else []
    outcome = "fail" if errors else "warn" if warnings else "pass"
    return check_result(
        "source-registry",
        "Source registry integrity",
        outcome,
        "critical" if errors else "medium" if warnings else "info",
        "fix" if outcome != "pass" else "none",
        affected_paths=["sources/_source_registry.yml"],
        source_ids=[str(item["source_id"]) for item in entries],
        evidence=errors + warnings + ([f"Validated {len(entries)} source registry entries."] if not errors else []),
        recommended_action="Reconcile registry entries with immutable raw evidence and Reference pages." if outcome != "pass" else "",
    )


def provenance_result() -> dict[str, Any]:
    errors = validate_provenance()
    return check_result(
        "provenance-chain",
        "Provenance and citation chain",
        "fail" if errors else "pass",
        "critical" if errors else "info",
        "human-required" if errors else "none",
        evidence=errors or ["All registered raw evidence, References, and ordinary-page citations reconcile."],
        recommended_action="Reconcile the cited Reference, registry identity, and immutable raw evidence before relying on affected claims." if errors else "",
    )


def source_coverage_result() -> dict[str, Any]:
    paths: list[str] = []
    for path in iter_markdown_pages(include_reserved=False):
        frontmatter, _body, error = parse_frontmatter(path)
        if not error and frontmatter.get("type") != "Reference" and not frontmatter.get("sources", []):
            paths.append(wiki_relative(path))
    return check_result(
        "source-coverage",
        "Ordinary-page source coverage",
        "warn" if paths else "pass",
        "medium" if paths else "info",
        "agent-required" if paths else "none",
        affected_paths=paths,
        evidence=[f"{path} has no source citation." for path in paths] or ["All ordinary pages declare at least one source."],
        recommended_action="Add a registered Reference citation or explicitly justify the uncited page." if paths else "",
    )


def orphan_result() -> dict[str, Any]:
    graph = build_graph_data()
    ordinary: list[str] = []
    for item in graph.get("orphans_excluding_reserved", []):
        path = ROOT / "wiki" / str(item).lstrip("/")
        frontmatter, _body, error = parse_frontmatter(path)
        if error or frontmatter.get("type") != "Reference":
            ordinary.append(str(item))
    return check_result(
        "ordinary-orphans",
        "Ordinary-page orphan check",
        "warn" if ordinary else "pass",
        "medium" if ordinary else "info",
        "agent-required" if ordinary else "none",
        affected_paths=ordinary,
        evidence=[f"{path} has no incoming wiki link." for path in ordinary] or ["No ordinary-page orphans found."],
        recommended_action="Link useful synthesis from an appropriate index or related page." if ordinary else "",
    )


def reference_lifecycle_result(now: datetime | None = None) -> tuple[dict[str, Any], list[str]]:
    current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    _manifest, policy = load_runtime_policy(ROOT)
    lifecycle = policy["lifecycle"]
    grace = timedelta(days=int(lifecycle["reference_integration_grace_days"]))
    evidence: list[str] = []
    affected: list[str] = []
    source_ids: list[str] = []
    overdue: list[str] = []
    disposition = "none"
    severity = "info"
    outcome = "pass"
    for entry in parse_registry():
        reference = ROOT / str(entry["reference_path"])
        frontmatter, _body, error = parse_frontmatter(reference)
        if error or frontmatter.get("profile") != "llm-wiki-profile/0.2":
            continue
        if frontmatter.get("integration_state") in {"integrated", "not-applicable"}:
            continue
        source_id = str(entry["source_id"])
        priority = str(frontmatter.get("review_priority", "normal"))
        consequence = str(frontmatter.get("consequence_tier", "ordinary"))
        try:
            validated = parse_utc(str(frontmatter["validated_at"]))
        except (KeyError, ContractError) as exc:
            evidence.append(f"{source_id}: invalid validated_at ({exc})")
            affected.append(str(entry["reference_path"]))
            source_ids.append(source_id)
            outcome, severity, disposition = "fail", "high", "fix"
            continue
        immediate_priority = priority in {"high", "critical"} and lifecycle["high_priority_escalates_immediately"]
        immediate_consequence = consequence == "high-consequence" and lifecycle["high_consequence_escalates_immediately"]
        is_overdue = current >= validated + grace
        if is_overdue or immediate_priority or immediate_consequence:
            affected.append(str(entry["reference_path"]))
            source_ids.append(source_id)
            if is_overdue:
                overdue.append(source_id)
            outcome = "warn" if outcome != "fail" else outcome
            candidate = "critical" if immediate_consequence or priority == "critical" else "high" if immediate_priority else "medium"
            if SEVERITY_ORDER[candidate] > SEVERITY_ORDER[severity]:
                severity = candidate
            if candidate == "critical":
                disposition = "human-required"
            elif disposition != "human-required":
                disposition = "agent-required"
            reasons = []
            if is_overdue:
                reasons.append("integration grace period expired")
            if immediate_priority:
                reasons.append(f"{priority} priority")
            if immediate_consequence:
                reasons.append("high-consequence work")
            evidence.append(f"{source_id}: unintegrated; {', '.join(reasons)}")
        else:
            remaining = validated + grace - current
            evidence.append(f"{source_id}: unintegrated within grace period ({remaining.days + 1} calendar days remaining)")
    return (
        check_result(
            "reference-integration",
            "Reference integration lifecycle",
            outcome,
            severity,
            disposition if affected else "monitor" if evidence else "none",
            affected_paths=affected,
            source_ids=source_ids,
            evidence=evidence or ["No unintegrated profile 0.2 References found."],
            recommended_action="Integrate or explicitly disposition the identified References." if affected else "Monitor References until integration or grace expiry.",
        ),
        sorted(overdue),
    )


def semantic_not_run(check_id: str, title: str) -> dict[str, Any]:
    return check_result(
        check_id,
        title,
        "not_run",
        "info",
        "agent-required",
        evidence=["No deterministic adapter can perform this semantic assessment."],
        recommended_action="Assign an authorised agent and preserve its evidence-backed assessment.",
    )


def overall_for(results: list[dict[str, Any]]) -> str:
    highest = max((OUTCOME_ORDER[item["outcome"]] for item in results), default=0)
    return "red" if highest == 2 else "yellow" if highest == 1 else "green"


def semantic_review_for(mode: str, results: list[dict[str, Any]]) -> str:
    if mode != "full":
        return "not-requested"
    expected = {"semantic-staleness", "semantic-coverage", "semantic-contradictions"}
    semantic = {item["check_id"]: item for item in results if item["check_id"] in expected}
    if set(semantic) != expected or any(item["outcome"] == "not_run" for item in semantic.values()):
        return "required"
    return "complete"


def build_report(
    mode: str,
    now: datetime | None = None,
    *,
    include_mutating_builders: bool = True,
) -> dict[str, Any]:
    current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc).replace(microsecond=0)
    results = [
        run_tool("check_reserved_files.py"),
        run_tool("validate_frontmatter.py"),
        run_tool("check_links.py"),
        run_tool("word_count.py"),
        run_tool("detect_duplicates.py"),
    ]
    if include_mutating_builders:
        results.extend([run_tool("build_index.py"), run_tool("build_graph.py")])
    results.extend(
        [
            registry_result(),
            provenance_result(),
            source_coverage_result(),
            orphan_result(),
        ]
    )
    lifecycle, overdue = reference_lifecycle_result(current)
    results.append(lifecycle)
    structural_overall = overall_for(results)
    if mode == "full":
        results.extend(
            [
                semantic_not_run("semantic-staleness", "Semantic staleness assessment"),
                semantic_not_run("semantic-coverage", "Semantic coverage-gap assessment"),
                semantic_not_run("semantic-contradictions", "Contradiction-candidate assessment"),
            ]
        )
    blockers = [item["check_id"] for item in results if item["outcome"] == "fail"]
    agent_required = [
        item["check_id"]
        for item in results
        if item["disposition"] in {"agent-required", "human-required"}
    ]
    stamp = current.isoformat().replace("+00:00", "Z")
    report = {
        "schema_version": "rb-wiki-lint-report/0.2",
        "report_id": stamp.replace(":", "") + "-lint",
        "created_at": stamp,
        "mode": mode,
        "overall": structural_overall,
        "semantic_review": semantic_review_for(mode, results),
        "results": results,
        "queues": {
            "blockers": sorted(blockers),
            "overdue": overdue,
            "agent_required": sorted(agent_required),
        },
        "capabilities": capability_snapshot(),
    }
    validate_contract(report, "lint-report", ROOT)
    return report


def render_report_markdown(report: dict[str, Any]) -> str:
    lines = [
        f"# Wiki lint report {report['report_id']}",
        "",
        f"- Structural health: `{report['overall']}`",
        f"- Semantic review: `{report['semantic_review']}`",
        f"- Mode: `{report['mode']}`",
        f"- Created: `{report['created_at']}`",
        "",
        "## Checks",
        "",
        "| Check | Outcome | Severity | Disposition |",
        "|---|---|---|---|",
    ]
    for result in report["results"]:
        lines.append(
            f"| {result['title']} | `{result['outcome']}` | `{result['severity']}` | `{result['disposition']}` |"
        )
    for result in report["results"]:
        lines.extend(["", f"### {result['title']}", ""])
        lines.extend([f"- {item}" for item in result["evidence"]] or ["- No evidence recorded."])
        if result["affected_paths"]:
            lines.append("- Affected paths: " + ", ".join(f"`{path}`" for path in result["affected_paths"]))
        if result["source_ids"]:
            lines.append("- Source IDs: " + ", ".join(f"`{item}`" for item in result["source_ids"]))
        if result["recommended_action"]:
            lines.append(f"- Recommended action: {result['recommended_action']}")
    lines.extend(["", "## Action queues", ""])
    for key in ("blockers", "overdue", "agent_required"):
        values = report["queues"][key]
        lines.append(f"- {key.replace('_', ' ').title()}: {', '.join(values) if values else 'None.'}")
    return "\n".join(lines).rstrip() + "\n"


def write_report(report: dict[str, Any]) -> tuple[str, str]:
    report_dir = REPORTS_DIR / "lint"
    report_dir.mkdir(parents=True, exist_ok=True)
    base = unique_sibling_path(report_dir / f"{run_timestamp_utc()}-lint-report.json")
    atomic_write_json(base, report, ROOT)
    markdown = base.with_suffix(".md")
    atomic_write_text(markdown, render_report_markdown(report), ROOT)
    return base.relative_to(ROOT).as_posix(), markdown.relative_to(ROOT).as_posix()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run LLM-wiki lint")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--quick", action="store_true")
    mode.add_argument("--full", action="store_true")
    parser.add_argument("--no-report", action="store_true", help="let a parent run controller own persistence")
    parser.add_argument("--json", action="store_true", help="print the canonical JSON report")
    args = parser.parse_args(argv)
    if args.no_report and os.environ.get("RB_WIKI_RUN_CONTROLLER") != "1":
        parser.error("--no-report is reserved for RB Wiki run-controller subprocesses")
    mode_name = "full" if args.full else "quick"
    try:
        report = build_report(mode_name, include_mutating_builders=not args.no_report)
    except (ContractError, OSError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    if args.no_report:
        print("INFO: controller owns persistence; lint report suppressed")
    else:
        json_path, markdown_path = write_report(report)
        print(f"PASS: wrote {json_path} and {markdown_path}")
    if args.json:
        print(json.dumps(report, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    print(f"Structural health status: {report['overall']}")
    print(f"Semantic review status: {report['semantic_review']}")
    return 1 if report["overall"] == "red" else 0


if __name__ == "__main__":
    sys.exit(main())
