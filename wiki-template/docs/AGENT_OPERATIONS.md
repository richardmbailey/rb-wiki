# Agent Operations

RB Wiki v0.2 supports artifact-driven acquire, ingest, synthesize, deterministic-maintain, and semantic-maintain workflows. Scheduled proposal work cannot make substantive wiki edits. Substantive autonomous apply requires an exact committed proposal, explicit tier authority, and—at the highest tier—a separate digest-bound approval. No mode authorises push or evidence deletion.

## Choose An Operating Model

There are two user-facing ways to run the same wiki:

| Operating model | Human responsibility | Agent responsibility | Controller mode |
|---|---|---|---|
| **Human-driven** | Choose each task, stay present, inspect the diff and evidence, and decide what to commit and push. | Advise without writing, or make one bounded change under direct supervision. | Direct human editing, or `manual-assist` when an agent mutates files. Managed ingest still requires a grant. |
| **Agent-driven** | Define and commit narrow grants, choose approval boundaries, review material/high-consequence proposals, and monitor recovery. | Run pre-authorised acquisition, ingest, maintenance, proposal, or exact-apply work without continual prompting. | `scheduled-propose`, followed where appropriate by `authorised-autonomous-apply`. |

The controller mode name `manual-assist` means “an agent is editing while a human directs and reviews it.” It does not mean that a person needs permission to edit a Markdown file directly. Conversely, a command does not become human-driven merely because a person typed it in a terminal: `wiki_cron.py` and mutating `wiki_run.py` commands remain managed, grant-controlled operations.

Start with the human-driven model. Move one narrow workflow to agent-driven operation only after its supervised runs, paths, checks, reports, and recovery behavior are understood.

## Trust boundary

The repository's committed `wiki-manifest.yml`, `schema/agent_policy.yml`, a selected contract under `schema/lanes/`, and a named, time-bounded grant under `schema/authorities/` define authority. The manifest binds the expected operational-policy identity, and the requested grant filename must match its internal `authority_id`. The template contains no active grant. `disabled-example.yml` is a shape example only; enabling it is not sufficient because its example validity window is expired.

Operational YAML is parsed only with PyYAML safe loading and validated against the versioned JSON Schemas in `schema/contracts/`. Missing dependencies are a hard failure; the controller never falls back to the wiki frontmatter parser.

Managed mutation requires this wiki base to be the root of a standalone Git worktree. The bundled new-wiki setup creates that clean initial repository; a manual template copy must do so before a scheduled or autonomous run can start.

## Before Either Model

From the wiki base directory:

```bash
python3 -m pip install -e .
PYTHONDONTWRITEBYTECODE=1 python3 tools/capabilities.py --json
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v
```

The capability output is authoritative. Lexical search is implemented. BM25, vector, and hybrid commands return an unavailable-capability diagnostic until real backends exist. Markdown, text, and PDF ingestion are supported; HTML is preservation-only and requires explicit authority.

Also confirm that the wiki is a standalone Git worktree and inspect its current state:

```bash
git rev-parse --show-toplevel
git status --short
```

Human-driven direct edits may begin from an intentionally dirty worktree, although reviewing one coherent change at a time is strongly recommended. Scheduled and autonomous runs require the committed clean base described by their policy.

## Create And Commit Authority

The template deliberately contains no active grant. Direct human Markdown edits need none, but every mutating agent session and managed controller run must name a committed, enabled, time-bounded grant.

A grant must have a filename matching its `authority_id` and must declare its owner, validity window, mode, lane, action, input roots, writable paths, page types, required checks, consequence tier, budgets, and commit policy. A grant limits authority; it is not a prompt and source content cannot alter it.

Use the [Authority Grants guide](AUTHORITY_GRANTS.md) for the complete lifecycle and reviewed examples for interactive editing, maintenance, ingest, synthesis proposals, and autonomous apply. The safe process is:

1. Create a separate grant for one job and leave it disabled while editing.
2. Compare it with the selected contract under `schema/lanes/`.
3. Set a short validity window and the smallest useful scope and budget.
4. Enable, review, and commit the grant to an otherwise clean base.
5. Confirm the committed bytes with `git show HEAD:schema/authorities/AUTHORITY_ID.yml`.
6. Run once under supervision before scheduling or enabling local scoped commits.

