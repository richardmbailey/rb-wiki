#!/usr/bin/env python3
"""Safely load, write, reconcile, and validate the v0.2 source registry."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from run_lib import (
    MAX_YAML_BYTES,
    ContractError,
    atomic_write_text,
    require_contract_dependencies,
    symlink_component,
    validate_contract,
)
from wiki_lib import RAW_DIR, ROOT, SOURCES_DIR, sha256_file, slugify, today_utc

REGISTRY_PATH = SOURCES_DIR / "_source_registry.yml"
REGISTRY_VERSION = "rb-wiki-source-registry/0.2"

SOURCE_TYPES_BY_SUFFIX = {
    ".pdf": "pdf", ".md": "note", ".markdown": "note", ".txt": "note", ".text": "note",
    ".html": "web", ".htm": "web", ".csv": "dataset", ".tsv": "dataset", ".json": "dataset",
    ".py": "code", ".js": "code", ".ts": "code", ".mp3": "audio", ".m4a": "audio",
    ".wav": "audio", ".mp4": "video", ".mov": "video", ".png": "image", ".jpg": "image",
    ".jpeg": "image",
}

SOURCE_FORMAT_CAPABILITIES = {
    ".md": "ingest",
    ".markdown": "ingest",
    ".txt": "ingest",
    ".text": "ingest",
    ".pdf": "ingest",
    ".html": "preservation-only",
    ".htm": "preservation-only",
}

FIELD_ORDER = [
    "source_id", "raw_path", "reference_path", "hash_sha256", "source_type", "date_ingested",
    "date_published", "status", "ingest_state", "access_level", "processed_path", "derivative_path",
]


def _legacy_entry(entry: dict[str, Any]) -> dict[str, Any]:
    migrated = dict(entry)
    migrated.setdefault("ingest_state", "validated")
    migrated.setdefault("access_level", "raw-only" if migrated.get("source_type") == "pdf" else "full-text")
    migrated.setdefault("processed_path", None)
    migrated.setdefault("derivative_path", None)
    return migrated


def load_registry_document(path: Path = REGISTRY_PATH, contract_root: Path = ROOT) -> dict[str, Any]:
    yaml, _jsonschema = require_contract_dependencies()
    try:
        data_root = path.absolute().parents[1]
        unsafe = symlink_component(path, data_root)
        if unsafe is not None:
            raise ContractError(f"source registry path must not traverse a symlink: {unsafe}")
        if path.stat().st_size > MAX_YAML_BYTES:
            raise ContractError(f"source registry exceeds the {MAX_YAML_BYTES}-byte YAML limit")
        text = path.read_text(encoding="utf-8")
        loaded = yaml.safe_load(text)
    except (OSError, yaml.YAMLError) as exc:
        raise ContractError(f"cannot safely load source registry: {exc}") from exc
    if isinstance(loaded, list):
        document = {"schema_version": REGISTRY_VERSION, "sources": [_legacy_entry(item) for item in loaded]}
    elif isinstance(loaded, dict):
        document = dict(loaded)
        document["sources"] = [_legacy_entry(item) for item in document.get("sources", [])]
    else:
        raise ContractError("source registry must be a mapping or legacy list")
    validate_contract(document, "source-registry", contract_root)
    return document


def parse_registry() -> list[dict[str, Any]]:
    if not REGISTRY_PATH.exists() and not REGISTRY_PATH.is_symlink():
        return []
    return [dict(entry) for entry in load_registry_document()["sources"]]


def write_registry(entries: list[dict[str, Any]]) -> None:
    document = {"schema_version": REGISTRY_VERSION, "sources": sorted(entries, key=lambda item: item["source_id"])}
    validate_contract(document, "source-registry", ROOT)
    yaml, _jsonschema = require_contract_dependencies()
    ordered = {
        "schema_version": REGISTRY_VERSION,
        "sources": [{key: entry[key] for key in FIELD_ORDER} for entry in document["sources"]],
    }
    text = yaml.safe_dump(ordered, sort_keys=False, allow_unicode=True)
    atomic_write_text(REGISTRY_PATH, text, ROOT)


def source_type_for(path: Path) -> str:
    return SOURCE_TYPES_BY_SUFFIX.get(path.suffix.lower(), "other")


def stable_source_id(path: Path, digest: str, entries: list[dict[str, Any]]) -> str:
    for entry in entries:
        if entry["hash_sha256"] == digest:
            return str(entry["source_id"])
    base = f"{today_utc()}-{slugify(path.stem)}"
    by_id = {entry["source_id"]: entry["hash_sha256"] for entry in entries}
    if base not in by_id or by_id[base] == digest:
        return base
    index = 2
    while f"{base}-{index}" in by_id and by_id[f"{base}-{index}"] != digest:
        index += 1
    return f"{base}-{index}"


def upsert_entry(entry: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    entries = parse_registry()
    for index, existing in enumerate(entries):
        if existing["hash_sha256"] == entry["hash_sha256"]:
            if existing["source_id"] != entry["source_id"]:
                raise ContractError("registry hash is associated with a different source ID")
            merged = {**existing, **entry}
            entries[index] = merged
            write_registry(entries)
            return merged, False
        if existing["source_id"] == entry["source_id"]:
            raise ContractError("source ID collision with different content")
    entries.append(entry)
    write_registry(entries)
    return entry, True


def add_source(path: Path) -> tuple[dict[str, Any], bool]:
    """Compatibility API; recoverable ingest should use ``ingest.py`` transitions."""
    path = path.resolve()
    digest = sha256_file(path)
    entries = parse_registry()
    source_id = stable_source_id(path, digest, entries)
    raw_path = RAW_DIR / f"{source_id}{path.suffix.lower() or '.txt'}"
    if symlink_component(raw_path, ROOT) is not None:
        raise RuntimeError("raw evidence path must not traverse a symlink")
    if not raw_path.exists():
        raise RuntimeError("raw evidence must be preserved atomically by tools/ingest.py before registration")
    entry = {
        "source_id": source_id,
        "raw_path": raw_path.relative_to(ROOT).as_posix(),
        "reference_path": f"wiki/references/{source_id}.md",
        "hash_sha256": digest,
        "source_type": source_type_for(path),
        "date_ingested": today_utc(),
        "date_published": "unknown",
        "status": "active",
        "ingest_state": "registered",
        "access_level": "raw-only" if path.suffix.lower() == ".pdf" else "full-text",
        "processed_path": None,
        "derivative_path": None,
    }
    return upsert_entry(entry)


def registered_entry_complete(entry: dict[str, Any]) -> bool:
    raw_path = ROOT / str(entry.get("raw_path", ""))
    reference_path = ROOT / str(entry.get("reference_path", ""))
    digest = entry.get("hash_sha256", "")
    return (
        symlink_component(raw_path, ROOT) is None
        and symlink_component(reference_path, ROOT) is None
        and raw_path.is_file()
        and reference_path.is_file()
        and sha256_file(raw_path) == digest
    )


def validate_registry() -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    seen_hashes: dict[str, str] = {}
    seen_ids: set[str] = set()
    try:
        entries = parse_registry()
    except ContractError as exc:
        return [str(exc)], []
    for entry in entries:
        source_id = str(entry["source_id"])
        raw_path = ROOT / entry["raw_path"]
        reference_path = ROOT / entry["reference_path"]
        digest = entry["hash_sha256"]
        if source_id in seen_ids:
            errors.append(f"{source_id}: duplicate source ID")
        seen_ids.add(source_id)
        if digest in seen_hashes:
            errors.append(f"{source_id}: duplicate hash also used by {seen_hashes[digest]}")
        seen_hashes[digest] = source_id
        if symlink_component(raw_path, ROOT) is not None or not raw_path.is_file():
            errors.append(f"{source_id}: raw path is missing: {entry['raw_path']}")
        elif sha256_file(raw_path) != digest:
            errors.append(f"{source_id}: hash mismatch for {entry['raw_path']}")
        if symlink_component(reference_path, ROOT) is not None or not reference_path.is_file():
            warnings.append(f"{source_id}: reference page is missing: {entry['reference_path']}")
    return errors, warnings


def main(argv: list[str]) -> int:
    if len(argv) < 2 or argv[1] in {"-h", "--help"}:
        print("usage: python3 tools/source_registry.py validate | list")
        return 0
    if argv[1] == "validate":
        errors, warnings = validate_registry()
        for item in errors:
            print(f"FAIL: {item}")
        for item in warnings:
            print(f"WARN: {item}")
        if not errors:
            print(f"PASS: validated {len(parse_registry())} source registry entries")
        return 1 if errors else 0
    if argv[1] == "list":
        for entry in parse_registry():
            print(f"{entry['source_id']}\t{entry['raw_path']}\t{entry['ingest_state']}\t{entry['access_level']}")
        return 0
    print(f"FAIL: unknown command `{argv[1]}`")
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
