---
type: Overview
title: "Wiki Template Overview"
description: "A high-level map of the reusable LLM-wiki template and its source-backed operating model."
resource: ""
tags: [wiki-template, overview, active]
timestamp: 2026-07-09T00:00:00Z

created: 2026-07-09
status: needs-review
profile: llm-wiki-profile/0.1
sources:
  - "/references/2026-07-09-llm-wiki-system-instructions.md"
confidence: medium
---

This wiki template is an initial source-backed knowledge system for compiling durable knowledge about a chosen subject.

# Current Scope

The template currently focuses on the operating foundations needed before larger subject-specific source ingestion:

- [LLM-Wiki](/concepts/llm-wiki.md) as the knowledge-system pattern.
- [Compiled Knowledge](/concepts/compiled-knowledge.md) as the durable synthesis goal.
- [Source Immutability](/concepts/source-immutability.md) as the evidence rule.
- [Progressive Disclosure](/concepts/progressive-disclosure.md) and [Graph Routing](/methods/graph-routing.md) as the routing discipline.
- [Wiki Linting](/methods/wiki-linting.md) as the maintenance routine.

# Main Decisions

- The wiki uses [OKF-compatible Markdown links](/decisions/use-okf-compatible-markdown-links.md).
- The wiki adopts the [local LLM-wiki profile over minimal OKF](/decisions/adopt-local-profile-over-minimal-okf.md).

# Known Gaps

- The wiki needs subject-specific source material beyond the seed design note.
- There are no entity, dataset, project, or contradiction pages yet.
- The initial pages are scaffold syntheses and should be reviewed as more sources arrive.

# Citations

- [LLM-Wiki System Instructions](/references/2026-07-09-llm-wiki-system-instructions.md)

# Change History

- `2026-07-09`: Created during initial wiki setup.
