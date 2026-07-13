#!/usr/bin/env python3
"""Generate a reviewed, deterministic v0.1-to-v0.2 migration plan and patch; never apply it."""

from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import sys
from pathlib import Path, PurePosixPath
from typing import Any

sys.dont_write_bytecode = True

from run_lib import (
    MAX_YAML_BYTES,
    ROOT,
    ContractError,
    RunError,
    canonical_json,
    git_status_paths,
    load_yaml_contract,
    require_contract_dependencies,
    validate_contract,
)
from wiki_lib import normalize_yaml_scalars
from fs_safety import checked_root, enumerate_regular_files, safe_path

MIGRATION_ID = "v01-to-v02"
IDEMPOTENCY_KEY = "rb-wiki-v01-to-v02-20260713"
MANIFEST_FIELDS = {
    "schema_version": "rb-wiki-manifest/0.2",
    "template_version": "0.2.0",
    "profile_version": "llm-wiki-profile/0.2",
    "tools_version": "0.2.0",
    "policy_version": "rb-wiki-policy/0.2",
    "agent_policy_id": "conservative-default",
    "consequence_policy_version": "rb-wiki-consequence-policy/0.2",
    "consequence_policy_id": "domain-neutral-default",
    "lane_contract_version": "rb-wiki-lane-contract/0.2",
    "report_version": "rb-wiki-run-record/0.2",
    "migration_version": "rb-wiki-migrations/0.2",
}


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def safe_overrides(values: Any) -> list[str]:
    if values is None:
        return []
    if not isinstance(values, list) or not all(isinstance(item, str) for item in values):
        raise ContractError("manifest local_overrides must be a list of safe relative paths")
    for value in values:
        path = PurePosixPath(value)
        if (
            value in {"", "."}
            or path.is_absolute()
            or ".." in path.parts
            or "\\" in value
            or value == "sources/raw"
            or value.startswith("sources/raw/")
        ):
            raise ContractError(f"unsafe local override: {value}")
    return sorted(set(values))


def load_legacy_yaml(path: Path, label: str, root: Path) -> Any:
    relative = path.absolute().relative_to(root.absolute()).as_posix()
    try:
        path = safe_path(root, relative, final_type="file")
    except ContractError as exc:
        raise ContractError(f"{label} must not be a symlink or traverse one") from exc
    try:
        if path.stat().st_size > MAX_YAML_BYTES:
            raise ContractError(f"{label} exceeds the {MAX_YAML_BYTES}-byte YAML limit")
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ContractError(f"cannot read {label}: {exc}") from exc
    yaml, _jsonschema = require_contract_dependencies()
    try:
        return yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise ContractError(f"unsafe or invalid YAML in {label}: {exc}") from exc


def load_legacy_text(path: Path, label: str, root: Path) -> str:
    relative = path.absolute().relative_to(root.absolute()).as_posix()
    try:
        path = safe_path(root, relative, final_type="file")
    except ContractError as exc:
        raise ContractError(f"{label} must not be a symlink or traverse one") from exc
    try:
        if not path.is_file():
            raise ContractError(f"{label} must be a regular file")
        if path.stat().st_size > MAX_YAML_BYTES:
            raise ContractError(f"{label} exceeds the {MAX_YAML_BYTES}-byte migration input limit")
        return path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ContractError(f"cannot read {label}: {exc}") from exc


def validate_legacy_reference_path(value: str) -> str:
    path = PurePosixPath(value)
    if (
        path.is_absolute()
        or ".." in path.parts
        or "\\" in value
        or len(path.parts) != 3
        or path.parts[:2] != ("wiki", "references")
        or path.suffix != ".md"
    ):
        raise ContractError(f"unsafe legacy reference path: {value}")
    return value


def unified_patch(path: str, before: str | None, after: str) -> str:
    header = f"diff --git a/{path} b/{path}\n"
    if before is None and after == "":
        return header + "new file mode 100644\nindex 0000000..e69de29\n"
    from_file = "/dev/null" if before is None else f"a/{path}"
    to_file = f"b/{path}"
    lines = difflib.unified_diff(
        [] if before is None else before.splitlines(keepends=True),
        after.splitlines(keepends=True),
        fromfile=from_file,
        tofile=to_file,
    )
    body = "".join(lines)
    return header + ("new file mode 100644\n" if before is None else "") + body


