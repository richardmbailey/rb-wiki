# AGENTS.md - LLM-Wiki Maintainer

## Mission

This wiki base directory is an LLM-wiki: a persistent, git-backed, OKF-compatible Markdown knowledge base maintained by an LLM agent and deterministic tools.

The goal is to compile raw sources into durable, cited, cross-linked knowledge about the wiki's chosen subject.

Raw sources are immutable evidence. Wiki pages are synthesized, maintained knowledge.

## Design Principles

1. Preserve raw evidence.
2. Maintain an OKF-compatible wiki bundle.
3. Enforce the stricter local profile.
4. Route before reading page bodies.
5. Use deterministic tools for mechanical checks.
6. Use LLM judgement for synthesis and interpretation.
7. Never delete without explicit human approval.
8. Prefer curation over overwriting.
9. Make contradictions explicit.
10. Keep the graph healthy through linting.

## Wiki Base Directory Layout

- `inbox/` - temporary drop zone for new uncatalogued material.
- `sources/raw/` - immutable raw sources. Never edit or delete these.
- `sources/_source_registry.yml` - machine-readable source registry.
- `wiki/` - OKF-compatible knowledge bundle.
- `wiki/index.md` - reserved OKF routing file.
- `wiki/log.md` - reserved OKF update-history file.
- `wiki/overview.md` - high-level synthesis of current wiki state.
- `wiki/concepts/` - concept pages.
- `wiki/entities/` - entity pages.
- `wiki/summaries/` - source or topic summaries.
- `wiki/syntheses/` - reusable higher-level answers and memos.
- `wiki/decisions/` - recorded decisions.
- `wiki/contradictions/` - unresolved tensions.
- `wiki/references/` - source catalog pages.
- `wiki/datasets/` - dataset descriptions.
- `wiki/methods/` - methods and protocols.
- `wiki/tools/` - tools and software descriptions.
- `wiki/projects/` - project pages.
- `schema/` - schemas, prompts, and policies.
- `tools/` - deterministic tooling.
- `reports/` - ingest, lint, and review reports.
- `.wiki_cache/` - generated indexes, graph files, search DBs, and embeddings.

## Hard Rules

1. Never edit, rewrite, casually rename, or delete files in `sources/raw/`.
2. Never delete any file unless the human maintainer explicitly approves.
3. Never remove historical claims merely because newer evidence exists.
4. When evidence changes, append nuance, cite the new source, and mark the evolution.
5. Every important wiki claim must trace to at least one source or reference page.
6. Do not scan all page bodies to find relevance. Use index, frontmatter, graph, and search tools first.
7. Keep ordinary content pages under 1,000 words where possible.
8. Use standard Markdown links as canonical links.
9. Update reciprocal links where appropriate.
10. Run validation after changing the wiki.
11. Record important operations in `wiki/log.md` or an appropriate report.
12. Do not treat `index.md` or `log.md` as ordinary content pages.

## Canonical Local Frontmatter

Every ordinary content page in `wiki/` must begin with:

```yaml
---
type: Concept | Entity | Summary | Synthesis | Decision | Contradiction | Reference | Dataset | Method | Tool | Project | Overview
title: "Human-readable title"
description: "One-sentence description of the page."
resource: ""
tags: [domain, topic, status]
timestamp: YYYY-MM-DDTHH:MM:SSZ

created: YYYY-MM-DD
status: active | draft | stale | deprecated | needs-review
profile: llm-wiki-profile/0.1
sources:
  - "/references/source-id.md"
confidence: high | medium | low | uncertain
---
```

Immediately after the frontmatter, include a one-sentence plain-language summary.

## Source Handling

When ingesting from `inbox/`:

1. Compute a content hash.
2. Create a stable source ID.
3. Copy the original file into `sources/raw/`.
4. Update `sources/_source_registry.yml`.
5. Create a `Reference` page in `wiki/references/`.
6. Only move or remove the inbox copy after successful validation and review.

## Validation Commands

Run these checks after changing the wiki:

```bash
python3 tools/build_index.py
python3 tools/build_graph.py
python3 tools/validate_frontmatter.py
python3 tools/check_reserved_files.py
python3 tools/check_links.py
python3 tools/word_count.py
python3 tools/lint.py --quick
```

If a required command is missing or broken, repair the deterministic tool before relying on manual inspection.

## Cron-Safe Maintenance Commands

Use these for scheduled upkeep:

```bash
python3 tools/wiki_cron.py inbox
python3 tools/wiki_cron.py nightly
python3 tools/wiki_cron.py weekly
```

The inbox command moves only already registered and complete inbox copies into `inbox/processed/YYYY-MM-DD/`. If the matching registry entry is incomplete, the file is routed through ingest so raw preservation, reference pages, validation, and reports can be repaired before it leaves the active inbox. Unsupported or failed files remain in `inbox/` for review.
