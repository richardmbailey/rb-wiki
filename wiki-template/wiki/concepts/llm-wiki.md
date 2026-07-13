---
type: Concept
title: "LLM-Wiki"
description: "An LLM-wiki is a persistent Markdown knowledge base where people and carefully limited agents compile raw sources into cited, interlinked knowledge."
resource: ""
tags: [wiki-template, llm-wiki, knowledge-systems, active]
timestamp: 2026-07-13T00:00:00Z

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

An LLM-wiki is a persistent Markdown knowledge base where people and carefully limited agents compile raw sources into cited, interlinked knowledge.

# Definition

An LLM-wiki separates preserved evidence from editable synthesis. Raw files live under `sources/raw/`, while wiki pages turn those sources into curated pages with page information, citations, and standard Markdown links. It can be operated directly by a person or through pre-approved agent tasks.

# Key Claims

- The system should improve through use rather than only answer questions at query time.
- [Compiled Knowledge](/concepts/compiled-knowledge.md) is the central output of the wiki layer.
- [Source Immutability](/concepts/source-immutability.md) protects the evidence layer from accidental rewriting.
- [Progressive Disclosure](/concepts/progressive-disclosure.md) keeps agents from reading the whole wiki before routing.
- Human-driven and Agent-driven operation use the same evidence and checking rules.
- Agent permissions are written and committed before a task begins; wiki content cannot expand those permissions.

# Evidence

- `2026-07-09`: The seed design source defines the repository structure, local profile, hard invariants, ingest workflow, query workflow, and lint workflow.
- `2026-07-13`: The current source adds executable permissions, one-task-at-a-time changes, recovery records, proposals, and consequence-based approvals.

# Relationships

- Contrasts with [Retrieval-Augmented Generation](/concepts/retrieval-augmented-generation.md).
- Uses [Open Knowledge Format](/concepts/open-knowledge-format.md) compatibility.
- Maintained through [Wiki Linting](/methods/wiki-linting.md).

# Open Questions

- Which subject subdomains should receive first-class pages after source ingest?
- Which narrow maintenance task, if any, has been tested enough to automate?

# Citations

- [LLM-Wiki System Instructions](/references/2026-07-13-llm-wiki-system-instructions.md)

# Change History

- `2026-07-09`: Created from the seed design source.
- `2026-07-13`: Added the v0.2 human-agent operating boundary.