def canonical_copy_paths(template: Path) -> list[str]:
    paths = ["pyproject.toml", "docs/AGENT_OPERATIONS.md", "docs/DOMAIN_POLICY_COMPATIBILITY.md"]
    paths.extend(path.relative_to(template).as_posix() for path in enumerate_regular_files(template, "tools", ".py"))
    paths.extend(path.relative_to(template).as_posix() for path in enumerate_regular_files(template, "schema/contracts", ".json"))
    paths.extend(path.relative_to(template).as_posix() for path in enumerate_regular_files(template, "schema/lanes", ".yml"))
    paths.extend(path.relative_to(template).as_posix() for path in enumerate_regular_files(template, "schema/prompts", ".md"))
    paths.extend(["schema/agent_policy.yml", "schema/consequence_policy.yml", "schema/domain_policy.yml", "schema/migrations.yml"])
    paths.extend(
        f"reports/{name}/.gitkeep"
        for name in ["acquisitions", "approvals", "ingest", "lint", "proposals", "review", "runs", "semantic"]
    )
    return sorted(set(paths))


def parse_frontmatter_text(text: str) -> tuple[dict[str, Any], str]:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        raise ContractError("Reference page has no frontmatter")
    try:
        end = next(index for index, line in enumerate(lines[1:], start=1) if line.strip() == "---")
    except StopIteration as exc:
        raise ContractError("Reference frontmatter is unterminated") from exc
    yaml, _jsonschema = require_contract_dependencies()
    data = yaml.safe_load("\n".join(lines[1:end]))
    if not isinstance(data, dict):
        raise ContractError("Reference frontmatter is not a mapping")
    return normalize_yaml_scalars(data), "\n".join(lines[end + 1 :]).rstrip() + "\n"


def migrate_reference(text: str, entry: dict[str, Any], template: Path) -> str:
    frontmatter, body = parse_frontmatter_text(text)
    if frontmatter.get("type") != "Reference" or frontmatter.get("profile") != "llm-wiki-profile/0.1":
        return text
    complete = entry.get("ingest_state") in {"validated", "inbox-archived"}
    frontmatter.update(
        {
            "profile": "llm-wiki-profile/0.2",
            "review_state": "reviewed" if complete else "pending",
            "review_priority": "normal",
            "consequence_tier": "ordinary",
            "source_id": entry["source_id"],
            "source_type": entry["source_type"],
            "hash_sha256": entry["hash_sha256"],
            "date_published": entry.get("date_published", "unknown"),
            "date_ingested": entry["date_ingested"],
            "authors": frontmatter.get("authors", []),
            "source_access_level": entry.get("access_level", "full-text"),
            "derived_text": entry.get("derivative_path") or "",
            "extraction_status": frontmatter.get("extraction_status", "not-applicable"),
            "integration_state": "integrated" if complete else "unintegrated",
            "assessment_state": "assessed" if complete else "unassessed",
            "validated_at": frontmatter.get("timestamp"),
        }
    )
    validate_contract(frontmatter, "page-frontmatter", template)
    yaml, _jsonschema = require_contract_dependencies()
    rendered = yaml.safe_dump(frontmatter, sort_keys=False, allow_unicode=True).rstrip()
    return f"---\n{rendered}\n---\n\n{body}"


def registry_entries(root: Path) -> dict[str, dict[str, Any]]:
    path = root / "sources" / "_source_registry.yml"
    if not path.exists() and not path.is_symlink():
        return {}
    data = load_legacy_yaml(path, "source registry", root)
    values = data if isinstance(data, list) else data.get("sources", []) if isinstance(data, dict) else []
    result: dict[str, dict[str, Any]] = {}
    for raw in values:
        if not isinstance(raw, dict) or "reference_path" not in raw:
            continue
        entry = dict(raw)
        entry.setdefault("ingest_state", "validated")
        entry.setdefault("access_level", "raw-only" if entry.get("source_type") == "pdf" else "full-text")
        entry.setdefault("derivative_path", None)
        relative = validate_legacy_reference_path(str(entry["reference_path"]))
        result[relative] = entry
    return result


