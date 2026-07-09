---
type: Decision
title: "Use OKF-Compatible Markdown Links"
description: "The wiki will use standard Markdown links as canonical links rather than Obsidian-style wikilinks."
resource: ""
tags: [wiki-template, decision, links, active]
timestamp: 2026-07-09T00:00:00Z

created: 2026-07-09
status: active
profile: llm-wiki-profile/0.1
sources:
  - "/references/2026-07-09-llm-wiki-system-instructions.md"
confidence: high
---

The wiki will use standard Markdown links as canonical links rather than Obsidian-style wikilinks.

# Decision

Use standard Markdown links such as `[LLM-Wiki](/concepts/llm-wiki.md)` as the source of truth for page relationships.

# Context

The seed design makes [Open Knowledge Format](/concepts/open-knowledge-format.md) compatibility a core requirement and states that standard Markdown links are canonical.

# Options Considered

| Option | Advantages | Disadvantages |
|---|---|---|
| Standard Markdown links | Portable, parseable, OKF-compatible | Slightly more verbose than wikilinks |
| Obsidian-style wikilinks | Convenient in Obsidian | Not canonical for OKF and harder for simple tools |

# Rationale

Standard Markdown links let deterministic tools build indexes, link checks, and graph data without depending on a single note-taking application.

# Consequences

Agents should create and repair links in Markdown format. Optional compatibility exports may be added later.

# Review Trigger

Review this decision only if the wiki adopts a new interoperability target that requires a different canonical link form.

# Citations

- [LLM-Wiki System Instructions](/references/2026-07-09-llm-wiki-system-instructions.md)

# Change History

- `2026-07-09`: Created from the seed design source.

