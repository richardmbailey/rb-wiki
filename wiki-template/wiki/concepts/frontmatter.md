---
type: Concept
title: "Frontmatter"
description: "Frontmatter is the YAML metadata block used for page type, routing, validation, provenance, and maintenance state."
resource: ""
tags: [wiki-template, metadata, okf, active]
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

Frontmatter is the YAML metadata block used for page type, routing, validation, provenance, and maintenance state.

# Definition

Every ordinary wiki page uses frontmatter to expose fields such as `type`, `title`, `description`, `tags`, `timestamp`, `status`, `sources`, and `confidence`.

# Key Claims

- Frontmatter lets deterministic tools validate pages without interpreting the whole body.
- [Open Knowledge Format](/concepts/open-knowledge-format.md) requires at least a `type` field, while this wiki's local profile requires more fields.
- [Query CLI](/tools/query-cli.md) supports frontmatter queries.

# Relationships

- Validated by `tools/validate_frontmatter.py`.
- Used by `tools/build_index.py` to produce the reserved index.
- Supports [Progressive Disclosure](/concepts/progressive-disclosure.md).

# Citations

- [LLM-Wiki System Instructions](/references/2026-07-13-llm-wiki-system-instructions.md)

# Change History

- `2026-07-09`: Created from the seed design source.

