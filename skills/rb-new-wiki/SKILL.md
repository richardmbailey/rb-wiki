---
name: "rb-new-wiki"
description: "Use when the user asks Codex to create a new LLM-wiki from wiki-template, gather setup choices, copy the template, reconfigure subject/title/tag metadata, validate the new wiki, and optionally set up wiki automations."
---

# RB New Wiki

Use this skill when the user asks to start, create, duplicate, clone, or set up a new LLM-wiki from `wiki-template`.

This is the frictionless setup path for new wikis. Use `rb-wiki` for broader design or operation of an existing wiki, `rb-wiki-ingest` for processing an inbox, and `rb-wiki-maintenance` for health checks after creation.

## Required Context

- A template wiki directory, usually the `wiki-template` directory from this public starter kit or a copied equivalent.
- A target parent directory where the new wiki base directory should be created.
- The new wiki's subject, display title, filesystem-safe base directory name, domain tag, and one-sentence description.
- Python with the template's declared dependencies installed. From the starter-kit root, use `python3 -m pip install -e wiki-template` before invoking setup; the setup script validates the staged wiki with that same interpreter.

Ask only for missing choices that materially affect the new wiki. If the user gives a clear subject, derive conservative defaults and state them before running setup:

- display title: title-case subject plus `Wiki` when needed;
- base directory: lowercase or existing-style kebab-case subject plus `-wiki` when needed;
- domain tag: lowercase kebab-case subject;
- parent directory: the current workspace or the parent directory the user names;
- template path: the nearest `wiki-template` directory, or the template path the user names.

## Setup Questions

Use these as the normal setup interview, but keep it light.

1. What is the subject/domain of the wiki?
2. What should the wiki be called on screen?
3. What base directory should it use?
4. What one-sentence mission/description should appear in the README and overview?
5. Should it start with an empty inbox, or are there initial source files to place in `inbox/`?
6. Should Codex create recurring automations now, or leave schedules for later?

For automations, the recommended default is:

- inbox sweep hourly between 7am and 11pm local time;
- nightly deterministic maintenance;
- weekly deep clean.

Scheduled inbox automations should not edit substantive content pages. They should register sources, create reference pages, rebuild routing assets, validate, and write proposed synthesis/review notes.

Create an automation only when its command names a matching committed grant. `--enable-scheduled-propose` creates a maintenance grant suitable for nightly/weekly deterministic work; it does not create ingest authority. If no reviewed ingest grant exists, leave the inbox automation uncreated and report that prerequisite.

## Procedure

1. Read the template's `TEMPLATE.md`, `README.md`, `AGENTS.md`, and `wiki/overview.md`.
2. Confirm the destination directory does not exist. Do not overwrite an existing wiki.
3. Install the template's declared runtime dependencies, then run the bundled setup script from this public starter kit, or from wherever this skill's `scripts/new_wiki.py` lives:

   ```bash
   python3 -m pip install -e wiki-template
   python3 skills/rb-new-wiki/scripts/new_wiki.py \
     --template wiki-template \
     --parent .. \
     --name example-wiki \
     --title "Example Wiki" \
     --subject "example subject" \
     --tag example \
     --description "Example Wiki is a local-first LLM-wiki for example subject."
   ```

   The script builds and validates in a temporary sibling, initializes a standalone `main` Git repository with a clean initial commit, and publishes the requested directory atomically only after success. It creates no active authority by default. Only when the user explicitly opts into bounded scheduled maintenance, add `--enable-scheduled-propose --authority-owner "OWNER"`; this generates a time-bounded maintenance grant, never autonomous-apply authority.

4. Inspect the generated `README.md`, `AGENTS.md`, `wiki/overview.md`, `wiki/log.md`, `wiki/index.md`, and the newest report under `reports/lint/`.
5. If the user supplied initial source files, place copies in the new wiki's `inbox/` and use `rb-wiki-ingest` to process them. Preserve original raw evidence.
6. If the user asks for automations, confirm the matching committed grant first, then search for the Codex automation tool and create conservative cron automations whose command includes `--authority AUTHORITY_ID`. Do not hand-write automation TOML or create a schedule that will predictably fail for lack of authority.
7. Run or confirm:

   ```bash
   PYTHONDONTWRITEBYTECODE=1 python3 tools/source_registry.py validate
   PYTHONDONTWRITEBYTECODE=1 python3 tools/lint.py --quick
   ```

8. Summarize the new wiki location, chosen configuration, validation status, any automations created, and next review points.

## Safety Rules

- Do not mutate `wiki-template` while creating a new wiki.
- Do not overwrite or merge into an existing destination directory.
- Do not edit files in `sources/raw/` after copying the template.
- Do not create scheduled automations that rewrite substantive content without explicit approval.
- Confirm the fresh wiki's capability snapshot reconciles with its manifest and its graph cache carries the current source-manifest digest.
- Confirm external-agent provenance and check-evidence contracts are present; never seed them with tokens, credentials, prompts, or fabricated attribution.
- Do not delete human-provided initial sources. If they are copied into `inbox/`, normal ingest rules decide when the inbox copy can move to `processed/`.

## Outputs

- A new sibling wiki base directory created from `wiki-template`.
- A standalone clean Git worktree whose root is the wiki base, as required by managed v0.2 mutation.
- Subject-specific top-level docs and overview.
- Rebuilt `wiki/index.md` and `.wiki_cache/graph.json`.
- A fresh quick-lint report.
- Optional conservative automations for inbox, nightly maintenance, and weekly deep clean.
- A concise final summary with commands/checks run.

## Failure Modes

- If the template is missing, stop and ask for the template path.
- If the destination exists, stop and ask whether the user wants a different name.
- If validation fails, the requested destination remains absent. Report the clearly named `.rb-wiki-failed-*` diagnostic staging directory and its inspect/remove/retry instructions; do not create automations until the failure is understood.
- If Git initialization or the clean initial commit fails, treat setup as failed and preserve the diagnostic staging directory; managed mutation cannot operate from an uncommitted or nested wiki base.
