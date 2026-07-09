#!/usr/bin/env python3
"""Register and validate immutable raw sources."""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

from wiki_lib import RAW_DIR, ROOT, SOURCES_DIR, sha256_file, slugify, today_utc

REGISTRY_PATH = SOURCES_DIR / "_source_registry.yml"

SOURCE_TYPES_BY_SUFFIX = {
    ".pdf": "pdf",
    ".md": "note",
    ".markdown": "note",
    ".txt": "note",
    ".text": "note",
    ".html": "web",
    ".htm": "web",
    ".csv": "dataset",
    ".tsv": "dataset",
    ".json": "dataset",
    ".py": "code",
    ".js": "code",
    ".ts": "code",
    ".mp3": "audio",
    ".m4a": "audio",
    ".wav": "audio",
    ".mp4": "video",
    ".mov": "video",
    ".png": "image",
    ".jpg": "image",
    ".jpeg": "image",
}


def parse_registry() -> list[dict[str, str]]:
    if not REGISTRY_PATH.exists():
        return []
    entries: list[dict[str, str]] = []
    current: dict[str, str] | None = None
    for raw_line in REGISTRY_PATH.read_text(encoding="utf-8").splitlines():
        if not raw_line.strip():
            continue
        if raw_line.startswith("- "):
            if current is not None:
                entries.append(current)
            current = {}
            remainder = raw_line[2:]
            if ":" in remainder:
                key, value = remainder.split(":", 1)
                current[key.strip()] = value.strip().strip('"')
        elif raw_line.startswith("  ") and current is not None and ":" in raw_line:
            key, value = raw_line.strip().split(":", 1)
            current[key.strip()] = value.strip().strip('"')
    if current is not None:
        entries.append(current)
    return entries


def write_registry(entries: list[dict[str, str]]) -> None:
    REGISTRY_PATH.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    for entry in sorted(entries, key=lambda item: item["source_id"]):
        lines.append(f'- source_id: "{entry["source_id"]}"')
        for key in [
            "raw_path",
            "reference_path",
            "hash_sha256",
            "source_type",
            "date_ingested",
            "date_published",
            "status",
        ]:
            lines.append(f'  {key}: "{entry[key]}"')
        lines.append("")
    REGISTRY_PATH.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def source_type_for(path: Path) -> str:
    return SOURCE_TYPES_BY_SUFFIX.get(path.suffix.lower(), "other")


def unique_source_id(path: Path, entries: list[dict[str, str]]) -> str:
    base = f"{today_utc()}-{slugify(path.stem)}"
    existing = {entry["source_id"] for entry in entries}
    if base not in existing:
        return base
    index = 2
    while f"{base}-{index}" in existing:
        index += 1
    return f"{base}-{index}"


def add_source(path: Path) -> tuple[dict[str, str], bool]:
    path = path.resolve()
    entries = parse_registry()
    digest = sha256_file(path)
    for entry in entries:
        if entry.get("hash_sha256") == digest:
            ensure_registered_raw(entry, path, digest)
            return entry, True

    source_id = unique_source_id(path, entries)
    raw_name = f"{source_id}{path.suffix.lower() or '.txt'}"
    raw_path = RAW_DIR / raw_name
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, raw_path)

    entry = {
        "source_id": source_id,
        "raw_path": raw_path.relative_to(ROOT).as_posix(),
        "reference_path": f"wiki/references/{source_id}.md",
        "hash_sha256": digest,
        "source_type": source_type_for(path),
        "date_ingested": today_utc(),
        "date_published": "unknown",
        "status": "active",
    }
    entries.append(entry)
    write_registry(entries)
    return entry, False


def ensure_registered_raw(entry: dict[str, str], source_path: Path, digest: str) -> None:
    source_id = entry.get("source_id", "<missing>")
    raw_value = entry.get("raw_path", "")
    if not raw_value:
        raise RuntimeError(f"{source_id}: duplicate source has no raw_path in registry")

    raw_path = ROOT / raw_value
    if raw_path.exists():
        if not raw_path.is_file():
            raise RuntimeError(f"{source_id}: registered raw path is not a file: {raw_value}")
        actual = sha256_file(raw_path)
        if actual != digest:
            raise RuntimeError(f"{source_id}: registered raw file hash does not match registry: {raw_value}")
        return

    raw_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source_path, raw_path)
    entry["_raw_restored"] = "true"


def registered_entry_complete(entry: dict[str, str]) -> bool:
    raw_value = entry.get("raw_path", "")
    reference_value = entry.get("reference_path", "")
    digest = entry.get("hash_sha256", "")
    if not raw_value or not reference_value or not digest:
        return False

    raw_path = ROOT / raw_value
    reference_path = ROOT / reference_value
    if not raw_path.is_file() or not reference_path.is_file():
        return False
    return sha256_file(raw_path) == digest


def validate_registry() -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    seen_hashes: dict[str, str] = {}
    for entry in parse_registry():
        source_id = entry.get("source_id", "<missing>")
        raw_path = ROOT / entry.get("raw_path", "")
        reference_path = ROOT / entry.get("reference_path", "")
        digest = entry.get("hash_sha256", "")
        if not raw_path.exists():
            errors.append(f"{source_id}: raw path is missing: {entry.get('raw_path')}")
            continue
        actual = sha256_file(raw_path)
        if actual != digest:
            errors.append(f"{source_id}: hash mismatch for {entry.get('raw_path')}")
        if not reference_path.exists():
            warnings.append(f"{source_id}: reference page is missing: {entry.get('reference_path')}")
        if digest in seen_hashes:
            warnings.append(f"{source_id}: duplicate hash also used by {seen_hashes[digest]}")
        seen_hashes[digest] = source_id
    return errors, warnings


def main(argv: list[str]) -> int:
    if len(argv) < 2 or argv[1] in {"-h", "--help"}:
        print("usage: python3 tools/source_registry.py add PATH | validate | list")
        return 0

    command = argv[1]
    if command == "add":
        if len(argv) < 3:
            print("FAIL: add requires a path")
            return 1
        for item in argv[2:]:
            entry, duplicate = add_source(Path(item))
            prefix = "DUPLICATE" if duplicate else "ADDED"
            print(f"{prefix}: {entry['source_id']} -> {entry['raw_path']}")
        return 0

    if command == "validate":
        errors, warnings = validate_registry()
        if errors:
            print("FAIL: source registry validation failed")
            for error in errors:
                print(f"- {error}")
            for warning in warnings:
                print(f"- WARN: {warning}")
            return 1
        if warnings:
            print("WARN: source registry validation passed with warnings")
            for warning in warnings:
                print(f"- {warning}")
            return 0
        print(f"PASS: validated {len(parse_registry())} source registry entries")
        return 0

    if command == "list":
        for entry in parse_registry():
            print(f"{entry['source_id']}\t{entry['raw_path']}\t{entry['status']}")
        return 0

    print(f"FAIL: unknown command `{command}`")
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
