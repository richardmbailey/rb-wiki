#!/usr/bin/env python3
"""Deterministically reconcile source registry, raw evidence, and Reference pages."""

from __future__ import annotations

import sys
from pathlib import Path, PurePosixPath
from typing import Any

from source_registry import load_registry_document, source_type_for
from run_lib import ContractError, symlink_component
from wiki_lib import ROOT, parse_frontmatter, sha256_file
from contracts import load_json_contract
from fs_safety import checked_root, enumerate_regular_files, safe_path


def validate_entry(entry: dict[str, Any], root: Path = ROOT, contract_root: Path = ROOT) -> list[str]:
    root = checked_root(root)
    contract_root = checked_root(contract_root)
    source_id = entry["source_id"]
    errors: list[str] = []
    raw = root / entry["raw_path"]
    reference = root / entry["reference_path"]
    if symlink_component(raw, root) is not None or not raw.is_file():
        errors.append(f"{source_id}: raw evidence is missing or symlinked")
    else:
        if sha256_file(raw) != entry["hash_sha256"]:
            errors.append(f"{source_id}: raw evidence hash mismatch")
        if source_type_for(raw) != entry["source_type"]:
            errors.append(f"{source_id}: raw suffix/source_type mismatch")
    if symlink_component(reference, root) is not None or not reference.is_file():
        errors.append(f"{source_id}: Reference page is missing or symlinked")
    else:
        frontmatter, _body, error = parse_frontmatter(reference, contract_root)
        if error:
            errors.append(f"{source_id}: Reference frontmatter is invalid: {error}")
        else:
            expected = {
                "type": "Reference",
                "source_id": source_id,
                "resource": entry["raw_path"],
                "hash_sha256": entry["hash_sha256"],
                "source_type": entry["source_type"],
            }
            for field, value in expected.items():
                if frontmatter.get(field) != value:
                    errors.append(f"{source_id}: Reference {field} mismatch")
            if frontmatter.get("profile") == "llm-wiki-profile/0.2" and frontmatter.get(
                "source_access_level"
            ) != entry["access_level"]:
                errors.append(f"{source_id}: Reference source_access_level mirror mismatch")
    return errors


