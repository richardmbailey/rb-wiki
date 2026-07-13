# RB Wiki v0.2: Human + Agent Operations

Status: implemented and verified  
Created: 2026-07-13  
Reviewed: 2026-07-13  
Source proposal: [`updates-needed.txt`](../../../updates-needed.txt)

## Summary

RB Wiki v0.2 will turn the repository's prose-level guidance for manual and scheduled agents into an enforceable, inspectable operating model. The release will add operating modes, authority and consequence policies, lane and run contracts, a single-writer run controller, recoverable ingestion, Git-aware closure, end-to-end provenance validation, structured reports, honest capability reporting, lifecycle-aware linting, and migration tooling.

The first supported autonomy boundary is deliberately narrow: one host, one writable wiki worktree, and at most one mutating run per wiki. Parallel read-only work remains allowed. Agent runtimes remain external to RB Wiki; this project supplies the repository protocol and deterministic safety tooling that cooperating agents must use.

The walking skeleton is a policy-authorised `scheduled-propose` maintenance run that travels through manifest loading, preliminary policy validation, atomic lock acquisition, authoritative Git preflight under the lock, lane execution, validation, structured reporting, closure, and lock release.

## Goals

- Make an agent run's mode, authority, scope, inputs, outputs, and closure state explicit and machine-checkable.
- Prevent overlapping mutating runs in a single wiki worktree.
- Make source ingestion idempotent, atomic where possible, and safely resumable after interruption.
- Prevent autonomous runs from absorbing or overwriting unrelated human or agent changes.
- Validate the complete provenance chain from immutable raw source to registry, Reference page, and cited ordinary page.
- Give agents truthful, structured information about available capabilities and checks that were or were not performed.
- Separate structural validity, source integration, evidence access, assessment, and review maturity.
- Support domain-specific policy without embedding any subject's source hierarchy, evidence rules, ontology, or review thresholds in the generic toolkit.
- Provide a generic high-consequence policy hook based on intended use and action, not merely domain labels.
- Give copied subject wikis a version manifest, health inspection, and reviewed migration path.
- Establish integration and failure-injection tests sufficient to support unattended operation claims.

## Non-goals

- Supporting concurrent mutating writers across multiple hosts or multiple writable worktrees in v0.2.
- Defending against a malicious process that deliberately bypasses RB Wiki tooling and directly edits repository files.
- Selecting, hosting, or routing between LLM providers or implementing a multi-agent framework.
- Implementing BM25, vector search, embeddings, or hybrid retrieval in this release; v0.2 must report their absence honestly.
- Encoding subject-specific evidence hierarchies, organisations, assessment rules, or recommendation boundaries in the core toolkit.
- Automatically resolving contradictions, approving high-consequence conclusions, deleting evidence, or merging pages.
- Automatically migrating every local override in existing subject wikis without a reviewed dry run.
- Treating repository authority records as cryptographic identity or authentication.
- Automatically pushing commits or coordinating remote branches; v0.2 automatic closure is local-only.

## Users

- Human maintainers operating a wiki manually.
- Scheduled agents that may acquire and preserve sources, create proposals, and run deterministic maintenance.
- Explicitly authorised agents that may apply bounded substantive changes.
- Reviewers who need evidence, provenance, run state, and approval requirements presented consistently.
- Maintainers of subject-specific wikis that need to inspect and adopt upstream toolkit changes.

## Requirements

### R1. Operating modes

The system must support and enforce:

- `manual-assist`: a human-supervised session; pre-existing changes may be tolerated only when snapshotted and protected from accidental inclusion.
- `scheduled-propose`: unattended work may preserve sources, generate references, run deterministic checks, and write proposals, but must not make substantive content edits.
- `authorised-autonomous-apply`: unattended substantive edits are allowed only within a valid authority record and consequence policy.

Unknown or missing modes must fail closed.

### R2. Manifest, authority, and policy

