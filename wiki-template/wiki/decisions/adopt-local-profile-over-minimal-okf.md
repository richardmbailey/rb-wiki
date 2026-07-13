---
type: Decision
title: "Adopt Local Profile Over Minimal OKF"
description: "The wiki will produce pages under the stricter llm-wiki-profile/0.2 rules while continuing to read older profile 0.1 and minimal OKF pages."
resource: ""
tags: [wiki-template, decision, schema, active]
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

The wiki will produce pages under the stricter llm-wiki-profile/0.2 rules while continuing to read older profile 0.1 and minimal OKF pages.

# Decision

Use the full profile 0.2 page information for all newly created ordinary pages. Continue reading profile 0.1 pages so existing wikis can be upgraded safely.

# Context

Minimal [Open Knowledge Format](/concepts/open-knowledge-format.md) requires only `type`, but the seed design needs stronger metadata for source coverage, review state, routing, and maintenance.

# Options Considered

| Option | Advantages | Disadvantages |
|---|---|---|
| Minimal OKF only | Simple and portable | Too weak for provenance and linting |
| Local profile 0.2 plus compatibility | Better source tracking, review state, consequence controls, and routing | Requires validation and migration tools |

# Rationale

The local profile gives the tools enough structure to validate pages, track review work, distinguish higher-consequence content, and support [Progressive Disclosure](/concepts/progressive-disclosure.md).

# Consequences

External minimal OKF and existing profile 0.1 pages can still be read. Newly produced pages must include the complete profile 0.2 fields. Migration is planned and reviewed before it changes a wiki.

# Review Trigger

Review this decision before any schema migration or external bundle import that conflicts with the local profile.

# Citations

- [LLM-Wiki System Instructions](/references/2026-07-13-llm-wiki-system-instructions.md)

# Change History

- `2026-07-09`: Created from the seed design source.
- `2026-07-13`: Updated the producer decision from profile 0.1 to profile 0.2 while retaining profile 0.1 read compatibility.
