#!/usr/bin/env python3
"""Shared helpers for the local LLM-wiki tools."""

from __future__ import annotations

import hashlib
import json
import re
from collections import defaultdict, deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
WIKI_DIR = ROOT / "wiki"
SOURCES_DIR = ROOT / "sources"
RAW_DIR = SOURCES_DIR / "raw"
CACHE_DIR = ROOT / ".wiki_cache"
REPORTS_DIR = ROOT / "reports"

RESERVED_NAMES = {"index.md", "log.md"}
LOCAL_PROFILE = "llm-wiki-profile/0.1"
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
    return path.resolve().relative_to(ROOT).as_posix()


def wiki_relative(path: Path) -> str:
    return "/" + path.resolve().relative_to(WIKI_DIR).as_posix()


def is_reserved(path: Path) -> bool:
    return path.parent.resolve() == WIKI_DIR.resolve() and path.name in RESERVED_NAMES


def iter_markdown_pages(include_reserved: bool = False) -> list[Path]:
    pages = sorted(WIKI_DIR.rglob("*.md"))
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


def parse_frontmatter(path: Path) -> tuple[dict[str, Any], str, str | None]:
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
    return parse_simple_yaml(yaml_text), body, None


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
    pages = iter_markdown_pages(include_reserved=True)
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

    return {
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
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def load_graph() -> dict[str, Any]:
    graph_path = CACHE_DIR / "graph.json"
    if not graph_path.exists():
        return build_graph_data()
    return json.loads(read_text(graph_path))


def print_lines(lines: Iterable[str]) -> None:
    for line in lines:
        print(line)
