# RB Wiki

RB Wiki helps you turn a collection of documents into an organised, searchable wiki on your local computer. It stores untouched versions of the original documents, creates linked notes, records where information came from, and checks the wiki for common issues. RB Wiki is intended to be a lasting knowledge collection, not just a one-time chat with a group of documents. You can use it in either of these ways:

- **Human-driven:** you decide when work happens, check every change, and decide when to save or share it.
- **Agent-driven:** an AI assistant or scheduled process performs carefully limited tasks that you approved in advance.

If you are not sure which model to choose, start with human-driven operation.

## What RB Wiki Does

Each wiki can:

- keep an unchanged copy of every original source;
- create readable notes with links back to their sources;
- connect related pages with normal Markdown links;
- show which source supports an important statement;
- check for missing information, broken links, and inconsistent records;
- keep a history of changes so mistakes can be reviewed and recovered; and
- allow carefully controlled automation without giving an AI assistant unrestricted access.

## A Few Terms Used In This Guide

- **Source:** an original document that provides information for the wiki.
- **Inbox:** the folder where you place new source files before the wiki processes them.
- **Ingest:** process a source file by preserving the original, recording it, and creating a source page that the rest of the wiki can cite.
- **Markdown:** a simple text-file format. Markdown files end in `.md` and can be opened in ordinary text editors as well as apps such as Obsidian.
- **Git:** Git is the change history for the wiki. A **commit** is a saved checkpoint. A **push** uploads saved checkpoints to a remote service such as GitHub.
- **Agent:** An AI assistant is software such as Codex or Claude. An agent is an AI assistant that can take actions, such as reading or changing files, rather than only answering questions.
- **Authority grant:** An authority grant is a small permission file. It says exactly what an agent or automated task may do, where it may make changes, and when its permission ends.
- **Check:** an automatic inspection for problems. Some technical documents call these checks “validation” or “lint”.
- **Proposal:** a suggested change that has been written out for review but has not yet been applied to the normal wiki pages.

## The Simplest Way To Start

The easiest approach is to clone/copy this repo to your local computer, then open this project folder in Codex and ask Codex to use the included setup instructions:

```text
Read skills/rb-new-wiki/SKILL.md and use it to create a new wiki from this template.
```

Codex will ask for the subject, title, folder name, short topic label, description, initial sources, and whether you want any automation. For a first wiki, choose human-driven operation and do not enable automation yet.

After setup:

1. Open the new wiki folder in Codex.
2. Read the `SETUP.md` file that was created for that wiki.
3. Follow the [Authority Grants guide](wiki-template/docs/AUTHORITY_GRANTS.md) to create and save a short-lived ingest permission. You can ask Codex to draft the permission text in the chat, then review and save it yourself.
4. Put a small number of test documents in the `inbox/` folder.
5. Ask Codex to process the inbox while you supervise it.
6. Check the new pages before saving the changes to Git.

## Creating A Wiki From The Terminal

You can also create a wiki yourself from the Terminal, and will need Python 3 and Git installed.

Run the following commands from this project folder. This example creates a new folder called `example-wiki` next to the `rb-wiki` folder (change names and details as needed):

```bash
python3 -m pip install -e wiki-template
python3 skills/rb-new-wiki/scripts/new_wiki.py \
  --template wiki-template \
  --parent .. \
  --name example-wiki \
  --title "Example Wiki" \
  --subject "example subject" \
  --tag example \
  --description "Example Wiki is a local wiki about the example subject."
cd ../example-wiki
python3 tools/source_registry.py validate
python3 tools/lint.py --quick
```

Replace the example name, title, subject, label, and description with your own choices. The final two commands check that the new wiki has been created correctly.

The setup tool creates a separate Git project and saves a clean starting checkpoint. This is important because the safety tools compare later changes with that known starting point.

Open the new wiki’s `wiki/` folder in Obsidian, VS Code, or any other Markdown editor. Its links are normal Markdown links, so you are not tied to a particular app.

You can copy `wiki-template/` manually instead, but the setup tool is safer and easier. A manual copy requires you to update the copied `README.md`, `AGENTS.md`, `wiki/overview.md`, `wiki/log.md`, and the generated navigation files yourself.

## Choose How To Operate The Wiki

Both operating models use the same wiki files and safety checks. The important difference is who starts the work and who approves the result.

