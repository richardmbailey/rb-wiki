---
type: Method
title: "Wiki Linting"
description: "Wiki linting is the deterministic and review-oriented maintenance workflow for catching structural problems and knowledge drift."
resource: ""
tags: [wiki-template, linting, maintenance, active]
timestamp: 2026-07-09T00:00:00Z

created: 2026-07-09
status: active
profile: llm-wiki-profile/0.1
sources:
  - "/references/2026-07-09-llm-wiki-system-instructions.md"
confidence: high
---

Wiki linting is the deterministic and review-oriented maintenance workflow for catching structural problems and knowledge drift.

# Purpose

Linting keeps the wiki usable by checking reserved files, frontmatter, links, graph structure, word counts, source coverage, duplicate candidates, and drift signals.

# Procedure

1. Check reserved files.
2. Validate ordinary page frontmatter.
3. Check standard Markdown links.
4. Count page words.
5. Detect duplicate slugs and titles.
6. Build the graph and inspect orphan pages.
7. Write a report under `reports/lint/`.

# Inputs

- `wiki/` pages.
- `sources/_source_registry.yml`.
- `.wiki_cache/graph.json`.

# Outputs

- Quick or full lint report.
- Prioritized review items.
- Validation exit status.

# Failure Modes

- Treating reserved files as ordinary pages.
- Ignoring pages with empty source coverage.
- Making substantive edits during lint rather than reporting them.

# Related Tools

- [Query CLI](/tools/query-cli.md)
- [Graph Routing](/methods/graph-routing.md)

# Citations

- [LLM-Wiki System Instructions](/references/2026-07-09-llm-wiki-system-instructions.md)

# Change History

- `2026-07-09`: Created from the seed design source.