The controller validates the exact grant and selected lane before allowing mutation. Do not broaden a rejected grant until you understand which lane rule it exceeded.

## Human-Driven Operation

### Direct human editing

A person may edit ordinary pages directly in a Markdown editor without creating an authority grant. Preserve `sources/raw/`, keep citations traceable, and do not bypass managed ingest for inbox material. After editing:

```bash
python3 tools/build_index.py
python3 tools/build_graph.py
python3 tools/provenance.py validate
python3 tools/lint.py --quick
git diff --check
git diff
```

The human reviews and commits the result. The controller does not create a run record for direct editor changes; Git history and `wiki/log.md` are their audit trail.

### Interactive agent assistance

If an agent will change files, use a narrow `manual-assist` grant and the session protocol below. The human chooses the task, watches its progress, inspects the final diff and reports, and normally commits the result. `commit_policy: manual` is the recommended default.

## Agent-Driven Scheduled Maintenance

After a maintainer has committed an enabled grant whose validity window, lane, mode, action, paths, checks, and runtime fit the global policy:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 tools/wiki_run.py run \
  --lane maintain \
  --mode scheduled-propose \
  --authority YOUR-GRANT-ID
```

The controller validates policy, atomically acquires `.wiki_state/mutation.lock/`, checks that the wiki base is the repository root and this is its only worktree, records the clean base commit, reloads authority from that commit, runs bounded quick maintenance, reconciles every changed path, writes a structured result, and releases the lock.

## Manual-Assist And External-Agent Sessions

A cooperating external agent uses this persistent protocol. The example is a human-supervised semantic edit:

```bash
python3 tools/wiki_run.py start --lane semantic --mode manual-assist --authority GRANT
python3 tools/wiki_run.py heartbeat --run-id RUN_ID --token RUN_TOKEN
python3 tools/wiki_run.py status --run-id RUN_ID
python3 tools/wiki_run.py finish --run-id RUN_ID --token RUN_TOKEN --check quick-lint=pass
python3 tools/wiki_run.py cancel --run-id RUN_ID --token RUN_TOKEN --reason "operator request"
python3 tools/wiki_run.py fail --run-id RUN_ID --token RUN_TOKEN --reason "agent failure"
```

`start` is the only command that prints the random run token. The token is stored only below `.wiki_state/`, is required for mutation/control commands, and is excluded from status, durable reports, and commit records. Heartbeat is expected every 60 seconds; a five-minute lease expiry is diagnostic and never grants a second writer.

An agent may voluntarily add bounded provenance with `--agent-label`, `--runtime`, `--provider-model`, `--prompt-policy-digest`, and a local `--trace-reference`. Missing values remain null rather than being guessed. The controller accepts only short metadata, aggregate tool-call counts, local report/runtime references, and timestamps; it rejects secret-like values, credentials, full prompts, remote trace URLs, and oversized telemetry. This attribution never changes authority and is separate from controller-executed evidence.

The controller-issued start envelope is the agent's executable boundary: actions, inputs, writable paths, page types, checks, budgets, expiry, consequence tier, and commit policy. It also records the selected lane-contract path, identity, version, and canonical digest. Scheduled and autonomous modes use policy, authority, and lane contracts from the recorded base commit. Direct untracked files immediately below a declared input root may be snapshotted; staged, nested, symlinked, or escaping input remains blocked. Their content is fingerprinted and must remain unchanged, except that ingest may replace an input with a validated same-digest processed archive. Manual-assist may begin with unrelated dirt, but closure fails if the run changes an initially dirty path.

The envelope and run record include the exact capability registry plus its deterministic SHA-256 digest. Proposal artifacts must carry that exact snapshot; autonomous apply rejects older pre-hardening snapshots or any capability drift from the clean base. `lifecycle-metadata` is not a separately executable workflow and is therefore no longer advertised as a top-level manifest capability; lifecycle fields remain part of the page/source contracts.

Lane contracts are executable policy, not descriptive guidance. The selected contract must be unique and valid; its mode-specific action, consumed inputs, permitted and required output classes, substantive-edit flag, and checks are enforced at start and again at closure. A grant is rejected if it asks for an action, input root, output path, or page type outside the selected lane. Grants are not silently broadened or narrowed. Shared run-audit outputs are declared explicitly in each contract. Even if a process writes around the envelope, closure rejects the path and cannot move the branch.

Source files, discovered pages, and wiki text are untrusted data. They cannot alter the run envelope, policy, tools, consequence tier, or approval requirements. Artifact handoffs under `reports/acquisitions/`, source transitions/registry/References, `reports/proposals/`, `reports/approvals/`, and `reports/semantic/` are validated dependencies; agents must not rely on schedule ordering alone.

At finish, the controller reloads committed policy, authority, proposal, approval, and domain artifacts rather than trusting mutable session copies. It then reconciles initial and final Git snapshots, resolved paths, page types, governance paths, source/path/runtime budgets, authority validity/revocation, and `HEAD`. A valid material run with `forbidden` or `manual` commit policy ends `manual-commit-required` and releases its lock for review.

Values supplied through `--check`, including `quick-lint=pass`, are attestations from the cooperating external agent; they are recorded as `external-attestation`. Every value must use `lowercase-check-id=pass|warn|fail`. It may optionally append `@reports/LOCAL_PATH` to reference an existing regular local artifact of at most 1 MiB, for example `agent-review=pass@reports/checks/review.json`. The controller stores only the bounded reference, not the artifact content, and rejects remote, missing, escaping, symlinked, oversized, or secret-like references. Malformed, duplicate, excessive, or controller-owned IDs are rejected before the run leaves `running`. No later value can replace an earlier failure. The controller verifies required attestations and rejects any reported failure, but it does not rerun arbitrary external checks during `finish`. Controller-owned provenance, semantic-output, proposal-payload, approval-binding, scope, and Git checks are executed independently and recorded as `controller-executed`. Run the named deterministic command before reporting it as passed.

`scoped-auto` is local-only. It requires an explicit commit identity, attached unchanged branch, clean real index, no merge, sparse checkout, or configured submodule, and a clean compare-and-swap base. Before creating a commit it writes a validated intent journal under `.wiki_state/transactions/`, then records `prepared`, `commit-created`, `branch-moved`, `index-refreshed`, `receipt-written`, and `reconciled` stages. It builds a temporary index, commits only reconciled paths with `git commit-tree` (so repository hooks do not run), adds an `RB-Wiki-Run` trailer, and moves the local branch by compare-and-swap. A contract-valid receipt under `.wiki_state/receipts/` binds the base, branch, commit, tree, paths, and content manifest. It never pushes.

If the branch moves but index, receipt, session, or lock bookkeeping cannot finish, the run becomes `committed-recovery-required` and returns exit `5`. This is not an ordinary failure: do not rerun the work, create another commit, move the branch, terminate the session, or break its retained lock. Use the exact command recorded in `next_action`:

```bash
# External-agent session
python3 tools/wiki_run.py recover --run-id RUN_ID --token RUN_TOKEN

