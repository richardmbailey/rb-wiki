#!/usr/bin/env python3
"""Create a new LLM-wiki from wiki-template and reconfigure its subject shell."""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path


TEXT_SUFFIXES = {".md", ".yml", ".yaml"}
SAFE_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
SAFE_TAG_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")


def slugify(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-") or "wiki"


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")


def yaml_quote(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def is_under(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def require_single_line(parser: argparse.ArgumentParser, value: str, label: str, maximum: int) -> None:
    if not value.strip() or any(character in value for character in "\r\n\x00"):
        parser.error(f"--{label} must be non-empty single-line text")
    if len(value) > maximum:
        parser.error(f"--{label} must be at most {maximum} characters")


def replace_all(root: Path, replacements: dict[str, str]) -> None:
    raw_dir = root / "sources" / "raw"
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.suffix not in TEXT_SUFFIXES:
            continue
        relative = path.relative_to(root)
        if relative.parts and relative.parts[0] in {"schema", "tools", "tests", "docs", "reports", ".wiki_cache"}:
            continue
        if relative.as_posix() == "wiki-manifest.yml":
            continue
        if is_under(path, raw_dir):
            continue
        text = read_text(path)
        updated = text
        for old, new in replacements.items():
            updated = updated.replace(old, new)
        if updated != text:
            write_text(path, updated)


def replace_line(path: Path, prefix: str, new_line: str) -> None:
    lines = read_text(path).splitlines()
    changed = False
    for index, line in enumerate(lines):
        if line.startswith(prefix):
            lines[index] = new_line
            changed = True
            break
    if changed:
        write_text(path, "\n".join(lines).rstrip() + "\n")


def reset_reports(root: Path) -> None:
    reports_dir = root / "reports"
    for subdir_name in ["acquisitions", "approvals", "ingest", "lint", "proposals", "review", "runs", "semantic"]:
        subdir = reports_dir / subdir_name
        subdir.mkdir(parents=True, exist_ok=True)
        for child in subdir.iterdir():
            if child.name == ".gitkeep":
                continue
            if child.is_dir():
                shutil.rmtree(child)
            else:
                child.unlink()
        (subdir / ".gitkeep").touch()


def run_tool(root: Path, *command: str) -> None:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    completed = subprocess.run(
        [sys.executable, *command],
        cwd=root,
        text=True,
        capture_output=True,
        check=False,
        env=env,
        timeout=300,
    )
    output = (completed.stdout + completed.stderr).strip()
    if output:
        print(output)
    if completed.returncode != 0:
        raise RuntimeError(f"{' '.join(command)} failed with exit code {completed.returncode}")


def initialize_git(root: Path) -> None:
    """Publish a clean standalone Git base required by managed v0.2 runs."""
    commands = [
        ["git", "init", "-q", "-b", "main"],
        ["git", "add", "--all"],
        [
            "git",
            "-c",
            "core.hooksPath=/dev/null",
            "-c",
            "user.name=RB Wiki Setup",
            "-c",
            "user.email=rb-wiki-setup@local.invalid",
            "commit",
            "-q",
            "-m",
            "Initialize RB Wiki v0.2",
        ],
    ]
    for command in commands:
        completed = subprocess.run(
            command,
            cwd=root,
            text=True,
            capture_output=True,
            check=False,
            timeout=120,
        )
        if completed.returncode != 0:
            detail = (completed.stderr or completed.stdout).strip()
            raise RuntimeError(f"{' '.join(command)} failed: {detail}")


def write_setup_note(root: Path, args: argparse.Namespace) -> None:
    setup_path = root / "SETUP.md"
    template_label = args.template.name
    # Setup runs in a temporary staging directory before atomic publication.
    # Show the requested final directory name, not that internal staging name.
    base_label = args.name
    grant_status = (
        "A bounded `scheduled-maintainer` grant was created for deterministic nightly/weekly upkeep. "
        "It does not authorise ingest or autonomous page editing."
        if args.enable_scheduled_propose
        else "No active authority grant was created. This is the safe default."
    )
    setup_path.write_text(
        "\n".join(
            [
                f"# {args.title} Setup",
                "",
                f"- Subject: {args.subject}",
                f"- Domain tag: `{args.tag}`",
                f"- Created from template directory: `{template_label}`",
                f"- Base directory name: `{base_label}`",
                "- Git base: standalone repository on branch `main` with a clean initial commit.",
                f"- Authority status: {grant_status}",
                "",
                "# Choose An Operating Model",
                "",
                "- **Human-driven:** a person chooses each task, reviews every change, and commits it. "
                "Direct human Markdown edits need no grant; a mutating interactive agent uses a narrow "
                "`manual-assist` grant.",
                "- **Agent-driven:** scheduled or autonomous agents run only under committed, enabled, "
                "time-bounded grants. Scheduled synthesis prepares proposals; exact proposal content is "
                "applied separately. No mode pushes.",
                "",
                "Read `README.md`, `docs/AGENT_OPERATIONS.md`, and `docs/AUTHORITY_GRANTS.md` before "
                "enabling agent-driven work.",
                "",
                "# Next Steps",
                "",
                "1. Install dependencies and run `python3 tools/capabilities.py --json` and "
                "`python3 tools/wiki_doctor.py --json`.",
                "2. Start in the human-driven model and confirm the wiki's subject policy and checks.",
                "3. Drop initial source files into `inbox/`. Create and commit a dedicated ingest grant "
                "before asking `$rb-wiki-ingest` or `wiki_cron.py inbox` to mutate the wiki.",
                "4. Use `$rb-wiki-maintenance` for human-reviewed checks after edits.",
                "5. Add one narrow automation only after its matching grant and supervised run have been "
                "reviewed successfully.",
                "",
            ]
        ),
        encoding="utf-8",
    )


def configure_wiki(root: Path, args: argparse.Namespace) -> None:
    subject_tag = args.tag
    overview_title = f"{args.title} Overview"
    overview_description = f"A high-level map of {args.title} and its source-backed operating model."

    replace_all(
        root,
        {
            "wiki-template": subject_tag,
            "Wiki Template Overview": overview_title,
            "Wiki Template": args.title,
            "this wiki template": args.title,
            "This wiki template": args.title,
            "the wiki template": args.title,
            "The template": args.title,
            "subject-specific": args.subject,
        },
    )

    readme = root / "README.md"
    if readme.exists():
        replace_line(readme, "# ", f"# {args.title}")
        text = read_text(readme)
        text = re.sub(
            r"This directory is .*?\n",
            lambda _match: f"{args.description}\n",
            text,
            count=1,
        )
        write_text(readme, text)

    agents = root / "AGENTS.md"
    if agents.exists():
        text = read_text(agents)
        text = re.sub(
            r"The goal is to compile raw sources into durable, cited, cross-linked knowledge about .*\.",
            lambda _match: (
                "The goal is to compile raw sources into durable, cited, cross-linked "
                f"knowledge about {args.subject}."
            ),
            text,
            count=1,
        )
        write_text(agents, text)

    overview = root / "wiki" / "overview.md"
    if overview.exists():
        replace_line(overview, "title: ", f"title: {yaml_quote(overview_title)}")
        replace_line(overview, "description: ", f"description: {yaml_quote(overview_description)}")
        text = read_text(overview)
        text = re.sub(
            r"\n.*? is an initial source-backed knowledge system.*?\n",
            lambda _match: f"\n{args.description}\n",
            text,
            count=1,
        )
        write_text(overview, text)

    log = root / "wiki" / "log.md"
    if log.exists():
        text = read_text(log)
        text = re.sub(
            r"Initialized .* skeleton\.",
            lambda _match: f"Initialized the {args.title} skeleton from wiki-template.",
            text,
            count=1,
        )
        write_text(log, text)

    manifest = root / "wiki-manifest.yml"
    if manifest.exists():
        replace_line(manifest, "wiki_id: ", f"wiki_id: {slugify(args.name)}")

    template_note = root / "TEMPLATE.md"
    if template_note.exists():
        template_note.unlink()
    write_setup_note(root, args)


def write_scheduled_authority(root: Path, args: argparse.Namespace) -> None:
    if not args.enable_scheduled_propose:
        return
    issued = datetime.now(timezone.utc).replace(microsecond=0)
    expires = issued + timedelta(days=args.authority_days)
    timestamp = lambda value: value.isoformat().replace("+00:00", "Z")
    path = root / "schema" / "authorities" / "scheduled-maintainer.yml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f'''schema_version: rb-wiki-authority-grant/0.2
authority_id: scheduled-maintainer
enabled: true
owner: {yaml_quote(args.authority_owner)}
issued_at: {yaml_quote(timestamp(issued))}
expires_at: {yaml_quote(timestamp(expires))}
revoked_at: null
modes: [scheduled-propose]
lanes: [maintain]
actions: [deterministic-maintenance]
input_roots: []
writable_paths:
  - wiki/index.md
  - .wiki_cache/graph.json
  - reports/lint/**
  - reports/runs/**
  - reports/latest.json
page_types: []
required_checks: [quick-lint]
consequence_tier: routine
budgets:
  max_runtime_seconds: 300
  max_changed_paths: 25
  max_acquired_sources: 0
commit_policy: forbidden
commit_identity: null
governance_maintenance: false
''',
        encoding="utf-8",
    )


def copy_template(template: Path, destination: Path) -> None:
    if not template.is_dir():
        raise RuntimeError(f"template does not exist: {template}")
    if destination.exists():
        raise RuntimeError(f"destination already exists: {destination}")
    for path in template.rglob("*"):
        relative = path.relative_to(template)
        if relative.parts and relative.parts[0] in {".git", ".wiki_state"}:
            continue
        if path.is_symlink():
            raise RuntimeError(f"template contains unsupported symlink: {relative.as_posix()}")
    shutil.copytree(
        template,
        destination,
        ignore=shutil.ignore_patterns(
            ".git", ".wiki_state", "__pycache__", "*.pyc", "*.egg-info", ".DS_Store", "processed"
        ),
    )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create a new LLM-wiki from wiki-template")
    parser.add_argument("--template", required=True, type=Path)
    parser.add_argument("--parent", required=True, type=Path)
    parser.add_argument("--name", required=True)
    parser.add_argument("--title", required=True)
    parser.add_argument("--subject", required=True)
    parser.add_argument("--tag")
    parser.add_argument("--description")
    parser.add_argument(
        "--enable-scheduled-propose",
        action="store_true",
        help="explicitly generate a bounded scheduled-maintenance grant (never autonomous apply)",
    )
    parser.add_argument("--authority-owner", default="local-maintainer")
    parser.add_argument("--authority-days", type=int, default=30)
    args = parser.parse_args(argv)
    args.template = args.template.expanduser().resolve()
    args.parent = args.parent.expanduser().resolve()
    args.tag = args.tag or slugify(args.subject)
    args.description = args.description or f"{args.title} is a local-first LLM-wiki for {args.subject}."
    if Path(args.name).name != args.name:
        parser.error("--name must be a single directory name, not a path")
    if not SAFE_NAME_RE.match(args.name):
        parser.error("--name may contain only letters, numbers, dots, underscores, and hyphens")
    if not 2 <= len(slugify(args.name)) <= 63:
        parser.error("--name must produce a wiki ID between 2 and 63 characters")
    if not SAFE_TAG_RE.match(args.tag):
        parser.error("--tag must be lowercase kebab-case, using only letters, numbers, and hyphens")
    if len(args.tag) > 63:
        parser.error("--tag must be at most 63 characters")
    require_single_line(parser, args.title, "title", 200)
    require_single_line(parser, args.subject, "subject", 300)
    require_single_line(parser, args.description, "description", 500)
    require_single_line(parser, args.authority_owner, "authority-owner", 128)
    if args.authority_days < 1 or args.authority_days > 365:
        parser.error("--authority-days must be between 1 and 365")
    return args


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    destination = args.parent / args.name
    staging = args.parent / f".{args.name}.rb-wiki-staging-{uuid.uuid4().hex[:12]}"
    if destination.exists():
        print(f"FAIL: destination already exists: {destination}", file=sys.stderr)
        return 1
    try:
        copy_template(args.template, staging)
        reset_reports(staging)
        configure_wiki(staging, args)
        write_scheduled_authority(staging, args)
        if os.environ.get("RB_WIKI_INJECT_SETUP_FAILURE") == "after-configure":
            raise RuntimeError("injected setup failure after configuration")
        run_tool(staging, "tools/build_index.py")
        run_tool(staging, "tools/build_graph.py")
        run_tool(staging, "tools/source_registry.py", "validate")
        run_tool(staging, "tools/lint.py", "--quick")
        initialize_git(staging)
        run_tool(staging, "tools/wiki_doctor.py", "--json")
        os.replace(staging, destination)
        directory_fd = os.open(args.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    except Exception as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        if staging.exists():
            diagnostic = args.parent / f"{args.name}.rb-wiki-failed-{uuid.uuid4().hex[:12]}"
            os.replace(staging, diagnostic)
            print(f"Diagnostic staging directory preserved at: {diagnostic}", file=sys.stderr)
            print("Inspect it, then remove it or retry with a new --name after correcting the failure.", file=sys.stderr)
        return 1

    print(f"PASS: created {destination}")
    print(f"Title: {args.title}")
    print(f"Subject: {args.subject}")
    print(f"Tag: {args.tag}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
