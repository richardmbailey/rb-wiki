# Wiki Template

This directory is a ready-to-copy starter for a subject-specific wiki that stays on your computer.

The wiki stores ordinary Markdown text files. You can read and edit them in Obsidian, VS Code, or any other text editor. An AI assistant such as Codex or Claude can help organise sources and write linked notes, but you remain in control of what it is allowed to change.

The system keeps unchanged copies of original sources, records where information came from, checks for common problems, and keeps a Git history of changes. Git is the wiki’s change history: a **commit** is a saved checkpoint, and a **push** uploads saved checkpoints to a service such as GitHub.

If this folder has just been used to create a new wiki, read `SETUP.md` first.

## Start Here

For a new wiki, use the human-driven model:

1. Keep the wiki’s starting Git checkpoint unchanged until setup is complete.
2. Put a small number of Markdown, text, or PDF files in `inbox/`.
3. Create a short-lived permission for inbox processing by following the [Authority Grants guide](docs/AUTHORITY_GRANTS.md).
4. Ask Codex to process the inbox while you supervise it.
5. Read the new source pages and check that their links point to the right original documents.
6. Run the quick check shown in [Everyday Commands](#everyday-commands).
7. Save a Git commit only when you are satisfied with the result.

The wiki deliberately starts with **no active grant**. This means an AI assistant or scheduled task cannot change it until a person creates and saves a suitable permission file.

## A Few Terms Used Here

- **Source:** an original document that provides information for the wiki.
- **Inbox:** the folder where new files wait to be processed.
- **Ingest:** preserve an original source, record it in the source list, and create a source page that other pages can cite.
- **Agent:** an AI assistant that can take actions, such as reading or changing files.
- **Authority grant:** a small permission file that says what an agent or automated task may do, where it may make changes, and when the permission ends.
- **Check:** an automatic inspection for problems. Technical files may call this “validation” or “lint”.
- **Proposal:** a suggested change that has been written out for review but has not yet been applied to normal wiki pages.

## Choose An Operating Model

This wiki supports two ways of working. If you are not sure which to choose, use human-driven operation.

| Operating model | In plain language | Who saves and uploads changes? |
|---|---|---|
| **Human-driven** | A person starts each task. The person may edit pages directly or ask an AI assistant to perform one clearly limited task. | The person normally reviews, commits, and pushes the changes. |
| **Agent-driven** | A scheduled process or AI assistant starts tasks that a person approved in advance. Its permission is limited by a saved permission file. | The system may make an allowed local commit, but a person decides whether to push it. |

The system uses these exact labels in commands and permission files:

| System label | What it means |
|---|---|
| `manual-assist` | An AI assistant changes files while a person supervises one task. |
| `scheduled-propose` | An automated task performs routine checks or prepares a suggested change for review. |
| `authorised-autonomous-apply` | An automated task applies only the exact proposal that received separate approval. |

A person editing Markdown directly does not need a grant. Any agent that changes files does need a grant. Inbox processing and scheduled maintenance also need grants because they update several connected records.

### Human-Driven: First Use

1. Start from a clean Git state, meaning there are no unreviewed changes left over from an earlier task.
2. Edit Markdown yourself, or ask an agent to do one clearly described job.
3. Before an agent changes ordinary wiki pages, create and commit a `manual-assist` grant limited to the necessary files.
4. Before processing the inbox, create and commit a separate ingest grant.
5. Read the changed pages, source links, and task report.
6. Run the source and quick checks.
7. Commit and push the result yourself only after you approve it.

The [Authority Grants guide](docs/AUTHORITY_GRANTS.md) contains permission-file examples and explains how to enable, expire, and revoke them.

### Agent-Driven: First Use

Move to agent-driven operation only after the human-driven process works reliably.

1. Choose one small task to automate.
2. Create a grant that names the task, allowed files, limits, and end time.
3. Review and commit the grant while no other changes are waiting.
4. Run the task once while supervising it and read the result report.
5. Schedule it only after the supervised run succeeds.
6. Make content-writing tasks prepare proposals instead of directly changing normal pages.
7. Review and commit a proposal before allowing a separate task to apply it.

High-consequence work means work where a mistake could cause serious harm. Applying this kind of proposal requires a separate approval that refers to that exact proposal.

An agent may create a local Git commit only when its grant explicitly permits it. Agents **never push** changes to GitHub or another remote service. For the complete operating and recovery procedures, read [Agent Operations](docs/AGENT_OPERATIONS.md).

## Adding Sources

Put Markdown, plain-text, or PDF files in `inbox/`. Then ask Codex:

```text
Use $rb-wiki-ingest to process this wiki's inbox while I supervise.
```

Inbox processing needs a committed, enabled, time-limited ingest grant. This is true even when a person starts the command, because processing updates the protected source copy, the source list, the source page, and the recovery record together.

You can run the same task from a terminal. Replace `YOUR-INGEST-GRANT` with the name of your ingest permission file:

```bash
python3 tools/wiki_cron.py inbox --authority YOUR-INGEST-GRANT
```

Do not run `tools/ingest.py` directly. The command above uses the built-in safety program, prevents two change-making jobs from running at the same time, and records how to continue after an interruption.

When processing succeeds, the wiki:

1. copies the original file unchanged into `sources/raw/`;
2. records the source and its identifying information;
3. creates or updates a source page that other pages can cite;
4. refreshes the wiki’s navigation information; and
5. moves the inbox copy aside only after all required checks pass.

PDF originals are kept unchanged. When possible, the wiki also creates a text copy for searching. Encrypted, unclear, unsupported, failed, or unusually large files stay in the inbox for a person to review.

## Everyday Commands

Run these commands from the main folder of this wiki.

Check the source records and links between source files and source pages:

```bash
python3 tools/provenance.py validate
```

Run the quick everyday health check:

```bash
python3 tools/lint.py --quick
```

Search the wiki for a phrase:

```bash
python3 tools/query.py search "your search words"
```

Ask the diagnostic tool why a controlled task cannot run:

```bash
python3 tools/wiki_doctor.py
```

A successful automatic check does not prove that every statement is true. A person should still review important content and source links.

When working in Codex, you can usually ask in plain language instead:

```text
Use $rb-wiki-ingest to process this wiki's inbox.
Use $rb-wiki-maintenance to run quick maintenance on this wiki.
Use $rb-wiki-maintenance to run the weekly deep clean.
```

## Scheduled Automation

These commands are for agent-driven operation. Each requires a separate committed grant for that job:

```bash
python3 tools/wiki_cron.py apply --authority YOUR-APPLY-GRANT
python3 tools/wiki_cron.py nightly --authority YOUR-MAINTENANCE-GRANT
python3 tools/wiki_cron.py weekly --authority YOUR-MAINTENANCE-GRANT
```

The apply command selects and applies at most one eligible committed proposal. It does not ask an AI assistant to choose the proposal, write the final page, construct controller records, or run Git commands. The nightly task rebuilds navigation data and performs quick routine checks. The weekly task performs a deeper review and writes a detailed report.

The complete staged workflow is: source acquisition or intake, then ingest, then synthesis/proposal, then deterministic authorised apply, then scheduled maintenance/review. Navigation index and graph rebuilding happen in the maintenance stage so a tightly constrained apply cannot acquire extra changed paths.

If a result says that recovery is required, do not simply run the task again. First run:

```bash
python3 tools/wiki_doctor.py
```

Then follow the exact recovery command recorded in the task report. Do not move to another Git branch or change the affected files until recovery is complete.

## Main Folders

```text
inbox/          New files waiting to be processed
sources/raw/    Unchanged copies of original source files
sources/        The source list and searchable text copies
wiki/           The readable Markdown wiki pages
schema/         The wiki's rules, permissions, and AI instructions
tools/          Programs that operate and check the wiki
reports/        Results that need review or provide an audit record
.wiki_cache/    Navigation data that can be rebuilt
.wiki_state/    Temporary recovery information used while a task runs
```

The hidden folders beginning with `.wiki_` are managed by the tools. Most users should not edit them.

## Current Template Content

This starter includes a source page made from the current [LLM-Wiki System Instructions](wiki/references/2026-07-13-llm-wiki-system-instructions.md). It also keeps the [earlier instructions](wiki/references/2026-07-09-llm-wiki-system-instructions.md) as historical evidence, clearly marked as superseded. Many starter pages are marked as needing review or having medium or low confidence until you add sources about your own subject.

New pages use the current `llm-wiki-profile/0.2` rules. Older pages that use the earlier `llm-wiki-profile/0.1` rules can still be read. Most users do not need to work with these version labels directly.

## Important Safety Limits

- Only one controlled task may change the wiki at a time.
- Original sources are kept and are not automatically deleted.
- Agents receive only the permission written in a grant that was saved before the task began.
- Important claims should link back to their sources.
- Interrupted tasks leave recovery information instead of silently guessing what happened.
- Higher-risk changes require stronger checks and, where appropriate, separate approval.
- Agents never push changes to a remote service.
- A person should review important factual judgments, contradictions, and high-consequence work.

## Advanced And Maintainer Information

Most users can stop here. The following documents explain the internal rules and administration details:

- [Agent Operations](docs/AGENT_OPERATIONS.md) explains every controlled task, result, and recovery step.
- [Authority Grants](docs/AUTHORITY_GRANTS.md) contains complete permission examples.

Developers who change the template itself can install its Python requirements and run its tests with:

```bash
python3 -m pip install -e .
python3 -m unittest discover -s tests -v
```
