# RB Wiki v0.2: Release Hardening and Incremental Modularisation

Status: complete — Phases 1–5 verified

Created: 2026-07-13

Source: whole-codebase adversarial review completed 2026-07-13

Predecessor: [`../rb-wiki-v0.2-human-agent-operations/IMPLEMENTATION_PLAN.md`](../rb-wiki-v0.2-human-agent-operations/IMPLEMENTATION_PLAN.md)

## Summary

The v0.2 implementation has strong foundations and a green ordinary regression suite, but adversarial review found release-blocking gaps at the boundaries between lane contracts, authority records, external-agent attestations, Git commit closure, cron orchestration, migration path safety, and provenance reconciliation. This plan closes every confirmed gap, strengthens persisted contracts and capability/cache honesty, and incrementally separates the large controller modules without changing the public command surface or adopting a new agent framework.

The walking skeleton is a disposable-wiki external session that proves four fail-closed properties end to end: the selected lane contract is the runtime source of truth, the requested authority ID is bound to the committed grant, any failed check prevents closure, and transient lock contention remains explicitly blocked. Later phases extend that same contract-driven path through recoverable Git closure, cron cleanup, filesystem/provenance integrity, capability/state/cache contracts, and release qualification.

No phase is complete until its tasks move from `[ ]` to `[x]`, are independently verified as `[v]`, and receive a review-and-fix pass.

## Goals

- Make versioned lane contracts executable runtime policy rather than descriptive documentation.
- Bind every policy, authority, proposal, approval, and runtime artifact to its requested identity and clean-base source.
- Ensure no failed or contradictory external check can be masked during closure.
- Make scoped automatic commit closure recoverable and auditable across every failure before and after branch movement.
- Guarantee cron-controlled sessions terminate or enter an explicit recovery state after exceptions.
- Enforce root-relative, parent-component symlink safety consistently in migration, provenance, controller, and resolution paths.
- Reconcile provenance in both directions so unregistered raw evidence and orphan or duplicate Reference pages are detected.
- Make manifest capabilities, controller snapshots, cached routing data, and persisted runtime state truthful and versioned.
- Verify resolution commit references against the Git object database and relevant run evidence.
- Reduce duplicated policy and oversized controller modules through small, test-protected extractions.
- Improve external-agent provenance and observability without coupling RB Wiki to a model provider or agent framework.
- Retain the current one-host, one-writable-worktree, cooperative-agent operating boundary.

## Non-goals

- Rewriting `wiki_run.py` or `run_lib.py` in one change.
- Adding a hosted workflow engine, database, message queue, MCP server, or LLM-agent framework.
- Selecting or routing model providers.
- Executing semantic review deterministically or treating structural provenance as proof of truth.
- Supporting hostile processes that deliberately bypass the controller and write directly to the repository.
- Supporting multiple concurrent mutating hosts or writable worktrees.
- Automatically pushing commits or changing remote-branch policy.
- Changing established page, registry, proposal, approval, or command formats without a versioned compatibility path.

## Users

- Maintainers preparing and releasing the v0.2 toolkit.
- Human operators running manual-assist sessions and resolving interrupted runs.
- Scheduled agents performing ingestion, maintenance, acquisition, or proposal work.
- Explicitly authorised agents applying bounded semantic changes.
- Reviewers auditing authority, evidence, checks, commits, approvals, and recovery actions.
- Maintainers of copied wikis using doctor and migration tooling.

## Requirements

### H1. Executable lane contracts

- Load and validate the selected versioned lane contract at session start and closure.
- Bind `controller_lane`, allowed modes, action-by-mode, input/output artifact classes, substantive-edit permission, and required checks to runtime enforcement.
- Reject an ambiguous or duplicate contract for the same controller lane/mode.
- Reject grants whose actions, output scope, or page permissions exceed the selected lane contract.
- For `substantive_wiki_edits: false`, reject substantive page changes regardless of authority writable-path breadth or commit policy.
- Keep semantic proposal/apply specialisation explicit and contract-driven rather than scattered lane conditionals.

