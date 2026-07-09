---
type: Synthesis
title: "LLM-Wiki Operating Model"
description: "The operating model for this wiki is capture, ingest, validate, review, commit, query, synthesize, lint, and maintain."
resource: ""
tags: [wiki-template, synthesis, operating-model, active]
timestamp: 2026-07-09T00:00:00Z

created: 2026-07-09
status: active
profile: llm-wiki-profile/0.1
sources:
  - "/references/2026-07-09-llm-wiki-system-instructions.md"
confidence: high
---

The operating model for this wiki is capture, ingest, validate, review, commit, query, synthesize, lint, and maintain.

# Answer

This wiki should operate as a small knowledge compiler for subject-specific material. New material lands in `inbox/`, gets preserved through [Source Ingestion](/methods/source-ingestion.md), becomes source metadata and reference pages, and then supports ordinary wiki pages only when cited.

# Supporting Evidence

- The seed source defines the separation between evidence and synthesis.
- It requires [Source Immutability](/concepts/source-immutability.md), standard Markdown links, validation tools, graph routing, and lint reports.
- It treats [Wiki Linting](/methods/wiki-linting.md) as an ongoing maintenance workflow.

# Interpretation

The most important early discipline is to make the deterministic checks boring and reliable before adding a large volume of subject-specific sources. Once the skeleton is stable, repeated queries can become reusable syntheses.

# Contradictions and Caveats

- Automation schedules have not yet been created.
- The content scope is still broad and should be narrowed as source material arrives.

# Related Pages

- [LLM-Wiki](/concepts/llm-wiki.md)
- [Graph Routing](/methods/graph-routing.md)
- [Query CLI](/tools/query-cli.md)
- [Adopt Local Profile Over Minimal OKF](/decisions/adopt-local-profile-over-minimal-okf.md)

# Citations

- [LLM-Wiki System Instructions](/references/2026-07-09-llm-wiki-system-instructions.md)

# Change History

- `2026-07-09`: Created from the seed design source.
