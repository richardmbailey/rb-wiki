---
type: Concept
title: "Progressive Disclosure"
description: "Progressive disclosure is the routing rule that agents should map relevant pages before reading full bodies."
resource: ""
tags: [wiki-template, routing, context, active]
timestamp: 2026-07-09T00:00:00Z

created: 2026-07-09
status: active
profile: llm-wiki-profile/0.1
sources:
  - "/references/2026-07-09-llm-wiki-system-instructions.md"
confidence: high
---

Progressive disclosure is the routing rule that agents should map relevant pages before reading full bodies.

# Definition

The wiki design frames routing as "map first, body second": use compact routing assets before opening detailed content.

# Key Claims

- Progressive disclosure reduces [Context Contamination](/concepts/context-contamination.md).
- It relies on `wiki/index.md`, [Frontmatter](/concepts/frontmatter.md), graph neighborhoods, search, and source registry records.
- It is especially important as the wiki grows beyond a small seed set.

# Relationships

- Implemented by [Graph Routing](/methods/graph-routing.md).
- Supported by [Hybrid Search](/concepts/hybrid-search.md).
- Used in the [LLM-Wiki Operating Model](/syntheses/llm-wiki-operating-model.md).

# Citations

- [LLM-Wiki System Instructions](/references/2026-07-09-llm-wiki-system-instructions.md)

# Change History

- `2026-07-09`: Created from the seed design source.