Every v0.2 wiki must have a versioned `wiki-manifest.yml`. `schema/agent_policy.yml` defines the modes, limits, and kinds of authority the wiki permits; separate committed records under `schema/authorities/` grant time-bounded authority to a particular owner label. The template ships with no active grant. Editable policies/grants must be YAML parsed with a safe, real YAML implementation; hand-written YAML parsing is not acceptable for operational authority. Policies, manifests, authority grants, run records, and reports must validate against versioned JSON Schema contracts. Runtime records and reports must use canonical JSON.

An authority record must declare:

- stable authority ID, owner label, issue time, expiry, and revocation state;
- permitted modes, lanes, actions, page types, and writable paths;
- prohibited actions and stop conditions;
- required validation checks and approval gates;
- maximum run duration and optional acquisition/change budgets;
- commit policy: forbidden, manual, or scoped automatic commit, plus an optional explicit commit identity;
- consequence-policy reference and maximum permitted consequence tier.

Scheduled and autonomous runs must use authority state from the clean base commit. Dirty or agent-modified policy must not silently authorise a run.

Policy parsing must reject unsafe YAML tags, oversized configuration, unknown producer fields, invalid path patterns, and schema-version mismatches. Strict producer validation and version-aware permissive reading are separate behaviors.

### R3. Lane contract

The core lanes are:

```text
acquire -> ingest -> synthesize -> maintain
```

Each lane must declare input roots, immutable input snapshots, outputs, allowed actions, writable paths, validation, and closure outcomes: `no-op`, `blocked`, `failed`, `cancelled`, `recovery-required`, `manual-commit-required`, `approval-required`, or `complete`. Dependencies must be expressed by validated artifacts and lifecycle state, not assumed cron timing.

Maintenance must distinguish deterministic maintenance from semantic/editorial review.

### R4. Run contract and controller

Every mutating run must have:

- run ID, lane, mode, authority ID, start/end timestamps, and current state;
- base commit and initial Git status snapshot;
- declared input roots, immutable input/source snapshot, and declared writable paths;
- lock metadata and heartbeat/lease state;
- capability snapshot and required validation set;
- changed-path reconciliation;
- structured report location and closure state;
- exact recovery or review action on failure.

The controller must support both managed subprocess runs and a persistent session protocol for external agents: `start`, `heartbeat`, `status`, `finish`, `cancel`, and `fail`. External sessions receive a random run token used to prevent accidental cross-run control; tokens stay in untracked runtime state and must never be copied into durable reports.

### R5. Single-writer safety

- A per-wiki mutation lock directory must be acquired atomically before the authoritative Git/input preflight or any changes.
- Lock metadata must include run ID, process, host, acquisition time, lease, heartbeat, lane, mode, and declared paths.
- Read-only commands must not require the mutation lock.
- Stale locks must be diagnosed; breaking a lock must be an explicit, audited operation.
- Lock and active-run state must live in a dedicated ignored `.wiki_state/` directory that is explicitly non-cache and must not be removed by cache rebuild/cleanup commands.
- The initial implementation may assume local POSIX-like filesystem semantics on one host/worktree.
- Scheduled/autonomous preflight must detect additional Git worktrees for the same repository and fail as an unsupported topology in v0.2 rather than pretending a per-worktree lock is sufficient.

### R6. Recoverable ingestion

Ingestion must use an idempotent source lifecycle:

```text
captured -> raw-preserved -> registered -> reference-created -> validated -> inbox-archived
```

Raw preservation is never rolled back. Each transition must be journalled and safely resumable. The SHA-256 digest is the idempotency key. Re-running an interrupted source must complete the existing record rather than create a duplicate source ID.

`captured` means that the input path, size, digest, and proposed stable source ID have been recorded while the lock is held. Preservation must copy through a temporary file, verify the copied digest, and atomically create the final raw path without overwriting an existing raw file.

Existing files under `sources/raw/` are append-only evidence: final reconciliation must reject modification, deletion, or rename of any pre-existing raw path. An authorised ingest may only add a new raw path whose hash is registered in the same run.

