from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

TEMPLATE_ROOT = Path(__file__).resolve().parents[1]

ACTIVE_GRANT = """schema_version: rb-wiki-authority-grant/0.2
authority_id: test-maintainer
enabled: true
owner: test-suite
issued_at: "2026-01-01T00:00:00Z"
expires_at: "2099-01-01T00:00:00Z"
revoked_at: null
modes: [scheduled-propose]
lanes: [maintain]
actions: [deterministic-maintenance]
input_roots: []
writable_paths:
  - wiki/index.md
  - .wiki_cache/graph.json
  - reports/runs/**
  - reports/latest.json
page_types: []
required_checks: [quick-lint]
consequence_tier: routine
budgets:
  max_runtime_seconds: 60
  max_changed_paths: 25
  max_acquired_sources: 0
commit_policy: forbidden
commit_identity: null
governance_maintenance: false
"""


def run(
    command: list[str], root: Path, check: bool = True, env_overrides: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env.update(env_overrides or {})
    completed = subprocess.run(command, cwd=root, env=env, text=True, capture_output=True, check=False)
    if check and completed.returncode != 0:
        raise AssertionError(
            f"command failed ({completed.returncode}): {' '.join(command)}\n{completed.stdout}\n{completed.stderr}"
        )
    return completed


def make_git_wiki(parent: Path) -> Path:
    root = parent / "wiki"
    shutil.copytree(
        TEMPLATE_ROOT,
        root,
        ignore=shutil.ignore_patterns(".git", ".wiki_state", "__pycache__", "*.pyc"),
    )
    (root / "schema" / "authorities" / "test-maintainer.yml").write_text(ACTIVE_GRANT, encoding="utf-8")
    run(["git", "init", "-q"], root)
    run(["git", "config", "user.email", "tests@example.invalid"], root)
    run(["git", "config", "user.name", "RB Wiki Tests"], root)
    run([sys.executable, "tools/build_index.py"], root)
    run([sys.executable, "tools/build_graph.py"], root)
    run(["git", "add", "."], root)
    run(["git", "commit", "-q", "-m", "test fixture"], root)
    return root


def run_controller(root: Path) -> subprocess.CompletedProcess[str]:
    return run(
        [
            sys.executable,
            "tools/wiki_run.py",
            "run",
            "--lane",
            "maintain",
            "--mode",
            "scheduled-propose",
            "--authority",
            "test-maintainer",
        ],
        root,
        check=False,
    )


def add_authority(
    root: Path,
    authority_id: str,
    *,
    mode: str,
    lane: str,
    action: str | list[str],
    writable_paths: list[str],
    page_types: list[str] | None = None,
    input_roots: list[str] | None = None,
    commit_policy: str = "forbidden",
    governance: bool = False,
    consequence_tier: str = "routine",
) -> None:
    identity = "\n  name: RB Wiki Test Agent\n  email: rb-wiki@example.invalid" if commit_policy == "scoped-auto" else " null"
    actions = action if isinstance(action, list) else [action]
    lines = [
        "schema_version: rb-wiki-authority-grant/0.2",
        f"authority_id: {authority_id}",
        "enabled: true",
        "owner: test-suite",
        'issued_at: "2026-01-01T00:00:00Z"',
        'expires_at: "2099-01-01T00:00:00Z"',
        "revoked_at: null",
        f"modes: [{mode}]",
        f"lanes: [{lane}]",
        f"actions: [{', '.join(actions)}]",
        "input_roots: " + ("[" + ", ".join(input_roots or []) + "]"),
        "writable_paths:",
        *[f"  - {path}" for path in writable_paths],
        "page_types: " + ("[" + ", ".join(page_types or []) + "]"),
        "required_checks: [quick-lint]",
        f"consequence_tier: {consequence_tier}",
        "budgets:",
        "  max_runtime_seconds: 300",
        "  max_changed_paths: 25",
        "  max_acquired_sources: 10",
        f"commit_policy: {commit_policy}",
        "commit_identity:" + identity,
        f"governance_maintenance: {'true' if governance else 'false'}",
        "",
    ]
    path = root / "schema" / "authorities" / f"{authority_id}.yml"
    path.write_text("\n".join(lines), encoding="utf-8")
    run(["git", "add", path.relative_to(root).as_posix()], root)
    run(["git", "commit", "-q", "-m", f"add {authority_id} authority"], root)


def latest_record(root: Path) -> dict[str, object]:
    return json.loads((root / ".wiki_state" / "latest.json").read_text(encoding="utf-8"))
