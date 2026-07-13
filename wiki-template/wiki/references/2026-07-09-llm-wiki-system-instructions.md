---
type: Reference
title: "LLM-Wiki System Instructions"
description: "A local design specification for building and maintaining an LLM-wiki with immutable sources, cited synthesis, and deterministic tooling."
resource: "sources/raw/2026-07-09-llm-wiki-system-instructions.md"
tags: [wiki-template, llm-wiki, reference, superseded]
timestamp: 2026-07-13T00:00:00Z

created: 2026-07-09
status: deprecated
profile: llm-wiki-profile/0.2
sources: []
confidence: high
review_state: reviewed
review_priority: normal
consequence_tier: ordinary
source_id: "2026-07-09-llm-wiki-system-instructions"
source_type: note
hash_sha256: "45143feba5179fd9dddbeca65a629175224d939eb4b5807269ab86565da50ee7"
date_published: unknown
date_ingested: 2026-07-09
authors: ["Richard Bailey"]
source_access_level: full-text
derived_text: ""
extraction_status: not-applicable
integration_state: integrated
assessment_state: assessed
validated_at: 2026-07-13T00:00:00Z
---

The LLM-Wiki System Instructions define the operating model used to initialize and maintain this wiki template.

This 9 July version is retained as historical evidence. It has been superseded by the [current LLM-Wiki System Instructions](/references/2026-07-13-llm-wiki-system-instructions.md), which add the v0.2 human-agent operating and safety model.

# Source Summary

The source describes a git-backed Markdown knowledge system where raw evidence is preserved under `sources/raw/`, wiki pages act as a cited synthesis layer, and deterministic tools handle validation, search, graph routing, indexing, ingestion, and linting.

# Key Claims

- An LLM-wiki should behave like a knowledge compiler rather than a generic file-chat system.
- Raw sources and synthesized wiki pages must remain separate.
- Agents should route through indexes, frontmatter, graph data, search, and source registries before reading many page bodies.
- Standard Markdown links are the canonical link format.
- The local `llm-wiki-profile/0.1` schema is stricter than baseline OKF.
- Serious deletion, schema changes, duplicate merges, and contradiction resolutions require human approval.

# Extracted Concepts

- [LLM-Wiki](/concepts/llm-wiki.md)
- [Compiled Knowledge](/concepts/compiled-knowledge.md)
- [Open Knowledge Format](/concepts/open-knowledge-format.md)
- [Source Immutability](/concepts/source-immutability.md)
- [Progressive Disclosure](/concepts/progressive-disclosure.md)
- [Wiki Drift](/concepts/wiki-drift.md)
- [Context Contamination](/concepts/context-contamination.md)

# Extracted Methods and Tools

- [Source Ingestion](/methods/source-ingestion.md)
- [Wiki Linting](/methods/wiki-linting.md)
- [Graph Routing](/methods/graph-routing.md)
- [Query CLI](/tools/query-cli.md)

# Links Into Wiki

- [Wiki Template Overview](/overview.md)
- [LLM-Wiki Operating Model](/syntheses/llm-wiki-operating-model.md)
- [LLM-Wiki versus RAG](/syntheses/llm-wiki-vs-rag.md)
- [Use OKF-Compatible Markdown Links](/decisions/use-okf-compatible-markdown-links.md)

# Change History

- `2026-07-09`: Registered as the seed source for the initial wiki setup.
- `2026-07-13`: Marked as superseded after the current v0.2 instructions were registered. The original raw file was preserved unchanged.