def validate_provenance(
    source_id: str | None = None, root: Path = ROOT, contract_root: Path = ROOT
) -> list[str]:
    try:
        root = checked_root(root)
        contract_root = checked_root(contract_root)
    except ContractError as exc:
        return [str(exc)]
    registry_path = root / "sources" / "_source_registry.yml"
    try:
        entries = load_registry_document(registry_path, contract_root)["sources"]
    except ContractError as exc:
        return [str(exc)]
    wiki_dir = root / "wiki"
    errors: list[str] = []
    ids: set[str] = set()
    hashes: set[str] = set()
    raw_paths: dict[str, str] = {}
    reference_paths: dict[str, dict[str, Any]] = {}
    for entry in entries:
        if entry["source_id"] in ids:
            errors.append(f"{entry['source_id']}: duplicate source ID")
        if entry["hash_sha256"] in hashes:
            errors.append(f"{entry['source_id']}: duplicate source hash")
        ids.add(entry["source_id"])
        hashes.add(entry["hash_sha256"])
        if entry["raw_path"] in raw_paths:
            errors.append(
                f"{entry['source_id']}: shared raw path also used by {raw_paths[entry['raw_path']]}"
            )
        raw_paths[entry["raw_path"]] = entry["source_id"]
        if entry["reference_path"] in reference_paths:
            errors.append(f"{entry['source_id']}: shared Reference path")
        reference_paths[entry["reference_path"]] = entry
        if source_id is None or entry["source_id"] == source_id:
            errors.extend(validate_entry(entry, root, contract_root))
    if source_id is not None and source_id not in ids:
        errors.append(f"{source_id}: registry entry not found")
    if source_id is None:
        recovery_raw: set[str] = set()
        recovery_references: set[str] = set()
        state_dir = root / ".wiki_state" / "sources"
        unsafe_state = symlink_component(state_dir, root)
        if unsafe_state is not None:
            errors.append(f"source recovery state traverses a symlink: {unsafe_state}")
        elif state_dir.is_dir():
            for journal in sorted(state_dir.glob("*.json")):
                try:
                    transition = load_json_contract(journal, "source-transition", contract_root)
                except (ContractError, OSError) as exc:
                    errors.append(f"{journal.name}: invalid source recovery journal: {exc}")
                    continue
                if transition["outcome"] != "complete":
                    recovery_raw.add(transition["raw_path"])
                    recovery_references.add(transition["reference_path"])
        try:
            raw_files = enumerate_regular_files(root, "sources/raw")
        except ContractError as exc:
            errors.append(str(exc))
            raw_files = []
        for raw_file in raw_files:
            if raw_file.name == ".gitkeep":
                continue
            relative = raw_file.relative_to(root).as_posix()
            if relative not in raw_paths:
                if relative in recovery_raw:
                    errors.append(f"{relative}: recovery-required by an incomplete source transition")
                else:
                    errors.append(
                        f"{relative}: unregistered raw evidence; register it or quarantine-review without deletion"
                    )
        try:
            pages = enumerate_regular_files(root, "wiki", ".md")
        except ContractError as exc:
            errors.append(str(exc))
            return errors
        reference_source_ids: dict[str, list[str]] = {}
        for page in pages:
            relative_page = "/" + page.relative_to(wiki_dir).as_posix()
            if page.parent == wiki_dir and page.name in {"index.md", "log.md"}:
                continue
            frontmatter, _body, parse_error = parse_frontmatter(page, contract_root)
            relative_root = page.relative_to(root).as_posix()
            if not parse_error and frontmatter.get("type") == "Reference":
                reference_source_ids.setdefault(str(frontmatter.get("source_id")), []).append(relative_root)
                if relative_root not in reference_paths:
                    if relative_root in recovery_references:
                        errors.append(f"{relative_root}: recovery-required by an incomplete source transition")
                    else:
                        errors.append(
                            f"{relative_root}: orphan Reference is not present in the source registry"
                        )
                continue
            if parse_error:
                continue
            for citation in frontmatter.get("sources", []):
                if not isinstance(citation, str):
                    errors.append(f"{relative_page}: non-string source citation")
                    continue
                raw_target = PurePosixPath(citation.lstrip("/")) if citation.startswith("/") else PurePosixPath(
                    page.parent.relative_to(wiki_dir).as_posix()
                ) / citation
                if ".." in raw_target.parts or raw_target.is_absolute() or "\\" in citation:
                    errors.append(f"{relative_page}: source citation escapes wiki/: {citation}")
                    continue
                try:
                    target = safe_path(root, f"wiki/{raw_target.as_posix()}", final_type="file")
                except ContractError as exc:
                    errors.append(f"{relative_page}: unsafe source citation {citation}: {exc}")
                    continue
                relative = target.relative_to(root).as_posix()
                entry = reference_paths.get(relative)
                if entry is None:
                    errors.append(f"{relative_page}: citation is not a registered Reference: {citation}")
                    continue
                cited_frontmatter, _cited_body, cited_error = parse_frontmatter(target, contract_root)
                if cited_error or cited_frontmatter.get("type") != "Reference":
                    errors.append(f"{relative_page}: citation target is not a Reference: {citation}")
                elif cited_frontmatter.get("source_id") != entry["source_id"]:
                    errors.append(f"{relative_page}: citation source ID does not reconcile: {citation}")
        for referenced_id, paths in sorted(reference_source_ids.items()):
            if len(paths) > 1:
                errors.append(
                    f"{referenced_id}: duplicate Reference pages: {', '.join(sorted(paths))}"
                )
    return errors


def main(argv: list[str]) -> int:
    if len(argv) < 2 or argv[1] != "validate":
        print("usage: python3 tools/provenance.py validate [--source-id ID]")
        return 1
    source_id = None
    if len(argv) == 4 and argv[2] == "--source-id":
        source_id = argv[3]
    errors = validate_provenance(source_id)
    if errors:
        for error in errors:
            print(f"FAIL: {error}")
        return 1
    if source_id:
        print(f"PASS: forward provenance validated for {source_id}; reverse global checks skipped")
    else:
        print("PASS: global bidirectional provenance validated")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