# Controller-owned maintenance run
python3 tools/wiki_run.py recover --run-id RUN_ID --authority ORIGINAL_GRANT
```

Recovery is idempotent. It accepts only the recorded branch head with one unambiguous `RB-Wiki-Run` trailer, the recorded parent/tree/path set/content manifest, and matching receipt evidence. It refreshes the real index, publishes any missing receipt, reconciles the journal/session, and only then releases the original lock. `wiki_doctor.py` reports the exact incomplete stage without modifying it.

An authorised human may acknowledge later manual commit/recovery without changing the original outcome:

```bash
python3 tools/wiki_run.py resolve --run-id RUN_ID --authority GRANT \
  --actor REVIEWER --reason "reviewed and committed" --commit COMMIT_HASH
```

## Semantic proposal and apply

Six lane contracts live under `schema/lanes/`: acquisition, ingestion, synthesis, deterministic maintenance, semantic maintenance, and governance maintenance. A scheduled synthesis run writes exactly one contract-valid proposal and a matching attributed semantic output; it may not change an ordinary page:

```bash
python3 tools/wiki_run.py start --lane synthesize --mode scheduled-propose --authority PROPOSAL_GRANT
python3 tools/wiki_run.py heartbeat --run-id RUN_ID --token RUN_TOKEN
python3 tools/wiki_run.py finish --run-id RUN_ID --token RUN_TOKEN --check quick-lint=pass
```

Proposals record intended use, action class, source IDs, findings, deterministic evidence, uncertainty, contradictions, checks, affected pages, tier, and policy/capability snapshot. Exact target content is hashed; high-consequence proposals require it and end `approval-required` without applying it.

After the proposal is reviewed and committed, a human may commit a separate approval under `reports/approvals/`. The approval identifies its role, scope, conditions, policy version, validity window, and the proposal payload digest. Apply starts only from a clean base containing both artifacts:

```bash
python3 tools/wiki_run.py start --lane synthesize --mode authorised-autonomous-apply \
  --authority APPLY_GRANT --proposal-id PROPOSAL_ID --approval-id APPROVAL_ID
