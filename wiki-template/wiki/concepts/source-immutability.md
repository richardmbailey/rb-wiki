---
type: Concept
title: "Source Immutability"
description: "Source immutability is the rule that raw evidence files are preserved without editing, renaming, or deletion by agents."
resource: ""
tags: [wiki-template, evidence, provenance, active]
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

Source immutability is the rule that raw evidence files are preserved without editing, renaming, or deletion by agents.

# Definition

Files under `sources/raw/` are the evidence layer. Agents may create reference pages and synthesis pages, but they must not mutate raw source files.

# Key Claims

- Immutable raw sources make later review and correction possible.
- [Source Ingestion](/methods/source-ingestion.md) must hash and register raw files before synthesis.
- Contradictions should be curated through new evidence and explicit notes rather than by overwriting earlier claims.

# Relationships

- Supports [LLM-Wiki](/concepts/llm-wiki.md) governance.
- Protects [Compiled Knowledge](/concepts/compiled-knowledge.md) from losing provenance.
- Checked by source registry validation in [Query CLI](/tools/query-cli.md) workflows.

# Citations

- [LLM-Wiki System Instructions](/references/2026-07-13-llm-wiki-system-instructions.md)

# Change History

- `2026-07-09`: Created from the seed design source.

