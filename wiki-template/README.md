# Wiki Template

This directory is a reusable local-first LLM-wiki template for a subject-specific knowledge base.

It follows the `llm-wiki-profile/0.1` operating model:

- immutable raw evidence lives in `sources/raw/`;
- source metadata lives in `sources/_source_registry.yml`;
- cited synthesis lives in `wiki/`;
- deterministic checks live in `tools/`;
- audit and maintenance outputs live in `reports/`.

## Current Status

The template has been initialized from the local seed source [LLM-Wiki System Instructions](/wiki/references/2026-07-09-llm-wiki-system-instructions.md). Most seed pages are intentionally marked `needs-review` or medium confidence until subject-specific sources are ingested.

## Common Commands

```bash
python3 tools/build_index.py
python3 tools/build_graph.py
python3 tools/validate_frontmatter.py
python3 tools/check_reserved_files.py
python3 tools/check_links.py
python3 tools/word_count.py
python3 tools/lint.py --quick
python3 tools/query.py search "agent memory"
python3 tools/query.py frontmatter --type Concept --tag routing
python3 tools/query.py graph neighbors /concepts/llm-wiki.md
```

## Adding Sources

Drop Markdown or text files into `inbox/`, then either ask Codex:

```text
Use $rb-wiki-ingest to process this wiki's inbox.
```

or run manually:

```bash
python3 tools/ingest.py inbox/
```

The ingest flow copies raw inputs into `sources/raw/`, registers hashes, creates reference pages, rebuilds the index and graph, moves successfully processed direct inbox files into `inbox/processed/YYYY-MM-DD/`, and writes an ingest report. Unsupported or ambiguous files remain in `inbox/` for review.

For the cron-safe trigger that moves already registered and complete inbox copies out of the active inbox, run:

```bash
python3 tools/wiki_cron.py inbox
```

If a matching registry entry is incomplete, for example because its raw file or reference page is missing, the cron-safe trigger routes the file back through ingest instead of moving it aside.

Maintenance wrappers:

```bash
python3 tools/wiki_cron.py nightly
python3 tools/wiki_cron.py weekly
```

## Working From Codex

When you are already in Codex, the usual commands are natural-language requests:

```text
Use $rb-wiki-ingest to process this wiki's inbox.
Use $rb-wiki-maintenance to run quick maintenance on this wiki.
Use $rb-wiki-maintenance to run the weekly deep clean.
```

`$rb-wiki-ingest` is for new material in `inbox/`. It preserves raw files, creates reference pages, moves processed inbox files into `inbox/processed/YYYY-MM-DD/`, runs quick checks, and reports anything needing review.

`$rb-wiki-maintenance` is for health checks, graph/index rebuilding, quick lint, nightly upkeep, and weekly review. It should write reports rather than making irreversible changes.
