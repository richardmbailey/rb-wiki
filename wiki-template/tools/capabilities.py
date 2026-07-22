#!/usr/bin/env python3
"""Report implemented and unavailable wiki capabilities truthfully."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def capability_snapshot(root: Path = ROOT) -> dict[str, object]:
    root = root.absolute()
    root_error = None
    if root.is_symlink() or not root.is_dir():
        root_error = f"operational root is not a real directory: {root}"
    try:
        import yaml
        import jsonschema
        dependency_error = None
    except ImportError as exc:
        yaml = jsonschema = None
        dependency_error = f"required dependency is unavailable: {exc.name}"

    def implemented(
        label: str, *relative_paths: str, executables: tuple[str, ...] = ()
    ) -> dict[str, object]:
        def safe_file(relative: str) -> bool:
            current = root
            for part in Path(relative).parts:
                current /= part
                if current.is_symlink():
                    return False
            return current.is_file()

        if root_error is not None:
            return {"available": False, "implementation": label, "reason": root_error}
        missing = [
            path
            for path in relative_paths
            if not safe_file(path)
        ]
        if missing:
            return {
                "available": False,
                "implementation": label,
                "reason": "missing implementation path(s): " + ", ".join(missing),
            }
        if sys.version_info < (3, 10):
            return {"available": False, "implementation": label, "reason": "Python 3.10 or newer is required"}
        if dependency_error is not None:
            return {"available": False, "implementation": label, "reason": dependency_error}
        missing_executables = [name for name in executables if shutil.which(name) is None]
        if missing_executables:
            return {
                "available": False,
                "implementation": label,
                "reason": "missing executable(s): " + ", ".join(missing_executables),
            }
        try:
            for relative in relative_paths:
                path = root / relative
                if path.suffix == ".py":
                    compile(path.read_text(encoding="utf-8"), str(path), "exec")
                elif path.name.endswith(".schema.json"):
                    assert jsonschema is not None
                    schema = json.loads(path.read_text(encoding="utf-8"))
                    jsonschema.validators.validator_for(schema).check_schema(schema)
                elif path.suffix in {".yml", ".yaml"}:
                    assert yaml is not None
                    if not isinstance(yaml.safe_load(path.read_text(encoding="utf-8")), dict):
                        raise ValueError("YAML root is not a mapping")
        except (
            OSError, UnicodeError, SyntaxError, ValueError, json.JSONDecodeError, AssertionError,
            yaml.YAMLError, jsonschema.exceptions.SchemaError,
        ) as exc:
            return {"available": False, "implementation": label, "reason": f"implementation validation failed: {exc}"}
        return {"available": True, "implementation": label}

    registry = {
        "deterministic-maintenance": implemented("tools/lint.py", "tools/lint.py"),
        "lexical-search": implemented("tools/query.py search", "tools/query.py"),
        "scheduled-propose": implemented("tools/wiki_run.py", "tools/wiki_run.py", "tools/run_lib.py"),
        "external-agent-sessions": implemented("tools/wiki_run.py start", "tools/wiki_run.py", "tools/run_lib.py"),
        "scoped-auto-commit": implemented(
            "recoverable Git transaction in tools/git_transaction.py", "tools/git_transaction.py",
            "schema/contracts/git-transaction.schema.json", executables=("git",),
        ),
        "recoverable-ingest": implemented("tools/ingest.py transitions", "tools/ingest.py", "tools/source_registry.py"),
        "typed-lint": implemented("tools/lint.py", "tools/lint.py", "schema/contracts/lint-report.schema.json"),
        "artifact-lane-handoffs": implemented(
            "schema/lanes and tools/semantic_protocol.py",
            "tools/semantic_protocol.py",
            "schema/lanes/acquire.yml",
            "schema/lanes/ingest.yml",
            "schema/lanes/synthesize.yml",
        ),
        "bounded-semantic-apply": implemented(
            "tools/wiki_cron.py apply",
            "tools/authorised_apply.py",
            "tools/wiki_cron.py",
            "tools/wiki_run.py",
            "tools/semantic_protocol.py",
        ),
        "high-consequence-approval": implemented(
            "base-committed proposal and approval binding",
            "tools/semantic_protocol.py",
            "schema/contracts/approval-record.schema.json",
        ),
        "domain-policy-adapter": implemented("schema/domain_policy.yml", "schema/domain_policy.yml"),
        "read-only-doctor": implemented("tools/wiki_doctor.py", "tools/wiki_doctor.py"),
        "migration-dry-run": implemented(
            "tools/wiki_migrate.py (patch output only)", "tools/wiki_migrate.py",
            "schema/contracts/migration-plan.schema.json", executables=("git",),
        ),
        "markdown-ingest": implemented("recoverable ingest", "tools/ingest.py"),
        "text-ingest": implemented("recoverable ingest", "tools/ingest.py"),
        "pdf-ingest": implemented("raw preservation with optional extraction", "tools/ingest.py", "tools/pdf_extract.py"),
        "html-ingest": {
            "available": False,
            "alias_for": None,
            "reason": "HTML has no v0.2 extraction adapter; explicit preservation-only authority is required",
        },
        "bm25-search": {"available": False, "alias_for": None, "reason": "no BM25 backend is installed"},
        "vector-search": {"available": False, "alias_for": None, "reason": "no vector backend is installed"},
        "hybrid-search": {"available": False, "alias_for": None, "reason": "BM25 and vector backends are unavailable"},
        "pdf-text-extraction": {
            "available": shutil.which("pdftotext") is not None,
            "implementation": "pdftotext" if shutil.which("pdftotext") else None,
        },
    }
    canonical = json.dumps(registry, sort_keys=True, separators=(",", ":"))
    return {
        "schema_version": "rb-wiki-capabilities/0.2",
        "digest_sha256": hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
        "capabilities": registry,
    }


def reconcile_capabilities(manifest: dict[str, object], snapshot: dict[str, object]) -> list[str]:
    enabled = set(manifest.get("enabled_capabilities", []))
    registry = snapshot["capabilities"]
    assert isinstance(registry, dict)
    errors = [f"manifest capability is unknown: {name}" for name in sorted(enabled.difference(registry))]
    for name in sorted(enabled.intersection(registry)):
        details = registry[name]
        if isinstance(details, dict) and not details.get("available"):
            errors.append(f"enabled capability is unavailable: {name}: {details.get('reason', 'no reason')}")
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Report RB Wiki capabilities")
    parser.add_argument("--json", action="store_true", help="write canonical JSON")
    args = parser.parse_args(argv)
    snapshot = capability_snapshot()
    if args.json:
        print(json.dumps(snapshot, sort_keys=True, separators=(",", ":")))
    else:
        for name, details in snapshot["capabilities"].items():
            status = "available" if details["available"] else "unavailable"
            print(f"{name}: {status}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
