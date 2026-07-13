---
type: Tool
title: "SQLite FTS5"
description: "SQLite FTS5 is a candidate local search backend for future BM25-style wiki routing."
resource: ""
tags: [wiki-template, tool, search, needs-review]
timestamp: 2026-07-09T00:00:00Z

created: 2026-07-09
status: needs-review
profile: llm-wiki-profile/0.2
sources:
  - "/references/2026-07-13-llm-wiki-system-instructions.md"
confidence: low
review_state: pending
review_priority: normal
consequence_tier: ordinary
---

SQLite FTS5 is a candidate local search backend for future BM25-style wiki routing.

# What It Does

This page records SQLite FTS5 as a likely local search implementation path. It needs source-backed expansion before becoming a technical guide.

# Interface

```bash
python3 tools/query.py bm25 "routing discipline"
```

# Inputs

- Wiki page text and frontmatter.

# Outputs

- Ranked lexical search hits.

# Dependencies

- Python's `sqlite3` module if the local SQLite build includes FTS5.

# Failure Modes

- The current wiki starts with simpler lexical search.
- FTS5 availability varies by SQLite build and should be validated before relying on it.

# Related Pages

- [BM25 Search](/concepts/bm25-search.md)
- [Hybrid Search](/concepts/hybrid-search.md)
- [Query CLI](/tools/query-cli.md)

# Citations

- [LLM-Wiki System Instructions](/references/2026-07-13-llm-wiki-system-instructions.md)

# Change History

- `2026-07-09`: Created from the seed design source.