### R7. Git-aware preflight and closure

- Scheduled and autonomous mutation must require a clean expected base outside declared lane input roots. An ingest run may accept snapshotted untracked files directly under `inbox/`; staged files, modified tracked files, symlinks, and unexpected paths remain blocking conditions.
- Manual-assist runs may snapshot existing changes but must never stage or commit them accidentally.
- The mutation lock must be held while the authoritative base/input snapshot is taken, and `HEAD` must still equal the recorded base immediately before any automatic commit.
- The controller must reconcile the final diff against declared writable paths.
- Unexpected changes must block closure and automatic commit.
- Automatic commits must be opt-in authority capabilities. `scoped-auto` uses a temporary Git index seeded from the base commit, stages only reconciled explicit pathspecs, verifies the resulting path set/content manifest, creates the commit with Git plumbing, and compare-and-swap updates the current local branch only if it still points at the base commit. Repository commit hooks are not executed; RB Wiki validation is the recorded gate. The commit message must contain a `RB-Wiki-Run` trailer linking it to the run ID.
- A run that cannot safely commit must end as `manual-commit-required` with an exact path list.

Durable reports included in the same commit record the run ID, base commit, reconciled content/audit path sets, and the non-audit content-manifest hash. They do not attempt to contain the staged tree or future commit hash because either would be self-referential. The final untracked runtime receipt records the resulting tree/commit hashes and verifies the committed path set and content manifest.

### R8. Provenance reconciliation

The deterministic provenance checker must reconcile:

```text
raw source <-> registry entry <-> Reference page <-> ordinary page sources field
```

It must detect missing, duplicate, mismatched, or divergent source IDs, hashes, raw paths, reference paths, source types, and citations. It must not infer semantic claim support; semantic evidence assessment remains an agent/reviewer responsibility.

### R9. Orthogonal lifecycle metadata

The existing page `status` remains for compatibility. v0.2 adds separate fields for workflow and evidence maturity, with one canonical owner for each value:

- source transition journal and registry: `ingest_state` and `access_level`;
- Reference page frontmatter: `integration_state`, `assessment_state`, and `review_state`.

Reports and queues may project these values but must not become another source of truth. Names and allowed values must remain domain-neutral. Subject profiles may refine assessment rules without changing the core meanings. Provenance validation must detect any explicitly mirrored value that diverges from its canonical owner.

### R10. Honest capabilities and lint

- `tools/capabilities.py --json` must report implemented, unavailable, optional, and semantic/agent-required capabilities.
- BM25, vector, and hybrid aliases must not be presented as implemented search backends.
- Every lint check must report an outcome (`pass`, `fail`, `not_run`, `error`), severity (`info`, `warning`, `error`, `critical`), and disposition (`observe`, `action-required`, `approval-required`).
- A check that was not performed must never report `pass`.
- New References may use a configurable integration grace period before becoming warnings.

### R11. Structured reports and retention

- Canonical run/check records must be JSON and validate against a versioned JSON Schema contract.
- Markdown reports remain as human-readable renderings.
- `.wiki_state/latest.json` must summarise the latest runtime attempt without creating tracked churn. A stable `reports/latest.json` must summarise the latest durable/material state and change only when that durable state changes.
- Mutation, post-mutation failure/recovery, manual-commit, approval-required, break-lock, and governance reports are durable audit records; transient pre-mutation contention may remain ephemeral unless policy escalates it.
- Routine no-op, all-pass, and transient contention telemetry lives under ignored `.wiki_state/runs/`. Policy-defined mutation, post-mutation failure/recovery, manual-commit, approval, and governance records are promoted to tracked `reports/runs/`.
- Agents must not silently delete durable reports. Ephemeral cleanup is allowed only under the explicit runtime retention policy and must never remove active/incomplete journals.

### R12. High-consequence policy

