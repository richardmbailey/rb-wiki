#!/usr/bin/env python3
"""Shared helpers for the local LLM-wiki tools."""

from __future__ import annotations

import json
import hashlib
import os
import re
from collections import defaultdict, deque
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from run_lib import (
    MAX_YAML_BYTES,
    ContractError,
    RunError,
    atomic_write_text,
    require_contract_dependencies,
    symlink_component,
    validate_contract,
)
from fs_safety import enumerate_regular_files
from contracts import load_json_contract

ROOT = Path(__file__).resolve().parents[1]
WIKI_DIR = ROOT / "wiki"
SOURCES_DIR = ROOT / "sources"
RAW_DIR = SOURCES_DIR / "raw"
CACHE_DIR = ROOT / ".wiki_cache"
REPORTS_DIR = ROOT / "reports"

RESERVED_NAMES = {"index.md", "log.md"}
LOCAL_PROFILE = "llm-wiki-profile/0.2"
SUPPORTED_PROFILES = {"llm-wiki-profile/0.1", "llm-wiki-profile/0.2"}
REQUIRED_FIELDS = [
    "type",
    "title",
    "description",
    "resource",
    "tags",
    "timestamp",
    "created",
    "status",
    "profile",
    "sources",
    "confidence",
]
ALLOWED_TYPES = {
    "Concept",
    "Entity",
    "Summary",
    "Synthesis",
    "Decision",
    "Contradiction",
    "Reference",
    "Dataset",
    "Method",
    "Tool",
    "Project",
    "Overview",
}
ALLOWED_STATUSES = {"active", "draft", "stale", "deprecated", "needs-review"}
ALLOWED_CONFIDENCE = {"high", "medium", "low", "uncertain"}

LINK_RE = re.compile(r"(?<!!)\[[^\]]+\]\(([^)]+)\)")
OBSIDIAN_RE = re.compile(r"\[\[[^\]]+\]\]")
WORD_RE = re.compile(r"\b[\w'-]+\b")
TIMESTAMP_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def today_utc() -> str:
    return now_utc()[:10]


def run_timestamp_utc() -> str:
    return now_utc().replace(":", "")


def unique_sibling_path(path: Path) -> Path:
    if not path.exists():
        return path
    stem = path.stem
    suffix = path.suffix
    index = 2
    while True:
        candidate = path.with_name(f"{stem}-{index}{suffix}")
        if not candidate.exists():
            return candidate
        index += 1


def root_relative(path: Path) -> str:
    return path.absolute().relative_to(ROOT.absolute()).as_posix()


def wiki_relative(path: Path) -> str:
    return "/" + path.absolute().relative_to(WIKI_DIR.absolute()).as_posix()


def is_reserved(path: Path) -> bool:
    return path.parent.absolute() == WIKI_DIR.absolute() and path.name in RESERVED_NAMES


