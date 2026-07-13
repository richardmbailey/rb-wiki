---
type: Synthesis
title: "LLM-Wiki versus RAG"
description: "An LLM-wiki stores maintained synthesis, while RAG usually retrieves source material at query time."
resource: ""
tags: [wiki-template, synthesis, rag, needs-review]
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

An LLM-wiki stores maintained synthesis, while RAG usually retrieves source material at query time.

# Answer

The seed design distinguishes an [LLM-Wiki](/concepts/llm-wiki.md) from a generic retrieval setup by where durable knowledge lives. In an LLM-wiki, valuable synthesis becomes a maintained page. In [Retrieval-Augmented Generation](/concepts/retrieval-augmented-generation.md), the answer is often reconstructed from retrieved snippets for each query.

# Supporting Evidence

- The seed source says the wiki should behave like a knowledge compiler.
- It frames raw evidence as separate from the [Compiled Knowledge](/concepts/compiled-knowledge.md) layer.
- It requires source-backed pages, routing tools, validation, graph updates, and linting.

# Interpretation

For subject-specific knowledge work, the wiki pattern is useful when the knowledge base should improve over time. RAG remains useful as a retrieval component, but the operating model here treats retrieval as routing support rather than the whole knowledge system.

# Contradictions and Caveats

- This page has only the seed design as a source. It needs RAG architecture sources before making broader technical claims.

# Related Pages

- [Hybrid Search](/concepts/hybrid-search.md)
- [Progressive Disclosure](/concepts/progressive-disclosure.md)
- [Source Ingestion](/methods/source-ingestion.md)

# Citations

- [LLM-Wiki System Instructions](/references/2026-07-13-llm-wiki-system-instructions.md)

# Change History

- `2026-07-09`: Created from the seed design source.
