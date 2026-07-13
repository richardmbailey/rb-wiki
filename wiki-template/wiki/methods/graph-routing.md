---
type: Method
title: "Graph Routing"
description: "Graph routing uses Markdown links and generated graph data to narrow which wiki pages an agent should read."
resource: ""
tags: [wiki-template, graph, routing, active]
timestamp: 2026-07-09T00:00:00Z

created: 2026-07-09
status: active
profile: llm-wiki-profile/0.2
sources:
  - "/references/2026-07-13-llm-wiki-system-instructions.md"
confidence: high
review_state: reviewed
review_priority: normal
consequence_tier: ordinary
---

Graph routing uses Markdown links and generated graph data to narrow which wiki pages an agent should read.

# Purpose

Graph routing helps an agent inspect neighborhoods, paths, or orphan pages before opening full page bodies.

# Procedure

1. Extract standard Markdown links from wiki pages.
2. Normalize local links to wiki-root paths.
3. Write graph data to `.wiki_cache/graph.json`.
4. Use graph neighbors or paths to select relevant pages.
5. Combine graph results with [Hybrid Search](/concepts/hybrid-search.md) when useful.

# Inputs

- Markdown links from wiki pages.
- Page frontmatter and index entries.

# Outputs

- Nodes and edges.
- Inbound and outbound degree counts.
- Orphan candidates.
- Connected components.

# Failure Modes

- Broken links.
- Dense but meaningless links.
- Important pages with no inbound links.

# Related Tools

- [Query CLI](/tools/query-cli.md)

# Citations

- [LLM-Wiki System Instructions](/references/2026-07-13-llm-wiki-system-instructions.md)

# Change History

- `2026-07-09`: Created from the seed design source.

