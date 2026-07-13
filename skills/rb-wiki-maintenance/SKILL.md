---
name: "rb-wiki-maintenance"
description: "Use when the user asks Codex to run LLM-wiki maintenance, quick or full lint, nightly upkeep, weekly deep clean, graph/index rebuilding, source registry checks, or wiki health review."
---

# RB Wiki Maintenance

Use this skill when the user asks to maintain an existing LLM-wiki, run quick or full lint, do a nightly tidy-up, run a weekly clean, review reports, rebuild the graph/index, or check wiki health.

This is a narrow operational skill for upkeep. Use `rb-wiki` for broader design/setup and use `rb-wiki-ingest` when the main task is processing new inbox files.

## Required Context

- A wiki base directory, usually the current working directory or a child directory containing `AGENTS.md`, `wiki/`, `sources/`, `tools/`, and `reports/`.
- A requested maintenance level:
  - quick or unspecified: quick lint and routing asset checks;
  - nightly: deterministic maintenance and quick lint;
  - weekly/full/deep clean: full lint and prioritized review.

If multiple wiki base directories are present, choose the one the user named. If none is named and only one exists, use that. If several plausible wikis exist, ask which one to maintain.

## Procedure

1. Enter the wiki base directory.
2. Read `AGENTS.md`, `README.md`, `wiki/index.md`, recent `wiki/log.md`, and the latest reports in `reports/ingest/`, `reports/lint/`, and `reports/review/` where present.
3. Run the appropriate command:

   If the operation can mutate a report, generated routing asset, or page, follow `docs/AGENT_OPERATIONS.md`: use `wiki_run.py run` for the bounded scheduled maintenance lane or `start`/`heartbeat`/`finish` for an external agent session. Do not enable or manufacture a grant as part of ordinary maintenance. Direct commands below are diagnostic/manual commands only when no managed mutation is being claimed.

   Quick or unspecified:

   ```bash
   PYTHONDONTWRITEBYTECODE=1 python3 tools/lint.py --quick
   ```

   Nightly upkeep:

   ```bash
   PYTHONDONTWRITEBYTECODE=1 python3 tools/wiki_cron.py nightly --authority AUTHORITY_ID
   ```

   Weekly/full/deep clean:

   ```bash
   PYTHONDONTWRITEBYTECODE=1 python3 tools/wiki_cron.py weekly --authority AUTHORITY_ID
   ```

   Both wrappers require committed scheduled-maintenance authority. Weekly additionally persists a typed lint report, so its grant must allow `reports/lint/**`.

4. Review the canonical JSON report. First order results by `outcome` (`fail`, then `warn`), then severity (`critical` to `info`), then disposition (`human-required`, `agent-required`, `fix`, `monitor`, `none`). Treat `not_run` as unavailable assessment work, never a pass. Within that ordering, prioritize raw/provenance integrity, structural validity, overdue Reference integration, source coverage, ordinary-page orphans, and editorial assessment queues.
5. Make only mechanical, unambiguous repairs. For substantive content, contradiction handling, merges, deletes, renames, or schema changes, write review notes and ask the user.
6. Re-run quick lint after any repair.
7. Summarize health status, generated reports, warnings, repairs made, and review items.

## Safety Rules

- Do not delete files, merge pages, rename pages, resolve serious contradictions, rewrite important synthesis, or change schemas without explicit approval.
- Do not treat scheduled reports as authority to make irreversible changes.
- Do not infer autonomy from a report. The v0.2 controller supports only the modes/actions in a committed grant; scoped automatic commits are local-only and never push.
- Exit `5` means the local commit succeeded and authenticated reconciliation is required; do not rerun maintenance or break the retained lock.
- Do not scan all page bodies before routing through index, frontmatter, graph, search, and reports.
- Trust cached graph routing only when its version and complete source digest validate.
- Raw source files in `sources/raw/` are immutable.
- Agent metadata and external check evidence are attribution only. Keep them bounded and secret-free; do not claim a controller-executed result from an external attestation.

## Outputs

- A lint or review report under `reports/`.
- Rebuilt `wiki/index.md` and `.wiki_cache/graph.json` when needed.
- A concise final summary with overall status and prioritized next actions.
