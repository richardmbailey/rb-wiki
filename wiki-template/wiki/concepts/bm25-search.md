---
type: Concept
title: "BM25 Search"
description: "BM25 search is a lexical retrieval method named in the wiki design as part of better routing."
resource: ""
tags: [wiki-template, search, routing, needs-review]
timestamp: 2026-07-09T00:00:00Z

created: 2026-07-09
status: needs-review
profile: llm-wiki-profile/0.1
sources:
  - "/references/2026-07-09-llm-wiki-system-instructions.md"
confidence: low
---

BM25 search is a lexical retrieval method named in the wiki design as part of better routing.

# Definition

This seed page records BM25 as a planned routing capability. More detailed implementation claims should wait for search-specific sources or code.

# Key Claims

- BM25 can help rank pages by lexical relevance.
- [Hybrid Search](/concepts/hybrid-search.md) can combine BM25 with [Vector Search](/concepts/vector-search.md).
- [SQLite FTS5](/tools/sqlite-fts5.md) is a likely local implementation route.

# Open Questions

- Should the initial query tool mature into SQLite FTS5 BM25, or remain simple until the wiki grows?

# Citations

- [LLM-Wiki System Instructions](/references/2026-07-09-llm-wiki-system-instructions.md)

# Change History

- `2026-07-09`: Created from the seed design source.

