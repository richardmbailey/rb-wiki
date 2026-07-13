---
type: Overview
title: "Wiki Template Overview"
description: "A high-level map of the current reusable wiki template, its evidence rules, and its human-driven and agent-driven operating models."
resource: ""
tags: [wiki-template, overview, active]
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

This wiki template is the current source-backed starting point for building durable knowledge about a chosen subject under direct human control or carefully limited automation.

# Current Scope

The template currently focuses on the operating foundations needed before larger subject-specific source ingestion:

- [LLM-Wiki](/concepts/llm-wiki.md) as the knowledge-system pattern.
- [Compiled Knowledge](/concepts/compiled-knowledge.md) as the durable synthesis goal.
- [Source Immutability](/concepts/source-immutability.md) as the evidence rule.
- [Progressive Disclosure](/concepts/progressive-disclosure.md) and [Graph Routing](/methods/graph-routing.md) as the routing discipline.
- [Wiki Linting](/methods/wiki-linting.md) as the maintenance routine.
- [LLM-Wiki Operating Model](/syntheses/llm-wiki-operating-model.md) as the guide to Human-driven and Agent-driven work.

# Main Decisions

- The wiki uses [OKF-compatible Markdown links](/decisions/use-okf-compatible-markdown-links.md).
- The wiki adopts the [local LLM-wiki profile over minimal OKF](/decisions/adopt-local-profile-over-minimal-okf.md).
- New wikis begin Human-driven with no active agent permission; automation is introduced one tested task at a time.

# Known Gaps

- The wiki needs subject-specific source material beyond the seed design note.
- There are no entity, dataset, project, or contradiction pages yet.
- The initial pages are scaffold syntheses and should be reviewed as more sources arrive.
- Cross-host coordination and automatic meaning-based judgement remain outside the current v0.2 controls.

# Citations

- [LLM-Wiki System Instructions](/references/2026-07-13-llm-wiki-system-instructions.md)

# Change History

- `2026-07-09`: Created during initial wiki setup.
- `2026-07-13`: Refreshed from the current v0.2 system instructions and reviewed against the implemented template.