### H2. Authority and policy identity binding

- Centralise working-tree and base-commit policy loading behind one identity-validating interface.
- Require a requested authority ID to equal the grant's `authority_id` for start, finish, break-lock, resolution, managed runs, and cron runs.
- Apply equivalent identity/version checks to manifests, operational policies, consequence policies, proposals, approvals, and lane contracts where the requested path implies an identity.
- Preserve the rule that scheduled/autonomous authority comes from the clean base commit.

### H3. External checks and closure semantics

- Validate check IDs and statuses before session mutation.
- Reject duplicate check IDs rather than applying last-value-wins behavior.
- Gate on every submitted result and distinguish external attestations from controller-executed checks.
- Preserve `blocked` for transient contention; never overwrite it with `failed` during exception cleanup.
- Prevent double terminalisation and require state/result/finished-time consistency.

### H4. Recoverable Git transaction closure

- Model scoped commit closure as explicit prepare, commit-created, branch-moved, index-refreshed, receipt-written, and reconciled steps.
- Record the commit/tree identity as soon as branch movement succeeds, even if later local bookkeeping fails.
- Introduce `committed-recovery-required` as the explicit state/result after a successful branch move whose local bookkeeping has not reconciled; only the recovery command or audited resolution may move it to a final completed/acknowledged outcome.
- Make index refresh, session persistence, receipt writing, and final reconciliation idempotently recoverable.
- Reconcile recovery using the `RB-Wiki-Run` trailer, base commit, changed paths, and content manifest.
- Extend doctor and resolution tooling to diagnose and complete or acknowledge interrupted post-commit closure.

### H5. Exception-safe scheduled orchestration

- Give `wiki_cron.py` ownership of exactly one started session and one terminal/recovery outcome.
- Wrap every operation after `start_session()` in exception-safe cleanup, including policy loading, inbox enumeration, empty-inbox closure, report writing, linting, finishing, and termination.
- Avoid recursive or duplicate termination when the original terminal operation itself fails.
- Preserve evidence and report the exact recovery action when cleanup cannot finish.

### H6. Filesystem and symlink safety

- Centralise lexical root-boundary and parent-component symlink checks.
- Reject symlinked final components and symlinked parent directories for every operational read/write target.
- Apply the shared boundary to migration source/template inputs, migration targets, provenance scans, resolution records, policy files, report paths, cache paths, and runtime-state paths.
- Ensure migration never includes external content in its patch or machine-readable plan, including on manual-review exits.

### H7. Bidirectional provenance

- Continue validating every registry entry against raw evidence and its Reference page.
- Reverse-scan raw evidence and reject unregistered or multiply registered files.
- Reverse-scan all Reference pages and reject orphan, duplicate, path-mismatched, or unregistered References.
- Retain ordinary-page citation reconciliation and explicitly handle incomplete recovery journals without silently accepting unexplained artifacts.
- Reject symlinked or escaped evidence and Reference paths in both scan directions.

### H8. Complete persisted contracts and semantic invariants

- Add versioned schemas for ingest reports, commit receipts, sessions, run envelopes, and latest snapshots.
- Validate every persisted or externally exchanged artifact before writing and after loading.
- Add semantic validators for state/result/timestamp/report-class consistency and ordered ingest transition prefixes.
- Validate outcome, failed transition, next transition, completed transitions, and terminal state as one invariant set.
- Define compatible reading behavior for existing v0.2 runtime data or provide an explicit diagnostic/migration rule.

### H9. Capability and agent-envelope honesty

- Reconcile `wiki-manifest.yml` enabled capabilities against the capability registry; define `lifecycle-metadata` explicitly or remove it.
- Replace file-existence-only claims with contract, dependency, version, and executable precondition checks where appropriate.
- Include the exact controller capability snapshot or digest in external run envelopes and persisted run records.
- Require scheduled proposals to bind the same snapshot; autonomous apply must verify the base-committed proposal snapshot against the active controller snapshot.
- Doctor must report manifest-only, registry-only, unavailable-enabled, and stale capability declarations.

