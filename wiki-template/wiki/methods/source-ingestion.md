---
type: Method
title: "Source Ingestion"
description: "Source ingestion is the workflow for registering raw inputs, creating reference pages, and updating cited wiki synthesis."
resource: ""
tags: [wiki-template, ingest, provenance, active]
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

Source ingestion is the workflow for registering raw inputs, creating reference pages, and updating cited wiki synthesis.

# Purpose

The method preserves evidence before interpretation, then makes the source visible to the wiki graph through a reference page.

# Procedure

1. Put a raw file in `inbox/`.
2. Create and commit a short-lived ingest grant covering only the required input and output folders.
3. Run `python3 tools/wiki_cron.py inbox --authority YOUR-INGEST-GRANT`; do not call `tools/ingest.py` directly.
4. The safety program records the input, computes its SHA-256 hash, and preserves an unchanged copy in `sources/raw/`.
5. It updates `sources/_source_registry.yml` and creates or updates the matching page in `wiki/references/`.
6. It checks the source record, raw-file hash, reference page, and links in both directions.
7. It rebuilds `wiki/index.md` and `.wiki_cache/graph.json`, runs quick checks, and writes an ingest and run report.
8. It moves the inbox copy aside only after every required step succeeds. Interrupted work resumes from its recorded step.
9. Any later synthesis should route through [Progressive Disclosure](/concepts/progressive-disclosure.md) and use a reviewed proposal when running without continual human direction.

# Inputs

- Markdown, text, or PDF files in `inbox/`.
- Existing source registry entries.
- Existing wiki routing assets.

# Outputs

- Immutable raw source copy.
- Source registry entry.
- Reference page.
- Optional cited synthesis updates.
- Ingest and recovery records.

# Failure Modes

- Duplicate source hash.
- Unsupported file type.
- Missing hash or broken raw path.
- Failed or empty PDF text extraction, including scanned or encrypted PDFs that require manual review.
- Unclear source metadata that needs human review.
- An unsafe path, changed input, unavailable permission, competing task, or interrupted transition.

# Related Tools

- [Query CLI](/tools/query-cli.md)
- [SQLite FTS5](/tools/sqlite-fts5.md)

# Citations

- [LLM-Wiki System Instructions](/references/2026-07-13-llm-wiki-system-instructions.md)

# Change History

- `2026-07-09`: Created from the seed design source.
- `2026-07-13`: Updated for grant-controlled, recoverable v0.2 inbox processing.
