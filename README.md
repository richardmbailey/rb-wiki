# RB Wiki

RB Wiki is a starter kit for building local LLM-wikis, which are git-backed Markdown knowledge bases where raw evidence is preserved, source-backed synthesis is curated, and deterministic tools keep the wiki healthy. It uses Google's Open Knowledge Framework standard for compatibility (https://cloud.google.com/blog/products/data-analytics/how-the-open-knowledge-format-can-improve-data-sharing).

The wikis generate here are specifically designed as durable knowledge systems rather than a one-off "chat with my files" workflow. Raw sources go into the `inbox` and are stored in an immutable evidence layer. The wiki creates citations and cross-linked syntheses. Scripts handle validation, routing, graph building, ingest, and maintenance.

It is easiest to run this by opening the root folder within Codex or ClaudeCode, to handle the chat interface and make use of the skills.

## What Is Included

- `llm-wiki-system-instructions.md` - the full operating specification for the LLM-wiki pattern. If you want to build your own wiki system from scratch you can give this to Codex/ClaudeCode etc. and ask them to build it.
- `wiki-template/` - a complete reusable starter wiki with schema files, tools, seed pages, reports, and an initial source registry. If you don't want to build your own, duplicate this template and work from there to modify the files as you wish. The `skills` below will help you do this using your agent. Alternatively ask you agent to read the `llm-wiki-system-instructions.md` file, review the template duplicate, and then set it up with your topic-specific needs.
- `skills/` - optional Codex skills for creating a new wiki, processing inbox material, running maintenance, and operating an existing wiki.

## Repository Layout

```text
rb-wiki/
  README.md
  llm-wiki-system-instructions.md
  wiki-template/
  skills/
    rb-wiki/
    rb-new-wiki/
    rb-wiki-ingest/
    rb-wiki-maintenance/
```

Inside each wiki, the important separation is:

```text
inbox/          temporary drop zone for new files
sources/raw/    immutable raw evidence
sources/        source registry and metadata
wiki/           OKF-compatible Markdown knowledge bundle
schema/         local profile, policies, and prompts
tools/          deterministic scripts
reports/        ingest, lint, and review outputs
.wiki_cache/    generated routing and graph caches
```

## Quick Start

Use the setup script to create a configured wiki from the template:

```bash
python3 skills/rb-new-wiki/scripts/new_wiki.py \
  --template wiki-template \
  --parent .. \
  --name example-wiki \
  --title "Example Wiki" \
  --subject "example subject" \
  --tag example \
  --description "Example Wiki is a local-first LLM-wiki for example subject."
cd ../example-wiki
PYTHONDONTWRITEBYTECODE=1 python3 tools/source_registry.py validate
PYTHONDONTWRITEBYTECODE=1 python3 tools/lint.py --quick
```

Open the `wiki/` folder in Obsidian, VS Code, or any Markdown editor. The canonical links are standard Markdown links, so the bundle remains portable outside Obsidian.

You can also copy `wiki-template/` manually, but then update the copied `README.md`, `AGENTS.md`, `wiki/overview.md`, `wiki/log.md`, and generated routing outputs before using it as a subject wiki.

## Creating A New Wiki With Codex

If you use Codex skills, copy the folders under `skills/` into your Codex skills directory, or point Codex at them in your own skill workflow. Then ask:

```text
Use $rb-new-wiki to create a new wiki from this template.
```

The `rb-new-wiki` skill will gather the subject, display title, base directory name, domain tag, description, initial source choices, and optional automation preferences.

## Adding Sources

Drop Markdown or text files into a wiki's `inbox/`, then either ask Codex:

```text
Use $rb-wiki-ingest to process this wiki's inbox.
```

or run the deterministic ingest wrapper:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 tools/wiki_cron.py inbox
```

Successful ingest copies files into `sources/raw/`, records hashes in `sources/_source_registry.yml`, creates reference pages in `wiki/references/`, rebuilds routing assets, runs quick checks, and moves processed inbox files into `inbox/processed/YYYY-MM-DD/`.

Unsupported, failed, ambiguous, encrypted, or very large files stay in `inbox/` for review.

## Maintenance

Run quick checks after ordinary edits:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 tools/lint.py --quick
```

Run cron-safe maintenance wrappers for regular upkeep:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 tools/wiki_cron.py nightly
PYTHONDONTWRITEBYTECODE=1 python3 tools/wiki_cron.py weekly
```

The nightly path rebuilds routing assets, validates source integrity, and runs quick lint. The weekly path runs deeper health review and writes reports. These routines are intentionally conservative: they write reports and perform mechanical checks, but they should not delete files, merge pages, rename important pages, resolve serious contradictions, or rewrite substantive content without human approval.

## Operating Principles

1. Preserve raw evidence in `sources/raw/`.
2. Keep `wiki/` as the portable Markdown knowledge bundle.
3. Use standard Markdown links as canonical links.
4. Route through index, graph, frontmatter, search, and source registry before reading lots of page bodies.
5. Cite reference pages for important claims.
6. Treat reports as review inputs, not permission for irreversible edits.
7. Use git history as the exact audit trail and `wiki/log.md` as the readable operational history.

## Public Use Notes

This repository is a shareable toolkit and template. Be careful not to put private raw sources, private reports, credentials, or unpublished collaborator material into a public fork. Create subject-specific wikis in separate private or project repositories when the source material is sensitive.

Before publishing your own derivative, check that your template or example content does not contain private sources.

## License

This project is released under the MIT License. See `LICENSE`.