def iter_markdown_pages(include_reserved: bool = False) -> list[Path]:
    pages: list[Path] = []
    for current, directories, files in os.walk(WIKI_DIR, topdown=True, followlinks=False):
        current_path = Path(current)
        directories[:] = sorted(
            name for name in directories if not (current_path / name).is_symlink()
        )
        pages.extend(
            current_path / name for name in sorted(files) if Path(name).suffix == ".md"
        )
    pages.sort()
    if include_reserved:
        return pages
    return [path for path in pages if not is_reserved(path)]


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def strip_quotes(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def parse_inline_list(value: str) -> list[str]:
    inner = value.strip()[1:-1].strip()
    if not inner:
        return []
    return [strip_quotes(part.strip()) for part in inner.split(",")]


def parse_scalar(value: str) -> Any:
    value = value.strip()
    if value in {"[]", ""}:
        return [] if value == "[]" else ""
    if value.startswith("[") and value.endswith("]"):
        return parse_inline_list(value)
    return strip_quotes(value)


def parse_simple_yaml(yaml_text: str) -> dict[str, Any]:
    data: dict[str, Any] = {}
    current_list_key: str | None = None
    for raw_line in yaml_text.splitlines():
        if not raw_line.strip():
            continue
        if raw_line.startswith("  - ") and current_list_key:
            data.setdefault(current_list_key, []).append(parse_scalar(raw_line[4:]))
            continue
        if raw_line.startswith(" ") and not raw_line.startswith("  - "):
            continue
        if ":" not in raw_line:
            continue
        key, value = raw_line.split(":", 1)
        key = key.strip()
        value = value.strip()
        if value == "":
            data[key] = []
            current_list_key = key
        else:
            data[key] = parse_scalar(value)
            current_list_key = None
    return data


def parse_frontmatter(path: Path, contract_root: Path = ROOT) -> tuple[dict[str, Any], str, str | None]:
    wiki_dir = next((candidate for candidate in path.absolute().parents if candidate.name == "wiki"), None)
    wiki_root = wiki_dir.parent if wiki_dir is not None else path.absolute().parent
    try:
        unsafe = symlink_component(path, wiki_root)
    except ContractError as exc:
        return {}, "", str(exc)
    if unsafe is not None:
        return {}, "", f"Markdown page path must not traverse a symlink: {unsafe}"
    text = read_text(path)
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, text, "missing YAML frontmatter"
    end_index: int | None = None
    for index, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            end_index = index
            break
    if end_index is None:
        return {}, text, "unterminated YAML frontmatter"
    yaml_text = "\n".join(lines[1:end_index])
    body = "\n".join(lines[end_index + 1 :])
    if len(yaml_text.encode("utf-8")) > MAX_YAML_BYTES:
        return {}, body, f"frontmatter exceeds the {MAX_YAML_BYTES}-byte limit"
    try:
        yaml, _jsonschema = require_contract_dependencies()
    except RunError as exc:
        return {}, body, str(exc)
    try:
        loaded = yaml.safe_load(yaml_text)
        if not isinstance(loaded, dict):
            return {}, body, "frontmatter must be a YAML mapping"
        frontmatter = normalize_yaml_scalars(loaded)
        # Reserved OKF files have their own compact metadata shape and are not
        # ordinary content pages governed by the page-frontmatter contract.
        if frontmatter.get("profile") == "llm-wiki-profile/0.2" and not is_reserved(path):
            validate_contract(frontmatter, "page-frontmatter", contract_root)
        return frontmatter, body, None
    except (ContractError, yaml.YAMLError) as exc:
        return {}, body, f"unsafe or invalid YAML frontmatter: {exc}"


def normalize_yaml_scalars(value: Any) -> Any:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, list):
        return [normalize_yaml_scalars(item) for item in value]
    if isinstance(value, dict):
        return {str(key): normalize_yaml_scalars(item) for key, item in value.items()}
    return value


def first_sentence(body: str) -> str:
    clean = body.strip()
    if not clean:
        return ""
    for line in clean.splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            return stripped
    return ""