def build_plan(root: Path, template: Path) -> dict[str, Any]:
    root, template = checked_root(root), checked_root(template)
    try:
        safe_path(root, "wiki", final_type="directory")
        safe_path(root, "sources", final_type="directory")
    except ContractError as exc:
        raise ContractError("migration root is not a safe RB Wiki base") from exc
    load_yaml_contract(template / "schema" / "migrations.yml", "migration-registry", template)
    yaml, _jsonschema = require_contract_dependencies()
    manifest_path = root / "wiki-manifest.yml"
    if manifest_path.exists() or manifest_path.is_symlink():
        loaded = load_legacy_yaml(manifest_path, "wiki manifest", root)
        manifest = dict(loaded) if isinstance(loaded, dict) else {}
    else:
        manifest = {"wiki_id": root.name, "enabled_capabilities": []}
    overrides = safe_overrides(manifest.get("local_overrides", []))
    known_manifest = set(MANIFEST_FIELDS) | {"wiki_id", "enabled_capabilities", "local_overrides"}
    unknown_manifest = sorted(set(manifest).difference(known_manifest))
    manual_review = [f"Unknown manifest field requires review: {field}" for field in unknown_manifest]
    try:
        dirty = git_status_paths(root)
    except RunError as exc:
        raise ContractError("migration dry-run requires an inspectable Git worktree") from exc
    desired: dict[str, tuple[str, list[str]]] = {}
    if not unknown_manifest and "wiki-manifest.yml" not in overrides:
        updated_manifest = {**manifest, **MANIFEST_FIELDS, "local_overrides": overrides}
        updated_manifest["enabled_capabilities"] = yaml.safe_load(
            load_legacy_text(template / "wiki-manifest.yml", "template wiki manifest", template)
        )["enabled_capabilities"]
        validate_contract(updated_manifest, "wiki-manifest", template)
        desired["wiki-manifest.yml"] = (
            yaml.safe_dump(updated_manifest, sort_keys=False, allow_unicode=True),
            sorted(MANIFEST_FIELDS) + ["enabled_capabilities", "local_overrides"],
        )
    if ".gitignore" not in overrides:
        canonical_ignore = load_legacy_text(template / ".gitignore", "template .gitignore", template).splitlines()
        current_ignore_path = root / ".gitignore"
        current_ignore = (
            load_legacy_text(current_ignore_path, "legacy .gitignore", root).splitlines()
            if current_ignore_path.exists() or current_ignore_path.is_symlink()
            else []
        )
        merged_ignore = current_ignore + [line for line in canonical_ignore if line not in current_ignore]
        desired[".gitignore"] = ("\n".join(merged_ignore).rstrip() + "\n", ["v0.2 operational ignore rules"])
    semantic_policy_paths = {"schema/consequence_policy.yml", "schema/domain_policy.yml"}
    for relative in canonical_copy_paths(template):
        if relative in overrides:
            continue
        source = safe_path(template, relative, allow_missing=True, final_type="file")
        if not source.exists():
            continue
        target = safe_path(root, relative, allow_missing=True, final_type="file")
        source_text = load_legacy_text(source, f"template {relative}", template)
        target_text = (
            load_legacy_text(target, f"legacy {relative}", root)
            if target.exists() or target.is_symlink()
            else None
        )
        if relative in semantic_policy_paths and target_text is not None and target_text != source_text and relative not in overrides:
            manual_review.append(f"Ambiguous local semantic policy requires adapter review: {relative}")
            continue
        desired[relative] = (source_text, ["whole-file canonical v0.2 copy"])
    entries = registry_entries(root)
    incomplete = [entry["source_id"] for entry in entries.values() if entry.get("ingest_state") not in {"validated", "inbox-archived"}]
    if incomplete:
        manual_review.append("Incomplete ingest must be recovered before migration: " + ", ".join(sorted(incomplete)))
    for relative, entry in entries.items():
        path = root / relative
        if relative in overrides:
            continue
        try:
            safe_path(root, relative, allow_missing=True, final_type="file")
        except ContractError as exc:
            raise ContractError(f"legacy Reference must not be a symlink or traverse one: {relative}") from exc
        if not path.is_file():
            continue
        before = load_legacy_text(path, f"legacy Reference {relative}", root)
        try:
            after = migrate_reference(before, entry, template)
        except ContractError as exc:
            manual_review.append(f"Reference lifecycle migration is ambiguous for {relative}: {exc}")
            continue
        desired[relative] = (after, ["profile", "review/integration/assessment lifecycle defaults"])
    changes: list[dict[str, Any]] = []
    patch_parts: list[str] = []
    for relative, (after, fields) in sorted(desired.items()):
        if relative.startswith("sources/raw/") or relative in overrides:
            continue
        path = root / relative
        safe_path(root, relative, allow_missing=True, final_type="file")
        before = (
            load_legacy_text(path, f"legacy migration target {relative}", root)
            if path.exists() or path.is_symlink()
            else None
        )
        if before == after:
            continue
        changes.append(
            {
                "path": relative,
                "operation": "replace" if before is not None else "create",
                "classification": "mechanical",
                "fields": fields,
                "before_sha256": sha(before) if before is not None else None,
                "after_sha256": sha(after),
            }
        )
        patch_parts.append(unified_patch(relative, before, after))
    migration_managed_paths = set(desired)
    unexpected_dirty = sorted(path for path in dirty if path not in migration_managed_paths)
    if unexpected_dirty:
        manual_review.append(
            "Dirty worktree must be committed or stashed before patch application: " + ", ".join(unexpected_dirty)
        )
    status = "manual-review" if manual_review else "ready" if changes else "no-op"
    plan = {
        "schema_version": "rb-wiki-migration-plan/0.2",
        "plan_id": f"{MIGRATION_ID}-{hashlib.sha256(str(root).encode()).hexdigest()[:12]}",
        "migration_id": MIGRATION_ID,
        "idempotency_key": IDEMPOTENCY_KEY,
        "wiki_root": str(root),
        "from_profile": str(manifest.get("profile_version", "llm-wiki-profile/0.1")),
        "to_profile": "llm-wiki-profile/0.2",
        "status": status,
        "changes": changes,
        "preserved_overrides": overrides,
        "manual_review": manual_review,
        "commands": [
            "python3 tools/wiki_migrate.py --dry-run --patch-only > rb-wiki-v01-to-v02.patch",
            "git apply --check rb-wiki-v01-to-v02.patch",
            "Review the patch and required approvals; application is deliberately external to the migration tool.",
            "git apply rb-wiki-v01-to-v02.patch",
        ],
        "risks": [
            "Generated tools/policies change operational behavior and require review.",
            "Reference frontmatter is reserialised only when lifecycle defaults are mechanically complete.",
            "Subject-specific semantic policy is never guessed.",
        ],
        "required_approvals": ["Maintainer review of the exact generated patch before external application."],
        "expected_validation": [
            "python3 tools/wiki_doctor.py --json",
            "python3 tools/provenance.py validate",
            "python3 tools/lint.py --quick",
            "python3 -m unittest discover -s tests -v",
        ],
        "generated_patch": "".join(patch_parts),
    }
    validate_contract(plan, "migration-plan", template)
    return plan


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate a reviewed RB Wiki v0.2 migration patch")
    parser.add_argument("--dry-run", action="store_true", required=True)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--template", type=Path, default=ROOT)
    parser.add_argument("--patch-only", action="store_true")
    args = parser.parse_args(argv)
    try:
        plan = build_plan(args.root, args.template)
    except (ContractError, RunError, OSError, KeyError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    print(plan["generated_patch"] if args.patch_only else canonical_json(plan), end="")
    return 2 if plan["status"] in {"manual-review", "blocked"} else 0


if __name__ == "__main__":
    sys.exit(main())
