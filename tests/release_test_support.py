from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[1]
TEMPLATE = REPO / "wiki-template"
NEW_WIKI = REPO / "skills" / "rb-new-wiki" / "scripts" / "new_wiki.py"
MIGRATE = TEMPLATE / "tools" / "wiki_migrate.py"


def run(command: list[str], cwd: Path, *, check: bool = True, env: dict[str, str] | None = None):
    merged = os.environ.copy()
    merged["PYTHONDONTWRITEBYTECODE"] = "1"
    merged.update(env or {})
    completed = subprocess.run(command, cwd=cwd, env=merged, text=True, capture_output=True, check=False)
    if check and completed.returncode != 0:
        raise AssertionError(f"command failed: {' '.join(command)}\n{completed.stdout}\n{completed.stderr}")
    return completed


def init_git(root: Path) -> None:
    run(["git", "init", "-q"], root)
    run(["git", "config", "user.email", "release-tests@example.invalid"], root)
    run(["git", "config", "user.name", "Release Tests"], root)
    run(["git", "add", "."], root)
    run(["git", "commit", "-q", "-m", "fixture baseline"], root)


def make_v01(
    parent: Path, *, local_override: bool = False, policy_diverged: bool = False, incomplete_ingest: bool = False
) -> Path:
    root = parent / "v01-wiki"
    shutil.copytree(TEMPLATE, root, ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".wiki_state"))
    manifest_path = root / "wiki-manifest.yml"
    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    manifest.update(
        schema_version="rb-wiki-manifest/0.1",
        template_version="0.1.0",
        profile_version="llm-wiki-profile/0.1",
        tools_version="0.1.0",
        policy_version="rb-wiki-policy/0.1",
        report_version="rb-wiki-run-record/0.1",
    )
    for key in ("consequence_policy_version", "lane_contract_version", "migration_version"):
        manifest.pop(key, None)
    manifest["enabled_capabilities"] = ["lexical-search", "deterministic-maintenance"]
    manifest["local_overrides"] = ["tools/query.py"] if local_override else []
    manifest_path.write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")
    reference = root / "wiki" / "references" / "2026-07-09-llm-wiki-system-instructions.md"
    text = reference.read_text(encoding="utf-8").replace(
        "profile: llm-wiki-profile/0.2", "profile: llm-wiki-profile/0.1"
    )
    remove_prefixes = (
        "review_state:", "review_priority:", "consequence_tier:", "source_access_level:",
        "integration_state:", "assessment_state:", "validated_at:",
    )
    text = "\n".join(line for line in text.splitlines() if not line.startswith(remove_prefixes)) + "\n"
    reference.write_text(text, encoding="utf-8")
    shutil.rmtree(root / "tools")
    (root / "tools").mkdir()
    if local_override:
        (root / "tools" / "query.py").write_text("# preserved local query adapter\n", encoding="utf-8")
    for relative in ["schema/contracts", "schema/lanes", "schema/prompts", "docs"]:
        path = root / relative
        if path.exists():
            shutil.rmtree(path)
    for relative in [
        "pyproject.toml", "schema/agent_policy.yml", "schema/consequence_policy.yml",
        "schema/domain_policy.yml", "schema/migrations.yml",
    ]:
        path = root / relative
        if path.exists():
            path.unlink()
    if policy_diverged:
        path = root / "schema" / "domain_policy.yml"
        path.write_text("schema_version: local-policy/0.1\nsubject_rule: ambiguous\n", encoding="utf-8")
    for name in ["acquisitions", "approvals", "proposals", "runs", "semantic"]:
        path = root / "reports" / name
        if path.exists():
            shutil.rmtree(path)
    ignore = root / ".gitignore"
    ignore.write_text("__pycache__/\n*.pyc\n", encoding="utf-8")
    if incomplete_ingest:
        registry = root / "sources" / "_source_registry.yml"
        registry.write_text(
            registry.read_text(encoding="utf-8").replace("ingest_state: validated", "ingest_state: recovery-required"),
            encoding="utf-8",
        )
    init_git(root)
    return root


def plan(root: Path):
    completed = run(
        [sys.executable, str(MIGRATE), "--dry-run", "--root", str(root), "--template", str(TEMPLATE)],
        REPO,
        check=False,
    )
    return completed, json.loads(completed.stdout)


def tree_hashes(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.rglob("*"))
        if path.is_file() and ".git" not in path.parts and "__pycache__" not in path.parts
    }