### H10. Routing-cache integrity

- Version the graph cache and bind it to a deterministic source manifest or digest.
- Detect stale, malformed, symlinked, or incompatible graph caches before query/routing use.
- Rebuild safely when permitted or return an explicit unavailable/stale diagnostic in read-only contexts.
- Test page edits, deletions, malformed cache data, schema upgrades, and cache write interruption.

### H11. Resolution evidence

- Verify an optional resolution commit hash exists and names a commit object.
- Where a resolution claims to close a run, verify an `RB-Wiki-Run` trailer or reconcile the claimed path/content manifest relationship.
- Record when a resolution is an acknowledgement rather than a controller-created managed commit.
- Reject nonexistent, unrelated, tree/blob, abbreviated, or malformed object identifiers.

### H12. Incremental modularisation

- Introduce a root-scoped `WikiContext` so reusable logic does not depend on module-level `ROOT` globals.
- Extract only cohesive, already-tested responsibilities: contracts, filesystem safety, authority/policy loading, lane runtime, Git transaction, and run storage.
- Keep `wiki_run.py` as CLI and high-level orchestration and preserve public commands/exit meanings.
- Avoid circular imports and duplicate compatibility layers; delete superseded logic after each caller migrates.
- Require characterization tests before extraction and full regression after each boundary change.

### H13. External-agent observability and evals

- Preserve RB Wiki's provider-independent external-agent protocol; do not embed an agent framework.
- Add optional bounded provenance fields for agent/runtime identifier, model/provider/version where supplied, prompt/policy digest, trace URI, and timing/tool summary.
- Never persist session tokens, credentials, full private prompts, or unrestricted tool arguments.
- Keep external checks explicitly labelled as attestations with optional structured evidence references.
- Add deterministic fake-agent and fault-injection evaluations; no live model call is required for release qualification.

### H14. Documentation, migration, and distribution consistency

- Update trust-model, agent-operations, upgrade, capability, and recovery documentation to match actual behavior.
- Update skills and system instructions only after executable behavior is verified.
- Preserve `wiki-template/` as the canonical standalone runtime and extend distribution-sync checks for any deliberate copies.
- Ensure new-wiki setup receives every new schema/module/doc and produces a clean, operational standalone repository.

## Assumptions

- Python 3.10+, PyYAML 6.x, `jsonschema` 4.x, and Git remain the supported runtime baseline.
- Existing JSON Schema and canonical-JSON conventions remain authoritative.
- The repository has no root `CONTEXT.md`; `wiki-template/AGENTS.md`, existing plans, code, tests, and current documentation provide project context.
- Agents cooperate with envelopes and controller commands; host filesystem permissions remain the ultimate enforcement boundary.
- Runtime-state compatibility can be handled with explicit version-aware readers or clear recovery diagnostics because `.wiki_state` is local and untracked.
- The current uncommitted v0.2 implementation remains the baseline; this plan does not rewrite its completed historical plan files.

## Constraints

- No automatic push or remote coordination.
- One host, one writable worktree, one mutating run at a time.
- Security-sensitive paths must fail closed; silent fallback is not acceptable.
- Raw evidence remains append-only and must not be deleted or rewritten during remediation.
- Migration remains dry-run/patch-only.
- Public CLI compatibility should be preserved unless safety requires a documented breaking change.
- Each phase must leave the repository runnable and independently testable.

## Proposed Approach

### Existing stack and architecture decision

Preserve the current provider-independent architecture: external agents exchange versioned artifacts with deterministic Python tools. Continue using the standard library, PyYAML, `jsonschema`, Git plumbing, canonical JSON, and Markdown renderings. Do not add PydanticAI, OpenAI Agents SDK, FastMCP, LangGraph, Temporal, LiteLLM, or an observability service; none is necessary to close these deterministic correctness gaps. Export-friendly optional trace metadata is sufficient for this release.