The generic policy must attach consequence controls to intended use, claim/action class, and proposed output. It must not assume an entire domain or source is uniformly high consequence.

Policy precedence is:

1. Core invariants.
2. Operational policy.
3. Domain profile.
4. Project/run authority.

Lower layers may tighten but must not weaken core invariants. Domain adapters may define admissibility, source hierarchy, assessment, reviewers, and approval thresholds.

High-consequence changes use a two-run proposal/approval/apply protocol. The proposal must include an exact patch or deterministic target-content bundle; the apply run must read an unexpired approval from its clean base commit, and that approval must bind the immutable digest of this exact apply payload. The apply run cannot create or modify its own approval, and its final diff must match the approved payload.

### R13. Template health and migration

- `wiki-manifest.yml` must record template, profile, tool, report-contract, and policy versions plus enabled capabilities.
- `wiki_doctor.py` must inspect compatibility, missing capabilities, local overrides, and migration readiness without modifying files.
- `wiki_migrate.py --dry-run` must produce a precise machine-readable plan and reviewed patch before any migration.
- v0.2 does not directly apply migrations. Explicitly applied generated patches must be versioned and reviewable; a subsequent dry-run must be a no-op, and listed local policy files must not be overwritten.
- New-wiki setup must build and validate in a temporary sibling directory, then atomically publish the requested destination. A failed setup must not leave a partially configured destination; it must retain or report a clearly named diagnostic staging path and exact cleanup/retry instructions.

### R14. Tests for unattended operation

The suite must cover lock contention, idempotent ingest, interruption at each transition, stale-lock handling, dirty worktrees, authority expiry/revocation, path-scope enforcement, commit closure, provenance mismatches, structured report validation, semantic checks marked `not_run`, consequence gates, and v0.1 migration. Existing PDF tests must continue to pass.

### R15. Untrusted inputs and path safety

- All input, output, and path-policy values must be normalised relative to the wiki root; reject absolute paths, `..` traversal, symlink traversal, and paths that resolve outside the wiki.
- Inbox processing must enforce policy-defined file-count and file-size budgets before expensive parsing or extraction.
- Raw/source content is data, never executable configuration or agent authority. Deterministic tools must not execute, import, or shell-evaluate source content or filenames.
- Agent prompts and lane contracts must state that instructions found inside acquired sources cannot expand authority, change policy, or override the run envelope.
- Subprocesses must use argument arrays, explicit timeouts, and no shell interpolation for source-controlled values.
- YAML loaders must use safe construction and reject executable/custom tags.

## Assumptions

- v0.2 supports one host and one writable worktree per wiki.
- Agents cooperate with the run protocol; postflight detects accidental out-of-scope changes but cannot stop deliberate bypass.
- Git is required for scheduled and autonomous mutation modes.
- `scoped-auto` requires a normal local branch with clean index, no unresolved merges, no sparse checkout/submodule boundary in declared paths, and a configured or authority-declared commit identity; unsupported Git topology fails closed.
- The existing Python CLI architecture and `unittest` framework remain in place.
- Python 3.10 or newer is required, matching the syntax already used by the codebase.
- YAML is used for human-edited manifest/policy files and JSON for runtime records. PyYAML 6.x and `jsonschema` 4.x are explicit required dependencies; missing dependencies fail with a clear diagnostic and no fallback parser.
- Semantic synthesis, appraisal, contradiction interpretation, and relevance decisions are performed by an external LLM agent under the recorded authority.
- Existing `llm-wiki-profile/0.1` wikis remain readable; v0.2 metadata is introduced through versioned migration.
- `CONTEXT.md` is absent, so this plan uses repository docs, code, tests, and `updates-needed.txt` as project context.

## Constraints

