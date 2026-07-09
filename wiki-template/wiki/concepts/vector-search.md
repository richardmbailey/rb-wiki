---
type: Concept
title: "Vector Search"
description: "Vector search is a semantic retrieval method named as a future mature routing layer for the wiki."
resource: ""
tags: [wiki-template, search, embeddings, needs-review]
timestamp: 2026-07-09T00:00:00Z

created: 2026-07-09
status: needs-review
profile: llm-wiki-profile/0.1
sources:
  - "/references/2026-07-09-llm-wiki-system-instructions.md"
confidence: low
---

Vector search is a semantic retrieval method named as a future mature routing layer for the wiki.

# Definition

The seed design lists vector search and embeddings as later-stage capabilities after basic index, frontmatter, graph, and lexical search are working.

# Key Claims

- Vector search should not be built before the minimal routing and validation layer exists.
- [Hybrid Search](/concepts/hybrid-search.md) can combine vector ranking with [BM25 Search](/concepts/bm25-search.md).

# Open Questions

- Which local embedding model should be used if semantic search becomes necessary?
- What privacy and reproducibility requirements should govern embeddings?

# Citations

- [LLM-Wiki System Instructions](/references/2026-07-09-llm-wiki-system-instructions.md)

# Change History

- `2026-07-09`: Created from the seed design source.