### Capability scaling decisions

| Capability | Classification | Decision |
|---|---|---|
| Policy, authority, lane, path, schema, Git, cache, and provenance checks | Deterministic tool | Keep executable, fail-closed, and conventionally tested. |
| Natural-language evidence quality, contradiction, synthesis, and review | External semantic-agent judgment | Keep outside deterministic tools; accept only attributed structured artifacts/attestations. |
| Lane-specific controller behavior | Embedded deterministic capability | Centralise behind `lane_runtime.py`; no new agent. |
| Commit recovery and cron retry/cleanup | Durable local workflow/state machine | Use repository journals and idempotent commands; no workflow-engine dependency. |
| Provider/model routing | Not required | Keep absent and report no claim. |
| Retrieval backends beyond lexical search | Not required | Preserve truthful unavailable capability reporting. |

### Agent and tool boundary

```text
human / scheduler / external agent
        |
        | start + typed envelope
        v
wiki_run / wiki_cron orchestration
        |
        +-- authority + lane contracts (scope and action)
        +-- filesystem safety (path boundary)
        +-- run store (session, journal, receipt, latest)
        +-- deterministic validators (checks, provenance, artifacts)
        +-- Git transaction (local commit and recovery)
        |
        | typed artifact / attestation / exact payload
        v
durable reports + untracked runtime state + optional local commit
```

The external agent owns semantic work and supplies attributed output. The controller alone owns authority interpretation, state transitions, deterministic validation, Git closure, and durable outcome classification. Agent output is evidence, never implicit authority.

### Target module boundaries

```text
tools/wiki_context.py       explicit root and canonical directories
tools/contracts.py          schema/YAML/JSON loading and invariant validation
tools/fs_safety.py          lexical paths, root boundaries, symlink components
tools/authority.py          runtime/base policy and identity binding
tools/lane_runtime.py       lane selection, actions, outputs, closure rules
tools/git_transaction.py    scoped commit stages and post-CAS recovery
tools/run_store.py          sessions, journals, receipts, latest snapshots
tools/wiki_run.py           CLI and high-level orchestration
tools/run_lib.py            temporary compatibility facade, then reduced/removed
```

These are target boundaries, not permission for a bulk file move. A module is introduced only when the phase has characterization tests for the responsibility being moved.

### State, durability, and failure containment

- Validate high-risk assumptions—root, clean base, authority identity, lane selection, artifact identity, capability snapshot, and input digest—before external work begins.
- Persist intent before mutation and persist each irreversible Git/ingest transition immediately after it occurs.
- Treat branch movement as an irreversible boundary with a recovery-required state, not an ordinary exception.
- Use idempotent recovery commands and doctor reconciliation rather than automatic destructive rollback.
- Bound runtime, changed paths, acquired sources, check count, artifact size, and optional observability fields.

### Observability and reproducibility

- Continue canonical run IDs, timestamps, policy/capability snapshots, content manifests, proposal digests, commit trailers, and structured checks.
- Add optional agent/runtime and trace-reference fields with strict size and URI constraints.
- Record controller-executed checks separately from external attestations.
- Use fake-agent fixtures and deterministic fault injection as release evals; record exact seeds/fixtures where randomness is introduced.
- No additional model calls, provider costs, or agent latency are introduced by this plan.

### Retrieval and provider routing

No retrieval or provider architecture change is planned. Lexical query and graph routing remain deterministic; unsupported BM25/vector/hybrid capabilities remain explicitly unavailable. External agents choose their own provider/runtime outside the wiki protocol.

## Implementation Phases

1. [Phase 1: Runtime contract and authority walking skeleton](PHASE_1_RUNTIME_AUTHORITY_BOUNDARIES.md)

   Enforce lane contracts, bind authority identity, reject duplicate checks, preserve blocked outcomes, and establish the first module boundaries.

