---
type: Tool
title: "Query CLI"
description: "The query CLI provides local routing commands for frontmatter lookup, keyword search, and graph inspection."
resource: "tools/query.py"
tags: [wiki-template, tool, query, active]
timestamp: 2026-07-09T00:00:00Z

created: 2026-07-09
status: active
profile: llm-wiki-profile/0.1
sources:
  - "/references/2026-07-09-llm-wiki-system-instructions.md"
confidence: medium
---

The query CLI provides local routing commands for frontmatter lookup, keyword search, and graph inspection.

# What It Does

`tools/query.py` lets agents route through metadata, lexical search, and graph data before reading many page bodies.

# Interface

```bash
python3 tools/query.py search "agent memory"
python3 tools/query.py frontmatter --type Concept --tag routing
python3 tools/query.py graph neighbors /concepts/llm-wiki.md
python3 tools/query.py graph path /concepts/llm-wiki.md /concepts/retrieval-augmented-generation.md
```

# Inputs

- `wiki/` Markdown files.
- `.wiki_cache/graph.json`.
- Frontmatter fields.

# Outputs

- Ranked page candidates.
- Frontmatter matches.
- Graph neighbors and paths.

# Dependencies

- Python standard library.

# Failure Modes

- Search is currently lexical and should not be treated as mature semantic retrieval.
- Graph queries need a current `.wiki_cache/graph.json`.

# Related Pages

- [Progressive Disclosure](/concepts/progressive-disclosure.md)
- [Graph Routing](/methods/graph-routing.md)
- [Hybrid Search](/concepts/hybrid-search.md)

# Citations

- [LLM-Wiki System Instructions](/references/2026-07-09-llm-wiki-system-instructions.md)

# Change History

- `2026-07-09`: Created from the seed design source.
