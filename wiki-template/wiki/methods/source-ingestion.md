---
type: Method
title: "Source Ingestion"
description: "Source ingestion is the workflow for registering raw inputs, creating reference pages, and updating cited wiki synthesis."
resource: ""
tags: [wiki-template, ingest, provenance, active]
timestamp: 2026-07-09T00:00:00Z

created: 2026-07-09
status: active
profile: llm-wiki-profile/0.1
sources:
  - "/references/2026-07-09-llm-wiki-system-instructions.md"
confidence: high
---

Source ingestion is the workflow for registering raw inputs, creating reference pages, and updating cited wiki synthesis.

# Purpose

The method preserves evidence before interpretation, then makes the source visible to the wiki graph through a reference page.

# Procedure

1. Put a raw file in `inbox/`.
2. Compute its SHA-256 hash.
3. Copy the raw file into `sources/raw/`.
4. Update `sources/_source_registry.yml`.
5. Create or update a page in `wiki/references/`.
6. Route through [Progressive Disclosure](/concepts/progressive-disclosure.md) before editing synthesis pages.
7. Rebuild `wiki/index.md` and `.wiki_cache/graph.json`.
8. Run quick lint and write an ingest report.

# Inputs

- Markdown or text files in `inbox/`.
- Existing source registry entries.
- Existing wiki routing assets.

# Outputs

- Immutable raw source copy.
- Source registry entry.
- Reference page.
- Optional cited synthesis updates.
- Ingest report.

# Failure Modes

- Duplicate source hash.
- Unsupported file type.
- Missing hash or broken raw path.
- Unclear source metadata that needs human review.

# Related Tools

- [Query CLI](/tools/query-cli.md)
- [SQLite FTS5](/tools/sqlite-fts5.md)

# Citations

- [LLM-Wiki System Instructions](/references/2026-07-09-llm-wiki-system-instructions.md)

# Change History

- `2026-07-09`: Created from the seed design source.

