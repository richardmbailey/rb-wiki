---
type: Concept
title: "Open Knowledge Format"
description: "Open Knowledge Format is the portable Markdown bundle baseline that this wiki extends with a stricter local profile."
resource: ""
tags: [wiki-template, okf, interoperability, active]
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

Open Knowledge Format is the portable Markdown bundle baseline that this wiki extends with a stricter local profile.

# Definition

The seed design treats OKF as an exchange format made of Markdown files, YAML frontmatter, standard Markdown links, and reserved `index.md` and `log.md` files.

# Key Claims

- OKF compatibility supports portability across tools and agents.
- The local profile remains stricter than baseline OKF so the wiki can enforce citations, source handling, and maintenance checks.
- [Frontmatter](/concepts/frontmatter.md) is the basic machine-readable layer for page routing and validation.

# Relationships

- Implemented through the decision to [adopt a local profile over minimal OKF](/decisions/adopt-local-profile-over-minimal-okf.md).
- Depends on [Use OKF-Compatible Markdown Links](/decisions/use-okf-compatible-markdown-links.md).
- Supports [LLM-Wiki](/concepts/llm-wiki.md) interoperability.

# Open Questions

- Which external OKF bundles should this wiki ingest or export first?

# Citations

- [LLM-Wiki System Instructions](/references/2026-07-13-llm-wiki-system-instructions.md)

# Change History

- `2026-07-09`: Created from the seed design source.

