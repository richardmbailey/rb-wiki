---
type: Concept
title: "Hybrid Search"
description: "Hybrid search combines lexical and semantic retrieval signals to route an agent toward relevant wiki pages."
resource: ""
tags: [wiki-template, search, routing, needs-review]
timestamp: 2026-07-09T00:00:00Z

created: 2026-07-09
status: needs-review
profile: llm-wiki-profile/0.2
sources:
  - "/references/2026-07-13-llm-wiki-system-instructions.md"
confidence: medium
review_state: pending
review_priority: normal
consequence_tier: ordinary
---

Hybrid search combines lexical and semantic retrieval signals to route an agent toward relevant wiki pages.

# Definition

The seed design identifies hybrid search as a mature routing option that can combine BM25, vector search, and graph expansion.

# Key Claims

- Hybrid search is useful once the wiki is large or semantically varied enough to need more than a compact index.
- [Reciprocal Rank Fusion](/concepts/reciprocal-rank-fusion.md) can combine multiple ranked retrieval lists.
- The current `tools/query.py` starts with keyword search and leaves full vector retrieval as a future maturation step.

# Relationships

- Combines [BM25 Search](/concepts/bm25-search.md) and [Vector Search](/concepts/vector-search.md).
- Supports [Progressive Disclosure](/concepts/progressive-disclosure.md).
- Used by [Graph Routing](/methods/graph-routing.md) when search results are expanded through link neighborhoods.

# Citations

- [LLM-Wiki System Instructions](/references/2026-07-13-llm-wiki-system-instructions.md)

# Change History

- `2026-07-09`: Created from the seed design source.