- Raw files in `sources/raw/` remain immutable and are never deleted automatically.
- Existing standard Markdown link and OKF compatibility rules remain canonical.
- No silent fallback or optimistic `pass` result is permitted.
- Scheduled automation must remain conservative unless explicit authority enables bounded apply behavior.
- Existing scripts should remain callable during staged migration; wrappers may progressively route them through the run controller.
- The public toolkit must stay generic; domain policy is configuration, not core branching logic.
- Report retention must respect audit requirements and the repository's no-unilateral-deletion rule.
- `.wiki_state/` is recoverable operational state, not a disposable cache. Cache cleanup must never remove it.
- Inputs and policy paths are resolved and checked within the wiki root before any filesystem operation.

## Proposed Approach

### Architecture

Add these primary artifacts to each v0.2 subject wiki:

```text
wiki-manifest.yml
docs/AGENT_OPERATIONS.md
schema/agent_policy.yml
schema/authorities/
schema/consequence_policy.yml
schema/contracts/wiki-manifest.schema.json
schema/contracts/agent-policy.schema.json
schema/contracts/authority-grant.schema.json
schema/contracts/consequence-policy.schema.json
schema/contracts/run-record.schema.json
schema/contracts/check-result.schema.json
schema/contracts/source-registry.schema.json
schema/contracts/page-frontmatter.schema.json
tools/wiki_run.py
tools/run_lib.py
tools/capabilities.py
tools/provenance.py
tools/wiki_doctor.py
tools/wiki_migrate.py
.wiki_state/
reports/runs/
reports/proposals/
reports/approvals/
reports/latest.json
```

The standalone `wiki-template/` copy is the canonical source for runtime tools, contracts, and wiki-local operations documentation because every generated wiki must remain self-contained. Root documentation and skills should link to wiki-local contracts where possible. Any unavoidable copied reference material must be generated through a checked sync step, and a test must detect drift.

### Runtime states

Run state transitions:

```text
created -> lock-acquired -> preflight-passed -> running
        -> validating -> closing
        -> complete | no-op | blocked | failed | cancelled
        -> recovery-required | manual-commit-required | approval-required
```

State changes use atomic write-then-rename JSON updates. Active attempt journals and runtime receipts live under `.wiki_state/`; durable mutation/failure/approval records are promoted to `reports/runs/`. A terminal outcome that later receives a human commit, recovery, or approval is not rewritten silently: a linked resolution record captures the follow-up.

### Structured data approach

- Use versioned JSON Schema files as the contract source of truth. Parse human-authored YAML with `yaml.safe_load`, validate the resulting data with `jsonschema`, then construct small dataclasses for internal behavior.
- Add PyYAML and `jsonschema` as explicit dependencies rather than extending handwritten YAML parsing.
- Migrate registry and frontmatter reading to the same safe YAML layer in the phases that change those formats; avoid bulk reserialisation of unchanged pages.
- Use deterministic JSON serialisation for run records and reports.
- Do not add an LLM framework dependency; external agents consume and produce declared artifacts.

### Deterministic versus semantic work

Deterministic tooling owns policy syntax, locking, state transitions, hashes, path scope, Git state, provenance reconciliation, capability reporting, report validation, and structural lint.

Agents own acquisition relevance, summarisation, evidence interpretation, synthesis, contradiction analysis, and domain assessment. When an authorised agent has not performed a semantic check, the deterministic report must say `not_run` or `agent-required`.

## Implementation Phases

Detailed executable checklists are in the linked phase files. Tasks begin as `[ ]`, become `[x]` when implemented, and become `[v]` only after independent verification.

1. [Phase 1: Safe scheduled-propose walking skeleton](PHASE_1_WALKING_SKELETON.md)
2. [Phase 2: Authority, session protocol, and Git closure](PHASE_2_RUN_SAFETY.md)
3. [Phase 3: Recoverable ingestion and provenance foundation](PHASE_3_RECOVERABLE_INGEST.md)
4. [Phase 4: Lifecycle-aware lint, reports, and capability honesty](PHASE_4_LIFECYCLE_REPORTS.md)
5. [Phase 5: Autonomous semantic lanes and high-consequence policy](PHASE_5_AUTONOMOUS_LANES.md)
6. [Phase 6: Doctor, migrations, documentation sync, and release qualification](PHASE_6_MIGRATION_RELEASE.md)

