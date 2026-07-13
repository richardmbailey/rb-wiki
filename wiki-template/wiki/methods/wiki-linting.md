---
type: Method
title: "Wiki Linting"
description: "Wiki linting is the deterministic and review-oriented maintenance workflow for catching structural problems and knowledge drift."
resource: ""
tags: [wiki-template, linting, maintenance, active]
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

Wiki linting is the deterministic and review-oriented maintenance workflow for catching structural problems and knowledge drift.

# Purpose

Linting keeps the wiki usable by checking reserved files, page information, links, graph structure, word counts, source coverage, duplicate candidates, and signs that knowledge pages may be out of date.

# Procedure

1. Run `python3 tools/lint.py --quick` after ordinary edits.
2. Check reserved files and validate ordinary page information.
3. Check standard Markdown links, source records, citations, and the generated graph.
4. Count page words and detect duplicate names or titles.
5. Record each result as `pass`, `warn`, `fail`, or `not_run`. `not_run` means the assessment did not happen; it is never treated as a pass.
6. Use full lint for a deeper review and write a report under `reports/lint/`.
7. Treat meaning-based assessments as work for an agent or person, not as proof from a mechanical check.
8. For scheduled maintenance, use a committed maintenance grant and the nightly or weekly `tools/wiki_cron.py` command.

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
- Treating a check that did not run as though it passed.
- Treating a structurally valid citation as proof that the statement is true.

# Related Tools

- [Query CLI](/tools/query-cli.md)
- [Graph Routing](/methods/graph-routing.md)

# Citations

- [LLM-Wiki System Instructions](/references/2026-07-13-llm-wiki-system-instructions.md)

# Change History

- `2026-07-09`: Created from the seed design source.
- `2026-07-13`: Updated for typed v0.2 outcomes and grant-controlled scheduled maintenance.
