---
type: Decision
title: "Adopt Local Profile Over Minimal OKF"
description: "The wiki will enforce the stricter llm-wiki-profile/0.1 schema for local pages while remaining compatible with minimal OKF consumers."
resource: ""
tags: [wiki-template, decision, schema, active]
timestamp: 2026-07-09T00:00:00Z

created: 2026-07-09
status: active
profile: llm-wiki-profile/0.1
sources:
  - "/references/2026-07-09-llm-wiki-system-instructions.md"
confidence: high
---

The wiki will enforce the stricter llm-wiki-profile/0.1 schema for local pages while remaining compatible with minimal OKF consumers.

# Decision

Use the full local frontmatter profile for all locally created ordinary pages.

# Context

Minimal [Open Knowledge Format](/concepts/open-knowledge-format.md) requires only `type`, but the seed design needs stronger metadata for source coverage, review state, routing, and maintenance.

# Options Considered

| Option | Advantages | Disadvantages |
|---|---|---|
| Minimal OKF only | Simple and portable | Too weak for provenance and linting |
| Local profile plus OKF compatibility | Better governance and routing | Requires validation tools |

# Rationale

The local profile gives deterministic tools enough structure to validate pages and support [Progressive Disclosure](/concepts/progressive-disclosure.md).

# Consequences

External minimal OKF pages can still be ingested, but locally produced pages must include full profile metadata.

# Review Trigger

Review this decision before any schema migration or external bundle import that conflicts with the local profile.

# Citations

- [LLM-Wiki System Instructions](/references/2026-07-09-llm-wiki-system-instructions.md)

# Change History

- `2026-07-09`: Created from the seed design source.