def body_word_count(body: str) -> int:
    return len(WORD_RE.findall(body))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def slugify(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-") or "source"


def split_link_target(raw_target: str) -> str:
    target = raw_target.strip()
    if " " in target and not target.startswith("<"):
        target = target.split(" ", 1)[0]
    if target.startswith("<") and target.endswith(">"):
        target = target[1:-1]
    return target.split("#", 1)[0]


def is_external_target(target: str) -> bool:
    return bool(re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", target))


def resolve_wiki_link(source_page: Path, raw_target: str) -> Path | None:
    target = split_link_target(raw_target)
    if not target or is_external_target(target):
        return None
    if target.startswith("/"):
        return (WIKI_DIR / target.lstrip("/")).resolve()
    return (source_page.parent / target).resolve()


def extract_markdown_links(text: str) -> list[str]:
    return [match.group(1) for match in LINK_RE.finditer(text)]


def local_link_to_wiki_path(source_page: Path, raw_target: str) -> str | None:
    resolved = resolve_wiki_link(source_page, raw_target)
    if resolved is None:
        return None
    try:
        return "/" + resolved.relative_to(WIKI_DIR.resolve()).as_posix()
    except ValueError:
        return None


def load_pages() -> list[dict[str, Any]]:
    pages: list[dict[str, Any]] = []
    for path in iter_markdown_pages(include_reserved=False):
        frontmatter, body, error = parse_frontmatter(path)
        pages.append(
            {
                "path": path,
                "wiki_path": wiki_relative(path),
                "frontmatter": frontmatter,
                "body": body,
                "error": error,
                "summary": first_sentence(body),
            }
        )
    return pages


def build_graph_data() -> dict[str, Any]:
    pages = [path for path in iter_markdown_pages(include_reserved=True) if not path.is_symlink()]
    nodes = sorted(wiki_relative(path) for path in pages)
    edges: list[dict[str, str]] = []
    outbound: dict[str, set[str]] = defaultdict(set)
    inbound: dict[str, set[str]] = defaultdict(set)
    inbound_non_reserved: dict[str, set[str]] = defaultdict(set)

    node_set = set(nodes)
    for path in pages:
        source = wiki_relative(path)
        text = read_text(path)
        for target in extract_markdown_links(text):
            wiki_target = local_link_to_wiki_path(path, target)
            if not wiki_target or wiki_target not in node_set:
                continue
            outbound[source].add(wiki_target)
            inbound[wiki_target].add(source)
            if not is_reserved(path):
                inbound_non_reserved[wiki_target].add(source)
            edges.append({"source": source, "target": wiki_target})

    ordinary_nodes = [node for node in nodes if node not in {"/index.md", "/log.md"}]
    orphans = sorted(node for node in ordinary_nodes if not inbound[node])
    orphans_excluding_reserved = sorted(node for node in ordinary_nodes if not inbound_non_reserved[node])

    graph = {
        "schema_version": "rb-wiki-graph-cache/0.2",
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "source_manifest_digest": graph_source_manifest_digest(),
        "cache_status": "current",
        "nodes": nodes,
        "edges": sorted(edges, key=lambda item: (item["source"], item["target"])),
        "outbound": {node: sorted(outbound[node]) for node in nodes},
        "inbound": {node: sorted(inbound[node]) for node in nodes},
        "inbound_non_reserved": {node: sorted(inbound_non_reserved[node]) for node in nodes},
        "degree": {
            node: {
                "in": len(inbound[node]),
                "out": len(outbound[node]),
                "in_non_reserved": len(inbound_non_reserved[node]),
            }
            for node in nodes
        },
        "orphans": orphans,
        "orphans_excluding_reserved": orphans_excluding_reserved,
        "components": connected_components(nodes, outbound),
    }
    validate_contract(graph, "graph-cache", ROOT)
    return graph


def graph_source_manifest_digest() -> str:
    paths = iter_markdown_pages(include_reserved=True)
    unsafe_inputs: list[str] = []
    for relative in ("schema/page_schema.yml", "schema/link_policy.md"):
        path = ROOT / relative
        unsafe = symlink_component(path, ROOT)
        if unsafe is not None:
            unsafe_inputs.append(relative)
        elif path.is_file():
            paths.append(path)
    items: list[str] = []
    for path in sorted(set(paths)):
        relative = path.relative_to(ROOT).as_posix()
        unsafe = symlink_component(path, ROOT)
        if unsafe is not None:
            unsafe_inputs.append(relative)
            continue
        items.append(f"{relative}\0{hashlib.sha256(path.read_bytes()).hexdigest()}")
    items.extend(f"{relative}\0unsafe-symlink" for relative in sorted(set(unsafe_inputs)))
    return hashlib.sha256("\n".join(items).encode("utf-8")).hexdigest()


def connected_components(nodes: list[str], outbound: dict[str, set[str]]) -> list[list[str]]:
    undirected: dict[str, set[str]] = {node: set() for node in nodes}
    for source, targets in outbound.items():
        for target in targets:
            if target in undirected:
                undirected[source].add(target)
                undirected[target].add(source)

    seen: set[str] = set()
    components: list[list[str]] = []
    for node in nodes:
        if node in seen:
            continue
        queue: deque[str] = deque([node])
        seen.add(node)
        component: list[str] = []
        while queue:
            current = queue.popleft()
            component.append(current)
            for neighbor in sorted(undirected[current]):
                if neighbor not in seen:
                    seen.add(neighbor)
                    queue.append(neighbor)
        components.append(sorted(component))
    return sorted(components, key=lambda part: (-len(part), part[0] if part else ""))


def write_json(path: Path, data: Any) -> None:
    atomic_write_text(path, json.dumps(data, indent=2, sort_keys=True) + "\n", ROOT)


def load_graph() -> dict[str, Any]:
    current = load_current_graph_cache()
    if current is not None:
        return current
    graph = build_graph_data()
    graph["cache_status"] = "rebuilt-in-memory"
    return graph


def load_current_graph_cache() -> dict[str, Any] | None:
    graph_path = CACHE_DIR / "graph.json"
    try:
        graph = load_json_contract(graph_path, "graph-cache", ROOT)
        if graph["source_manifest_digest"] != graph_source_manifest_digest():
            raise ContractError("graph cache source manifest is stale")
        return graph
    except (ContractError, OSError):
        return None


def print_lines(lines: Iterable[str]) -> None:
    for line in lines:
        print(line)
