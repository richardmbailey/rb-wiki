---
type: Concept
title: "Wiki Drift"
description: "Wiki drift is the failure mode where synthesis pages become stale relative to newer sources or related pages."
resource: ""
tags: [wiki-template, maintenance, drift, active]
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

Wiki drift is the failure mode where synthesis pages become stale relative to newer sources or related pages.

# Definition

Drift happens when new evidence changes the state of knowledge but high-level pages, overviews, or central syntheses do not reflect the change.

# Key Claims

- Stale high-degree pages are risky because many future routes pass through them.
- [Wiki Linting](/methods/wiki-linting.md) should flag stale pages, overview drift, contradiction candidates, and unsupported claims.
- [Compiled Knowledge](/concepts/compiled-knowledge.md) needs active maintenance to remain useful.

# Relationships

- Prevented by [Source Ingestion](/methods/source-ingestion.md) and regular linting.
- Interacts with [Context Contamination](/concepts/context-contamination.md), because stale routing can lead an agent into irrelevant or outdated bodies.

# Citations

- [LLM-Wiki System Instructions](/references/2026-07-13-llm-wiki-system-instructions.md)

# Change History

- `2026-07-09`: Created from the seed design source.