| Operating model | In plain language | Who checks the result? |
|---|---|---|
| **Human-driven** | You start each task. You may edit pages yourself or ask an AI assistant to perform one clearly defined task. | You inspect the changes and decide whether to save and upload them. |
| **Agent-driven** | A scheduled process or AI assistant starts tasks that you approved in advance. Its permission is limited by a permission file. | You set the limits and approval rules. The system may save an allowed local checkpoint, but it does not upload it. |

The system uses three exact labels for AI-assisted work. You may see these names in commands and permission files:

| System label | What it means |
|---|---|
| `manual-assist` | An AI assistant is working on one task while a person supervises it. |
| `scheduled-propose` | An automated task may perform routine checks or prepare a suggested change for later review. |
| `authorised-autonomous-apply` | An automated task may apply only the exact proposal that was separately approved. |

A person typing directly into a Markdown page does not need an authority grant. An agent that changes the wiki does need one. Processing the inbox and running scheduled maintenance also need grants because those tasks change several connected records.

### Human-Driven Operation

This is the recommended model for a new wiki.

1. Create the wiki. A new wiki deliberately starts with **no active grant**, which means no agent has permission to change it automatically.
2. Add documents to `inbox/`, or edit ordinary Markdown pages yourself.
3. If an AI assistant will change files, create a short-lived `manual-assist` grant for that specific task. The [Authority Grants guide](wiki-template/docs/AUTHORITY_GRANTS.md) gives examples.
4. If you want to process the inbox, create a separate ingest grant. Inbox processing always uses its built-in safety program, even when you start it yourself.
5. Ask the assistant to perform one clearly described task.
6. Read the changed pages and check their source links. Use `git diff` if you are comfortable with Git; it shows exactly what changed.
7. Run the quick check shown in [Checking The Wiki](#checking-the-wiki).
8. Create a Git commit when you are satisfied. Push it only if you want to upload the change to a remote repository.

The agent does not decide when its permission begins or what it covers. You create the grant, review it, and save it in Git before the task starts. You can disable or remove the grant when the task is finished.

### Agent-Driven Operation

Use this model only after the human-driven process works reliably and you understand the reports it produces.

1. Choose one small task to automate, such as checking links, processing the inbox, or preparing a proposed page update.
2. Create an authority grant that names the task, the files it may change, its limits, and its end time.
3. Review the grant and save it as a Git commit. The automation cannot quietly give itself more permission later.
4. Schedule only the command named in that grant.
5. For changes to normal wiki content, have the agent prepare a proposal first. Review and save that proposal before allowing another task to apply it.
6. High-consequence work means work where a mistake could cause serious harm. Applying this kind of proposal requires a separate approval that refers to that exact proposal.
7. Read the result report after each run. If the report says recovery is required, follow its recovery instruction instead of simply starting the task again.

An agent may create a local Git commit only when its grant explicitly allows this. It may **never push** changes to GitHub or another remote repository. Start with human-created commits. The advanced setting named `scoped-auto` allows the system to save an approved change automatically in the local Git history. Use it only for a narrow task that has been tested repeatedly. Give it a dedicated name and email address so the Git history clearly shows that an automated task created the commit.

For the full procedures, read the [Agent Operations guide](wiki-template/docs/AGENT_OPERATIONS.md). For permission-file examples and instructions for enabling, expiring, or revoking permission, read the [Authority Grants guide](wiki-template/docs/AUTHORITY_GRANTS.md).

## Adding Sources

Place Markdown, plain-text, or PDF files in the wiki’s `inbox/` folder. In human-driven use, you can ask Codex:

```text
Use $rb-wiki-ingest to process this wiki's inbox while I supervise.
```

This request assumes that the included `rb-wiki-ingest` Codex skill has been installed. If Codex does not recognise the skill name, open the original `rb-wiki` project and ask Codex to help install the folders under `skills/` in your Codex skills directory.

Inbox processing requires an ingest authority grant. This remains true when a person starts the command because processing one source updates the protected source copy, the source list, the source page, and the wiki’s recovery record together.

If you prefer the terminal, run this command from inside the subject wiki and replace `YOUR-INGEST-GRANT` with the name of your ingest permission file:

```bash
python3 tools/wiki_cron.py inbox --authority YOUR-INGEST-GRANT
```

Do not run `tools/ingest.py` directly. The command above uses the built-in safety program, allows only one change-making job at a time, and records enough information to continue safely after an interruption.

When processing succeeds, the wiki:

1. copies the original file unchanged into `sources/raw/`;
2. records the source and its identifying information;
3. creates or updates a source page that other pages can cite;
4. rebuilds the navigation information; and
5. moves the inbox copy aside only after all required checks pass.

PDF originals are kept unchanged. When possible, the wiki also creates a text version for searching. Encrypted, unclear, unsupported, failed, or unusually large files remain in the inbox for a person to review.

## Checking The Wiki

Run this quick check after ordinary edits:

```bash
python3 tools/lint.py --quick
```

It checks the wiki’s structure, page information, links, and source records. A successful check does not prove that every statement is true, so a person should still review important content and citations.

The system also offers nightly and weekly maintenance commands for agent-driven use:

```bash
python3 tools/wiki_cron.py apply --authority YOUR-APPLY-GRANT
python3 tools/wiki_cron.py nightly --authority YOUR-MAINTENANCE-GRANT
python3 tools/wiki_cron.py weekly --authority YOUR-MAINTENANCE-GRANT
```

Use a separate, narrowly scoped permission file for apply and maintenance. The apply task deterministically selects and applies at most one eligible committed proposal; it does not ask an AI assistant to construct the page, task record, or Git commit. The nightly task rebuilds navigation data and performs quick routine checks. The weekly task performs a deeper review and writes a detailed report.

The staged agent-driven pipeline is: source acquisition or intake, then ingest, then synthesis/proposal, then deterministic authorised apply, then scheduled maintenance/review. Navigation index and graph rebuilding happen during maintenance so they cannot broaden a tightly scoped apply.

## What Is In This Project

- `wiki-template/` is the complete starter wiki that the setup tool copies.
- `skills/` contains instructions that help Codex create, operate, check, and maintain a wiki.
- `llm-wiki-system-instructions.md` is the detailed technical design for people who want to build or adapt the system.
- `docs/` contains upgrade, safety, compatibility, and design documents for advanced users and maintainers.

Inside a created wiki, the main folders are:

```text
inbox/          New files waiting to be processed
sources/raw/    Unchanged copies of original source files
sources/        The list of sources and searchable text copies
wiki/           The readable Markdown wiki pages
schema/         The wiki's rules, permissions, and AI instructions
tools/          Programs that operate and check the wiki
reports/        Results that need review or provide an audit record
.wiki_cache/    Navigation data that can be rebuilt
.wiki_state/    Temporary recovery information used while a task runs
```

The hidden folders beginning with `.wiki_` are managed by the tools. Most users should not edit them.

## Important Safety Limits

RB Wiki reduces the chance of accidental or unauthorised changes, but it does not make AI-generated information automatically correct.

- Only one controlled task may change a wiki at a time.
- Original sources are kept and are not automatically deleted.
- Every automated change needs permission that was saved before the task began.
- Important claims should link back to their sources.
- Interrupted tasks leave recovery information instead of silently guessing what happened.
- Higher-risk changes require stronger checks and, where appropriate, a separate approval.
- Agents may never push changes to a remote repository.
- A person should review important factual judgments, contradictions, and high-consequence work.

For the precise boundaries and remaining risks, read [Trust Model and Limitations](docs/TRUST_MODEL_AND_LIMITATIONS.md). Advanced maintainers may also need the [v0.2 Upgrade Guide](docs/UPGRADE_V02.md), [Capability Matrix](docs/CAPABILITY_MATRIX.md), and [Canonical Ownership Rules](docs/CANONICAL_OWNERSHIP.md).

The file arrangement follows Google’s Open Knowledge Format, or OKF, so compatible tools can understand the wiki’s structure. You do not need to know OKF to use the wiki. See [Google’s introduction to the format](https://cloud.google.com/blog/products/data-analytics/how-the-open-knowledge-format-can-improve-data-sharing) if you need the technical background.

## Privacy And Public Sharing

This project is safe to share as a toolkit, but a subject wiki may contain private source documents, reports, credentials, or unpublished work. Keep sensitive wikis in separate private repositories.

Before making a wiki public, check the source folders, reports, configuration files, and Git history for private information. Removing a file from the current folder does not remove it from older Git commits.

## License

This project is released under the MIT License. See `LICENSE`.
