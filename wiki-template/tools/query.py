#!/usr/bin/env python3
"""Route through frontmatter, keyword search, and graph data."""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import deque

from wiki_lib import load_graph, load_pages


def tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


def command_search(mode: str, query: str, limit: int) -> int:
    if mode != "search":
        print(
            json.dumps(
                {
                    "error": "unavailable-capability",
                    "capability": f"{mode}-search",
                    "available": False,
                    "recommended_action": "use `query.py search` for implemented lexical search",
                },
                sort_keys=True,
            )
        )
        return 2
    query_terms = tokenize(query)
    if not query_terms:
        print("FAIL: search query is empty")
        return 1

    scored: list[tuple[int, str, str, str]] = []
    for page in load_pages():
        if page["error"]:
            continue
        fm = page["frontmatter"]
        haystack = " ".join(
            [
                str(fm.get("title", "")),
                str(fm.get("description", "")),
                " ".join(str(tag) for tag in fm.get("tags", [])),
                page["body"],
            ]
        ).lower()
        score = sum(haystack.count(term) for term in query_terms)
        if score:
            scored.append((score, page["wiki_path"], str(fm.get("title", "")), str(fm.get("description", ""))))

    scored.sort(key=lambda item: (-item[0], item[1]))
    if not scored:
        print(f"No {mode} hits for: {query}")
        return 0

    for score, path, title, description in scored[:limit]:
        print(f"{score}\t{path}\t{title}\t{description}")
    return 0


def command_frontmatter(page_type: str | None, tag: str | None, status: str | None) -> int:
    matches = []
    for page in load_pages():
        if page["error"]:
            continue
        fm = page["frontmatter"]
        if page_type and fm.get("type") != page_type:
            continue
        if status and fm.get("status") != status:
            continue
        if tag and tag not in [str(item) for item in fm.get("tags", [])]:
            continue
        matches.append(page)

    for page in sorted(matches, key=lambda item: item["wiki_path"]):
        fm = page["frontmatter"]
        print(f"{page['wiki_path']}\t{fm.get('type')}\t{fm.get('status')}\t{fm.get('title')}")
    print(f"Matched {len(matches)} page(s)")
    return 0


def command_graph_neighbors(page: str) -> int:
    graph = load_graph()
    if page not in graph["nodes"]:
        print(f"FAIL: unknown graph node `{page}`")
        return 1
    print(json.dumps(
        {
            "page": page,
            "inbound": graph["inbound"].get(page, []),
            "outbound": graph["outbound"].get(page, []),
            "degree": graph["degree"].get(page, {}),
        },
        indent=2,
        sort_keys=True,
    ))
    return 0


def command_graph_path(start: str, end: str) -> int:
    graph = load_graph()
    nodes = set(graph["nodes"])
    if start not in nodes or end not in nodes:
        print("FAIL: both start and end pages must exist in the graph")
        return 1
    queue: deque[list[str]] = deque([[start]])
    seen = {start}
    while queue:
        path = queue.popleft()
        current = path[-1]
        if current == end:
            print(" -> ".join(path))
            return 0
        neighbors = set(graph["outbound"].get(current, [])) | set(graph["inbound"].get(current, []))
        for neighbor in sorted(neighbors):
            if neighbor not in seen:
                seen.add(neighbor)
                queue.append(path + [neighbor])
    print(f"No path found between {start} and {end}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Route through the LLM-wiki")
    subparsers = parser.add_subparsers(dest="command", required=True)

    for name in ["search", "bm25", "vector", "hybrid"]:
        search_parser = subparsers.add_parser(name)
        search_parser.add_argument("query")
        search_parser.add_argument("--limit", type=int, default=10)

    frontmatter_parser = subparsers.add_parser("frontmatter")
    frontmatter_parser.add_argument("--type")
    frontmatter_parser.add_argument("--tag")
    frontmatter_parser.add_argument("--status")

    graph_parser = subparsers.add_parser("graph")
    graph_sub = graph_parser.add_subparsers(dest="graph_command", required=True)
    neighbors = graph_sub.add_parser("neighbors")
    neighbors.add_argument("page")
    path = graph_sub.add_parser("path")
    path.add_argument("start")
    path.add_argument("end")

    args = parser.parse_args(argv)
    if args.command in {"search", "bm25", "vector", "hybrid"}:
        return command_search(args.command, args.query, args.limit)
    if args.command == "frontmatter":
        return command_frontmatter(args.type, args.tag, args.status)
    if args.command == "graph" and args.graph_command == "neighbors":
        return command_graph_neighbors(args.page)
    if args.command == "graph" and args.graph_command == "path":
        return command_graph_path(args.start, args.end)
    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
