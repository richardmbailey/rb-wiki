---
type: Reference
title: "LLM-Wiki System Instructions — v0.2"
description: "The current design and operating specification for a source-backed wiki that can be run under human control or carefully limited automation."
resource: "sources/raw/2026-07-13-llm-wiki-system-instructions.md"
tags: [wiki-template, llm-wiki, reference, operations, active]
timestamp: 2026-07-13T00:00:00Z

created: 2026-07-13
status: active
profile: llm-wiki-profile/0.2
sources: []
confidence: high
review_state: reviewed
review_priority: normal
consequence_tier: ordinary
source_id: "2026-07-13-llm-wiki-system-instructions"
source_type: note
hash_sha256: "65105ad863ff965ee7b2b6c694c18c87a56f2ce960ad2c5c4f4571022840209c"
date_published: unknown
date_ingested: 2026-07-13
authors: ["Richard Bailey"]
source_access_level: full-text
derived_text: ""
extraction_status: not-applicable
integration_state: integrated
assessment_state: assessed
validated_at: 2026-07-13T00:00:00Z
---

The current LLM-Wiki System Instructions define both the knowledge-building method and the v0.2 controls for safe human-directed and agent-directed operation.

# Source Summary

The source describes a Git-backed Markdown wiki that keeps original evidence separate from editable knowledge pages. It combines source records, citations, links, routing tools, structural checks, and human review so the wiki can improve over time without losing its evidence trail.

The v0.2 addendum turns important operating rules into files and checks the software can enforce. It defines a safe human-driven starting model, narrowly authorised agent-driven work, recoverable source processing, proposals and approvals for content changes, and explicit limits on what agents may do.

# Key Claims

- Original sources must be preserved unchanged; new versions are added rather than overwriting old evidence.
- Wiki pages are editable synthesis and should trace important statements back to source pages.
- New wikis should begin in the Human-driven model with no active agent permission.
- Direct human Markdown editing does not need a grant, but every agent or managed change-making command does.
- Agent-driven work uses committed, enabled, time-limited permission files and introduces automation one small task at a time.
- `scheduled-propose` may perform approved routine work or prepare proposals without directly rewriting ordinary pages.
- `authorised-autonomous-apply` may apply only the exact content of an approved proposal.
- High-consequence work, where an error could cause serious harm, requires a separate approval tied to the exact proposal.
- Controlled jobs run one at a time, leave recovery records after interruption, never delete raw evidence, and never push changes to a remote repository.
- Automated checks can confirm structure and source links, but they do not prove that every statement is true.

# Extracted Concepts

- [LLM-Wiki](/concepts/llm-wiki.md)
- [Compiled Knowledge](/concepts/compiled-knowledge.md)
- [Source Immutability](/concepts/source-immutability.md)
- [Progressive Disclosure](/concepts/progressive-disclosure.md)
- [Wiki Drift](/concepts/wiki-drift.md)
- [Context Contamination](/concepts/context-contamination.md)

# Extracted Methods and Tools

- [Source Ingestion](/methods/source-ingestion.md)
- [Wiki Linting](/methods/wiki-linting.md)
- [Graph Routing](/methods/graph-routing.md)
- [Query CLI](/tools/query-cli.md)

# Links Into Wiki

- [Wiki Template Overview](/overview.md)
- [LLM-Wiki Operating Model](/syntheses/llm-wiki-operating-model.md)
- [LLM-Wiki versus RAG](/syntheses/llm-wiki-vs-rag.md)
- [Use OKF-Compatible Markdown Links](/decisions/use-okf-compatible-markdown-links.md)

# Version History

- The [9 July instructions](/references/2026-07-09-llm-wiki-system-instructions.md) remain available as historical evidence.
- This 13 July version adds the v0.2 Human-Agent Operations Addendum and supersedes the older version for current operation.

# Change History

- `2026-07-13`: Registered as the current seed source and reviewed against the v0.2 template implementation.