2. [Phase 2: Transaction and orchestration recovery](PHASE_2_TRANSACTION_AND_ORCHESTRATION_RECOVERY.md)

   Make post-CAS closure and cron-controlled sessions explicitly recoverable and idempotent.

3. [Phase 3: Filesystem and provenance integrity](PHASE_3_FILESYSTEM_AND_PROVENANCE_INTEGRITY.md)

   Centralise symlink/root safety, harden migration, reconcile provenance bidirectionally, and verify resolution commits.

4. [Phase 4: Contracts, capabilities, and cache integrity](PHASE_4_CONTRACT_CAPABILITY_CACHE_HARDENING.md)

   Complete persisted schemas and semantic invariants, capability snapshots, doctor reconciliation, and graph-cache freshness.

5. [Phase 5: Modularisation, observability, and release qualification](PHASE_5_MODULARISATION_OBSERVABILITY_RELEASE.md)

   Finish incremental extractions, add bounded agent provenance, synchronise distribution/docs, and rerun the release and adversarial matrix.

## Review-Finding Traceability

| Review finding | Requirement | Primary phase |
|---|---|---|
| Lane contracts are descriptive and scheduled maintenance can auto-commit substantive edits | H1 | Phase 1 |
| Base authority filename/internal identity mismatch | H2 | Phase 1 |
| Duplicate external check masks an earlier failure | H3 | Phase 1 |
| External-session contention is overwritten from blocked to failed | H3 | Phase 1 |
| Branch moves before post-CAS bookkeeping failure is durably represented | H4 | Phase 2 |
| Cron exception strands running session and mutation lock | H5 | Phase 2 |
| Migration follows parent-directory symlinks and exposes external content | H6 | Phase 3 |
| Provenance misses unregistered raw and orphan/duplicate Reference artifacts | H7 | Phase 3 |
| Resolution accepts syntactically valid but nonexistent/unrelated commits | H11 | Phase 3 |
| Persisted runtime/report interfaces lack schemas and semantic invariants | H8 | Phase 4 |
| Manifest, capability registry, controller, and proposal snapshots diverge | H9 | Phase 4 |
| Existing graph cache is trusted without freshness/version validation | H10 | Phase 4 |
| Large modules, duplicated policy, and mutable root globals obscure ownership | H12 | Phases 1–5 |
| External-agent provenance and trace evidence are too thin for high-consequence unattended work | H13 | Phase 5 |
| Tests/docs/distributed copies do not cover the adversarial boundaries | H14 | All phases |

## Validation Plan

### Test strategy

- Add a regression test for every reproduced failure before changing behavior.
- Use disposable copied wikis and temporary Git repositories for all mutation, migration, and commit tests.
- Add fault injection immediately before and after irreversible transitions.
- Test all relevant callers when centralising a safety rule; do not prove it through only one CLI path.
- Preserve the existing 129 template tests and 25 root tests and expand their counts.
- Test compatibility reading for existing v0.2 artifacts and fail explicitly on unsupported versions.

### Adversarial regression matrix

- Scheduled maintenance substantive edit with broad grant cannot close or commit.
- Requested authority ID cannot resolve to a differently identified committed grant.
- `fail` followed by duplicate `pass` is rejected before closure.
- Lock contention remains `blocked` in latest and journal state.
- Failure after branch CAS reports committed recovery state and is recoverable without duplicate commit.
- Exceptions at every cron step release or deliberately retain a diagnosed recovery lock.
- Symlinked migration parent directories cannot be read and leak no marker content.
- Orphan raw evidence and orphan/duplicate Reference pages fail provenance.
- Fake/non-commit/unrelated resolution hashes are rejected.
- Manifest/proposal/controller capability mismatch fails explicitly.
- Stale graph cache is detected and never silently used.
- Schema-valid but semantically impossible run/transition records are rejected.