python3 tools/wiki_run.py finish --run-id RUN_ID --token RUN_TOKEN --check quick-lint=pass
```

Routine apply needs routine-tier authority. Material apply needs material-tier authority and expanded semantic output. High-consequence apply always needs the separate approval. The controller compares final ordinary-page bytes and paths to the committed target-content payload, validates citations and provenance, prevents the apply run from changing its proposal/approval, and rejects expired, wrong-role, wrong-scope, or stale-digest approvals. Consequence follows intended use and action class, not a domain or source label. An enabled domain adapter may tighten rules but cannot weaken core invariants.

## Recoverable inbox ingestion

Ingestion is a controller-owned lane, not a standalone mutation command:

```bash
python3 tools/wiki_cron.py inbox --authority INGEST_GRANT
```

When ingest follows an acquisition lane, commit the validated acquisition result first and bind the run to it:

```bash
python3 tools/wiki_cron.py inbox --authority INGEST_GRANT --acquisition-id ACQUISITION_ID
```

Selected locators must use `inbox:FILENAME`, and the direct inbox contents must match the committed selection exactly. A mismatch terminates the ingest session without preserving unselected material.

The grant must include `ingest-sources`, direct `inbox` input, source/Reference/routing/report paths, `Reference` page type, budgets, required checks, and commit policy. Unsupported formats fail before preservation unless the same grant explicitly adds `preserve-unsupported`, in which case they are recorded as `preservation-only` rather than pretending extraction or integration exists.

Each input is keyed by SHA-256 under `.wiki_state/sources/` and moves through `captured`, `raw-preserved`, `registered`, `reference-created`, `validated`, and `inbox-archived`. Raw preservation uses a same-filesystem verified temporary copy and non-overwriting atomic link. Later extraction or Reference failures never roll raw evidence back. A failed/no-text PDF is still archived after provenance validation, with `access_level: raw-only` and an exact OCR/manual-review next action.

The engine can resume a digest inside an active controller session:

```bash
RB_WIKI_RUN_CONTROLLER=1 python3 tools/ingest.py --resume-digest SHA256 --run-id RUN_ID
```

Direct, nested, symlinked, escaping, unsafe-name, oversized, or excessive inputs fail closed. Pre-existing `sources/raw/` files are fingerprinted at session start and must remain byte-for-byte append-only. Inbox archival is a final idempotent transition and occurs only after registry/raw/Reference provenance validates.

Global provenance validation is bidirectional. In addition to checking every registry entry forward to its raw file and Reference, it enumerates `sources/raw/` and all wiki Reference pages without following links. Every regular artifact must map uniquely back to one registry source ID and path. An extra artifact named by a valid incomplete source-transition journal is reported as `recovery-required`; an unexplained extra is a failure requiring registration or quarantine review, never automatic deletion. `--source-id` deliberately performs only the named forward check and says that reverse global checks were skipped.

The cron wrapper owns exactly one session from successful start through finish/failure. It restores the process controller flag on every exit, terminalises at most once, and never overwrites a committed-recovery outcome. Exceptions after raw preservation keep the raw file and digest transition journal so the work can be inspected or resumed.

Output parent chains are also checked for symlinks, so a redirected raw, processed, report, cache, or runtime directory cannot make a cooperating tool write outside the wiki root.

## Runtime and durable records

`.wiki_state/` is ignored recoverable runtime state, not a disposable cache. Every attempt gets an incremental journal under `.wiki_state/runs/` and updates `.wiki_state/latest.json`. Cache cleanup must never remove `.wiki_state/`.

No-op, all-pass, and pre-mutation blocked attempts remain `ephemeral-telemetry` in runtime state to avoid tracked-report churn. Material records are classified as durable mutation, failure/recovery, approval, or governance and promoted to `reports/runs/<run-id>.json`. `reports/latest.json` changes only for durable/material state and includes blockers, overdue actions, and the capability snapshot.

Lint emits canonical, contract-validated JSON and a deterministic Markdown view. Every check records outcome, severity, disposition, affected paths/source IDs, evidence, and a recommended action. Unimplemented semantic checks are `not_run` and `agent-required`, never `pass`. Reference integration uses the policy grace period and explicit priority/consequence escalation.

The graph cache is versioned and bound to a digest of every Markdown routing input plus graph-interpretation policy. Mutating maintenance reuses an identical current cache or atomically rebuilds a stale one. Read-only query commands never trust malformed, symlinked, old-version, or stale cache bytes; they build a current graph in memory and leave the suspect cache untouched.

Retention is explicit and dry-run-first:

```bash
python3 tools/wiki_run.py prune --days 30
python3 tools/wiki_run.py prune --days 30 --apply
```

Only old terminal ephemeral journals can be removed. Active/incomplete state and durable records are never pruned.

Terminal states include `completed`, `blocked`, `failed`, `cancelled`, `manual-commit-required`, and `approval-required`. `committed-recovery-required` is deliberately non-terminal: the commit exists and only validated reconciliation or an audited resolution may advance it.

Stable command exit meanings are: `0` success or no-op; `1` failure; `2` blocked/contention; `3` manual commit required; `4` approval required; and `5` committed recovery required.

Contention is a transient blocked outcome, not an ordinary validation failure. `wiki_run.py start` returns exit code `2`, writes one coherent `blocked` journal/latest snapshot with a finish time, and does not overwrite it as `failed`. A terminal session cannot be finished, cancelled, or failed a second time.

`tools/wiki_doctor.py --root OTHER_WIKI` is read-only and uses this installed canonical doctor's validation code. It inspects target data and declared capability files but never imports or executes Python from the target wiki.

Migration is also no-follow and patch-only. Both the supplied wiki root and template root must be real directories. Every manifest, policy, contract, lane, prompt, tool, report placeholder, registry, and legacy Reference is checked against its declared root immediately before bounded reading; a missing planned output is distinct from a symlinked parent. Unsafe-path diagnostics contain only the path and reason, never content reached through a link.

## Failure recovery

- A dirty base is blocked before maintenance. Review and commit, stash, or remove the unrelated changes; never absorb them into the scheduled run.
- A second Git worktree is blocked because the v0.2 lock is per wiki worktree, not cross-worktree.
- An existing lock directory always blocks. If `owner.json` is missing or unreadable, treat the lock as incomplete and held. Inspect the process and journal before manually moving the lock directory aside; do not delete it speculatively.
- Handled failures release a normally owned lock. If release cannot prove ownership, the journal records incomplete cleanup and the lock remains for diagnosis.
- A `committed-recovery-required` lock is intentionally retained. Run `wiki_doctor.py`, verify the recorded commit, then use `wiki_run.py recover`; do not use `break-lock` as a shortcut.
- Changed paths outside the grant's `writable_paths` prevent successful closure.

`break-lock` is never automatic and age alone is insufficient. It requires committed governance-maintenance authority, actor and reason, readable observed owner metadata, same-host process-liveness failure, and (for a known session) an expired lease. The displaced lock is preserved under `.wiki_state/broken-locks/` and a durable audit report is written:

```bash
python3 tools/wiki_run.py break-lock --authority GOVERNANCE_GRANT \
  --actor OPERATOR --reason "confirmed owner process exited"
```
