---
type: Concept
title: "LLM-Wiki"
description: "An LLM-wiki is a persistent Markdown knowledge base where agents compile raw sources into cited, interlinked synthesis."
resource: ""
tags: [wiki-template, llm-wiki, knowledge-systems, active]
timestamp: 2026-07-09T00:00:00Z

created: 2026-07-09
status: active
profile: llm-wiki-profile/0.1
sources:
  - "/references/2026-07-09-llm-wiki-system-instructions.md"
confidence: high
---

An LLM-wiki is a persistent Markdown knowledge base where agents compile raw sources into cited, interlinked synthesis.

# Definition

An LLM-wiki separates immutable evidence from editable synthesis. Raw files live under `sources/raw/`, while wiki pages turn those sources into curated pages with frontmatter, citations, and standard Markdown links.

# Key Claims

- The system should improve through use rather than only answer questions at query time.
- [Compiled Knowledge](/concepts/compiled-knowledge.md) is the central output of the wiki layer.
- [Source Immutability](/concepts/source-immutability.md) protects the evidence layer from accidental rewriting.
- [Progressive Disclosure](/concepts/progressive-disclosure.md) keeps agents from reading the whole wiki before routing.

# Evidence

- `2026-07-09`: The seed design source defines the repository structure, local profile, hard invariants, ingest workflow, query workflow, and lint workflow.

# Relationships

- Contrasts with [Retrieval-Augmented Generation](/concepts/retrieval-augmented-generation.md).
- Uses [Open Knowledge Format](/concepts/open-knowledge-format.md) compatibility.
- Maintained through [Wiki Linting](/methods/wiki-linting.md).

# Open Questions

- Which subject subdomains should receive first-class pages after source ingest?
- What level of automation is appropriate for this wiki's upkeep cadence?

# Citations

- [LLM-Wiki System Instructions](/references/2026-07-09-llm-wiki-system-instructions.md)

# Change History

- `2026-07-09`: Created from the seed design source.