### Required release commands

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s wiki-template/tests -v
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v
PYTHONDONTWRITEBYTECODE=1 python3 scripts/sync_distributed.py --check
PYTHONDONTWRITEBYTECODE=1 python3 wiki-template/tools/capabilities.py --json
PYTHONDONTWRITEBYTECODE=1 python3 wiki-template/tools/wiki_doctor.py --json
PYTHONDONTWRITEBYTECODE=1 python3 wiki-template/tools/provenance.py validate
RB_WIKI_RUN_CONTROLLER=1 PYTHONDONTWRITEBYTECODE=1 python3 wiki-template/tools/lint.py --quick --no-report
RB_WIKI_RUN_CONTROLLER=1 PYTHONDONTWRITEBYTECODE=1 python3 wiki-template/tools/lint.py --full --no-report
git diff --check
```

Also meta-validate every JSON Schema and parse/compile every Python file. Doctor may report expected governance dirt in the implementation worktree; a fresh generated wiki must report no blocking diagnostic.

## Risks

### Contract changes accidentally reject supported workflows

Executable lane contracts may expose previously tolerated combinations. Mitigation: characterize every supported lane/mode first, validate all shipped contracts, provide exact diagnostics, and update grants/tests rather than weakening the contract.

### Recovery logic creates duplicate commits or misleading outcomes

A retry after branch movement could repeat work. Mitigation: bind recovery to run trailer, base commit, tree/content manifest, and stored stage; make recovery idempotent and test each failure point.

### Centralisation introduces circular imports or behavior drift

Moving helpers from large modules can change default roots or error handling. Mitigation: introduce `WikiContext`, migrate one call path at a time, keep temporary facades narrow, and delete duplicated logic only after full tests.

### Reverse provenance mistakes recovery artifacts for valid evidence

Interrupted ingest may legitimately leave preserved raw material before registration. Mitigation: reconcile extras against validated source-transition journals and report an explicit recovery-required state rather than silently passing or deleting data.

### Stronger cache checks add rebuild latency

Source-manifest hashing costs scale with wiki size. Mitigation: use deterministic lightweight metadata/digests, measure on representative wikis, and expose stale/unavailable state rather than using an invalid cache.

### Observability fields leak sensitive context

Agent metadata could accidentally include prompts, tokens, or tool arguments. Mitigation: allowlist bounded fields, store hashes/references instead of content, redact tokens, and add secret-leak tests.

### Passing tests create false confidence

The previous complete suite missed boundary failures. Mitigation: retain independent adversarial scenarios and phase completion review rather than relying only on aggregate test count.

## Success Criteria

- Every reproduced failure has a test that fails on the current baseline and passes after remediation.
- Lane contract, authority identity, and check semantics are enforced consistently in all managed and external-session callers.
- No tested failure after branch movement is reported as an ordinary uncommitted failure.
- No cron exception leaves an unexplained running session or lock.
- Migration cannot follow any target/template symlink component or expose external content.
- Provenance detects both missing registered artifacts and unregistered extra artifacts.
- Every persisted/exchanged runtime artifact validates structurally and semantically.
- Capability declarations and proposal/run snapshots reconcile exactly.
- Stale graph caches are detected before use.
- Resolution commits are real, appropriately typed, and evidentially related or explicitly labelled acknowledgements.
- `wiki_run.py` and `run_lib.py` have materially narrower responsibilities without a bulk rewrite or public CLI regression.
- All phase tasks are `[v]`, the complete adversarial matrix passes, the full release matrix passes, and the final review has no unresolved release blocker.

## Open Questions

- Should this remediation remain version `0.2.0` until first release, or become `0.2.1` if v0.2 has already been distributed? Default: decide at release time based on whether an external v0.2 artifact exists.
- Should an orphan raw file with a valid incomplete ingest journal be a provenance failure or a distinct recovery-required diagnostic? Default: recovery-required, never pass.
- Which optional trace URI schemes should be accepted? Default: bounded `https`, `file`-independent opaque IDs, or no URI until a concrete integration exists; never persist credentials.
