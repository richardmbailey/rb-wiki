---
type: Concept
title: "Retrieval-Augmented Generation"
description: "Retrieval-augmented generation retrieves source snippets at query time, while an LLM-wiki stores durable synthesis for reuse."
resource: ""
tags: [wiki-template, retrieval, rag, needs-review]
timestamp: 2026-07-09T00:00:00Z

created: 2026-07-09
status: needs-review
profile: llm-wiki-profile/0.1
sources:
  - "/references/2026-07-09-llm-wiki-system-instructions.md"
confidence: low
---

Retrieval-augmented generation retrieves source snippets at query time, while an LLM-wiki stores durable synthesis for reuse.

# Definition

This seed page records RAG only as the contrast class used by the LLM-wiki design source. More detailed RAG claims need additional sources.

# Key Claims

- The seed source contrasts a durable wiki with systems that repeatedly search or re-summarize raw documents.
- This wiki should avoid pretending that query-time retrieval alone is the same as maintained [Compiled Knowledge](/concepts/compiled-knowledge.md).

# Relationships

- Compared with [LLM-Wiki](/concepts/llm-wiki.md) in [LLM-Wiki versus RAG](/syntheses/llm-wiki-vs-rag.md).
- May use [Vector Search](/concepts/vector-search.md), [BM25 Search](/concepts/bm25-search.md), or [Hybrid Search](/concepts/hybrid-search.md) as retrieval components.

# Open Questions

- Which RAG architecture sources should be ingested before expanding this page?

# Citations

- [LLM-Wiki System Instructions](/references/2026-07-09-llm-wiki-system-instructions.md)

# Change History

- `2026-07-09`: Created as a minimal contrast page from the seed design source.