No phase is complete until every task is `[v]` and the phase review-and-fix cycle has no blocking findings.

### Release Gates

- After Phase 1, only bounded deterministic `scheduled-propose` maintenance is supported through the new controller.
- After Phase 3, unattended source ingestion may be enabled because lock, recovery, and provenance foundations are verified.
- `authorised-autonomous-apply` must remain disabled until Phase 5 has passed all authority, semantic-boundary, and consequence-gate tests.
- v0.2 is not release-qualified until Phase 6 migration, sustained-operation, documentation, and final review gates pass.

## Validation Plan

### Test levels

- Unit tests for contract parsing, state machines, lock records, path matching, severity mapping, provenance reconciliation, and report serialisation.
- Integration tests in temporary copied wikis and temporary Git repositories.
- Concurrency tests using competing subprocesses.
- Failure-injection tests at every mutating transition.
- End-to-end lane tests using deterministic fake agent actions.
- Migration fixtures for clean and locally modified v0.1 wikis.
- Existing template validation and PDF extraction tests.

### Required commands

The release interface must include these commands:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s wiki-template/tests -v
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v
PYTHONDONTWRITEBYTECODE=1 python3 wiki-template/tools/capabilities.py --json
PYTHONDONTWRITEBYTECODE=1 python3 wiki-template/tools/wiki_doctor.py --json
PYTHONDONTWRITEBYTECODE=1 python3 wiki-template/tools/provenance.py validate
```

`wiki-template/tests/` owns copied-wiki tool/unit tests. Root `tests/` owns starter-kit setup, distribution-sync, migration, and end-to-end integration tests. Tests that invoke mutating lint, ingest, setup, migration, or run-controller commands must operate on disposable wiki copies and temporary Git repositories, never the committed public template.

## Risks

### False security from cooperative enforcement

The run controller cannot protect against processes that ignore it. Mitigation: state the trust model, restrict autonomous tools where the host supports it, snapshot Git state, and fail closure on unexpected changes.

### Stale or incorrectly broken locks

Automatic stale-lock deletion could create two writers. Mitigation: use leases and heartbeat diagnostics, require an explicit audited break-lock action, and test process-death scenarios.

### Partial migration creates mixed contracts

Older tools may not understand v0.2 fields. Mitigation: manifest gating, doctor checks, idempotent migrations, explicit minimum tool versions, and no automatic migration during ordinary runs.

### Policy complexity becomes another source of ambiguity

Over-flexible authority can be hard to audit. Mitigation: constrained enums, deterministic validation, conservative defaults, example policies, and rejection of unknown fields in producer mode.

### Report and journal churn recreates dirty-worktree problems

Mitigation: separate ephemeral telemetry from durable audit records, keep a stable latest summary, and promote only policy-defined records into tracked reports.

### Human edits occur while an agent holds the lock

The lock coordinates cooperating tools, not editors. Mitigation: final Git/path reconciliation, manual-commit state, and no automatic commit when unexpected changes appear.

### Lifecycle fields become a new status taxonomy

Mitigation: define orthogonal meanings, avoid domain-specific values, keep page `status` unchanged, and provide migration/validation examples.

### High-consequence policy is applied too broadly or narrowly

Mitigation: bind gates to intended use and action class, require explicit consequence declarations, allow domain profiles only to tighten policy, and test denied/approval-required paths.

### Dependency change affects zero-install use

Using real YAML parsing adds installation work. Mitigation: add explicit packaging/setup instructions, pin a supported range, fail fast with a clear message, and avoid additional runtime dependencies unless justified.

### Declared inbox inputs weaken clean-base checks

Allowing untracked inbox files is necessary for unattended ingest but could mask unrelated dirt. Mitigation: permit only snapshotted direct files under declared input roots, reject staged/modified tracked inputs and symlinks, record size/hash before work, and require all other paths to match the clean base.

### Runtime state is ignored by Git

`.wiki_state/` must survive process restart but is not portable through clone. Mitigation: mark it non-cache, protect it from cleanup, persist material artifacts to tracked reports, and make `wiki_doctor.py` reconstruct/diagnose incomplete state from raw files, registry, References, and Git when runtime state is missing.

### Report and commit linkage is circular

A report committed with the content cannot contain its own future commit hash or a staged tree hash that includes the report. Mitigation: record a deterministic hash manifest of declared non-audit content, add the run ID as a commit trailer, then store the actual tree/commit hashes in the untracked final runtime receipt and verify the committed path set/content manifest.

### Acquired content contains hostile instructions or paths

Mitigation: treat all source content as untrusted data, reject path/symlink escapes, impose size/count/time budgets, never execute source-controlled values, and require agents to follow only the controller-issued envelope derived from committed policy and authority.

## Success Criteria

- Two simultaneous mutating runs result in exactly one lock holder; the other exits `blocked` without mutation.
- A scheduled or autonomous run with unexpected dirt outside declared snapshotted input roots exits before mutation with a structured diagnosis.
- An interrupted ingest resumes to exactly one raw file, one registry entry, one Reference page, and one processed inbox copy.
- Failure injection after every ingest transition preserves raw evidence and records the exact next safe action.
- An out-of-scope changed path prevents closure and automatic commit.
- Automatic commit, when explicitly authorised, includes only declared paths.
- An automatic commit's non-audit content manifest and `RB-Wiki-Run` trailer reconcile to the durable report, committed paths, and final runtime receipt.
- Provenance validation detects deliberately introduced raw/registry/reference/citation mismatches.
- Capability JSON accurately reports lexical search and marks BM25/vector/hybrid unavailable unless actually installed.
- No lint check reports `pass` when its implementation did not run.
- A newly validated Reference inside its grace period is informational rather than making the whole wiki Yellow.
- `scheduled-propose` cannot close successfully after a substantive content edit.
- `authorised-autonomous-apply` cannot exceed authority scope or consequence tier.
- Routine all-pass runs do not create unbounded tracked report files.
- `wiki_doctor.py` diagnoses a v0.1 wiki, and migration dry-run identifies all planned changes and local overrides without mutation.
- Failed new-wiki setup never exposes a partial requested destination; successful setup publishes only after validation.
- Existing wiki creation, validation, graph/index building, ingestion, and PDF tests continue to pass.
- Path traversal, symlink, oversized-input, changing-input, unsafe-YAML, and source-instruction fixtures fail closed without escaping declared scope.
- Every phase checklist reaches `[v]` and completes a review-and-fix cycle before v0.2 is declared ready.

## Open Questions

No blocking architectural questions remain. The following defaults are part of the plan and may be tuned only through reviewed implementation changes:

- Python 3.10+, PyYAML 6.x, and `jsonschema` 4.x are the supported baseline.
- External sessions heartbeat every 60 seconds with a five-minute lease. Lease expiry diagnoses a stale run but never breaks the lock automatically. Break-lock requires `manual-assist` or governance-maintenance authority, an explicit reason, and confirmation that no same-host owner process is alive.
- `manual-assist` may close with unrelated pre-existing dirty paths only when there is no overlap, no automatic commit, and the initial/final path sets are preserved in the report.
- New References have a seven-day default integration grace period; policy may shorten it, including to zero for high-priority/high-consequence work.
- Ephemeral completed runtime attempts may be pruned after 30 days by an explicit maintenance command; active/incomplete state and durable reports are never automatically removed.
- Initial consequence tiers are `routine`, `material`, and `high-consequence`. High-consequence apply always requires a separately recorded approval bound to an immutable proposal digest.
- v0.2 migration tooling is read-only by default and emits a reviewed migration plan plus patch; direct migration apply is deferred.
- Cross-host and multiple-writable-worktree mutation remain deferred.
