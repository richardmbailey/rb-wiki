---
type: Concept
title: "Context Contamination"
description: "Context contamination occurs when an agent reads too much irrelevant or stale material before forming a synthesis."
resource: ""
tags: [wiki-template, routing, failure-mode, needs-review]
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

Context contamination occurs when an agent reads too much irrelevant or stale material before forming a synthesis.

# Definition

In this wiki, context contamination is avoided by routing through compact metadata and graph/search tools before opening full page bodies.

# Key Claims

- The agent should map candidate pages first and read page bodies second.
- [Progressive Disclosure](/concepts/progressive-disclosure.md) is the main operating discipline for reducing irrelevant context.
- [Graph Routing](/methods/graph-routing.md) and search help narrow the reading set.

# Relationships

- A failure mode for [LLM-Wiki](/concepts/llm-wiki.md) maintenance.
- Related to [Wiki Drift](/concepts/wiki-drift.md).
- Reduced by [Hybrid Search](/concepts/hybrid-search.md).

# Citations

- [LLM-Wiki System Instructions](/references/2026-07-13-llm-wiki-system-instructions.md)

# Change History

- `2026-07-09`: Created from the seed design source.

