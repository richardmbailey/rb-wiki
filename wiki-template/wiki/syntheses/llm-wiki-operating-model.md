---
type: Synthesis
title: "LLM-Wiki Operating Model"
description: "This wiki can be run under direct human control or through carefully limited, pre-approved agent tasks."
resource: ""
tags: [wiki-template, synthesis, operating-model, active]
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

This wiki can be run under direct human control or through carefully limited, pre-approved agent tasks.

# Answer

The recommended starting point is the Human-driven model. A person chooses each task, reviews the changes, and creates the Git commit. Direct human editing needs no permission file. An agent that changes files works under a narrow `manual-assist` grant.

The Agent-driven model is for one small, well-tested task at a time. A committed, enabled, time-limited grant defines exactly what the agent may do. Routine scheduled work and proposed content use `scheduled-propose`. Applying normal page content uses `authorised-autonomous-apply` and may apply only the exact content of a committed proposal.

In both models, new material lands in `inbox/`, is preserved through [Source Ingestion](/methods/source-ingestion.md), becomes a source record and reference page, and supports ordinary wiki pages only when cited.

# Supporting Evidence

- The current source defines the separation between evidence and synthesis.
- New wikis start with no active grant and introduce automation only after a supervised run succeeds.
- [Source Immutability](/concepts/source-immutability.md), standard Markdown links, validation tools, graph routing, and [Wiki Linting](/methods/wiki-linting.md) apply in both operating models.
- High-consequence work, where an error could cause serious harm, requires a separate approval tied to the exact proposal.

# Interpretation

The ordinary knowledge cycle is capture, ingest, check, review, commit, query, synthesise, and maintain. Automation does not replace that cycle; it limits who starts a step and what may happen without another human instruction.

The safety program allows only one controlled change-making task at a time, records interrupted work for recovery, and checks the grant again before accepting the result. Agents may never delete raw evidence or push changes to a remote repository.

# Contradictions and Caveats

- Structural checks can confirm files, links, permissions, and source records, but they cannot prove that every statement is true.
- The v0.2 controls assume one writable wiki on one host. They do not coordinate separate machines changing the same wiki.
- Automation schedules and active grants are not included by default.

# Related Pages

- [LLM-Wiki](/concepts/llm-wiki.md)
- [Graph Routing](/methods/graph-routing.md)
- [Query CLI](/tools/query-cli.md)
- [Adopt Local Profile Over Minimal OKF](/decisions/adopt-local-profile-over-minimal-okf.md)

# Citations

- [LLM-Wiki System Instructions](/references/2026-07-13-llm-wiki-system-instructions.md)

# Change History

- `2026-07-09`: Created from the seed design source.
- `2026-07-13`: Updated for the Human-driven and Agent-driven v0.2 operating models.
