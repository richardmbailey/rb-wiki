#!/usr/bin/env python3
"""Build the wiki link graph cache."""

from __future__ import annotations

import sys

from wiki_lib import CACHE_DIR, build_graph_data, load_current_graph_cache, write_json


def main() -> int:
    graph = load_current_graph_cache()
    if graph is not None:
        print(
            "PASS: reused current .wiki_cache/graph.json "
            f"with {len(graph['nodes'])} nodes and {len(graph['edges'])} edges"
        )
        return 0
    graph = build_graph_data()
    path = CACHE_DIR / "graph.json"
    write_json(path, graph)
    print(
        "PASS: wrote .wiki_cache/graph.json "
        f"with {len(graph['nodes'])} nodes and {len(graph['edges'])} edges"
    )
    if graph["orphans_excluding_reserved"]:
        print("WARN: pages without non-reserved inbound links:")
        for node in graph["orphans_excluding_reserved"]:
            print(f"- {node}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
