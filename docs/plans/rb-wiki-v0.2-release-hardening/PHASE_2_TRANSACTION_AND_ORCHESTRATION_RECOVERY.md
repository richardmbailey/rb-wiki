# Phase 2: Transaction and Orchestration Recovery

## Phase Goal

Ensure every irreversible commit or scheduled-orchestration transition is durably identifiable and recoverable, so branch movement, controller state, receipts, locks, and reports cannot silently disagree.

## Scope

- Explicit scoped-commit transaction stages.
- Post-CAS recovery state and idempotent reconciliation.
- Commit receipt contract and durable recovery evidence.
- Doctor and operator recovery path.
- Exception-safe cron inbox orchestration.
- Fault injection around every irreversible or terminal boundary.
- Incremental extraction of Git transaction and run-store responsibilities required by the recovery slice.

## Non-scope

- Migration/provenance parent-symlink work.
- Capability and graph-cache redesign.
- Provider/framework orchestration.
- Automatic destructive rollback of a successfully created commit.

## Dependencies

- Phase 1 verified runtime contract, authority, check, and state boundaries.
- Existing temporary-index `commit-tree` plus `update-ref` implementation.
- Existing run trailer, content manifest, session journal, durable report, and runtime receipt concepts.

## Task Checklist

- [v] Add a failing fault-injection test reproducing branch movement followed by `read-tree` failure and assert the baseline incorrectly reports an exception without returning/storing the commit.
- [v] Add fault-injection coverage before and after temporary-index creation, staging, tree writing, commit creation, CAS branch update, index refresh, run-record update, receipt write, session save, and lock release.
- [v] Define versioned transaction stages such as `prepared`, `commit-created`, `branch-moved`, `index-refreshed`, `receipt-written`, and `reconciled` with legal forward transitions.
- [v] Schema-model `committed-recovery-required` as the state/result after branch movement but before complete local reconciliation; permit only validated recovery or audited resolution to advance it.
- [v] Persist transaction intent, base commit, target branch, expected paths, and content manifest before commit creation.
- [v] Persist commit/tree identities immediately after creation and branch-movement evidence immediately after successful CAS.
- [v] Ensure any exception after branch movement returns or records the known commit identity and cannot be classified as an ordinary uncommitted failure.
- [v] Introduce `tools/git_transaction.py` around scoped commit preparation, branch CAS, local-index refresh, and reconciliation without changing the public closure command.
- [v] Add a versioned commit-receipt schema and validate receipts before write and after load.
- [v] Make receipt publication, real-index refresh, session update, and final lock handling idempotent when repeated for the same run/commit/tree/content manifest.
- [v] Add a deterministic recovery command or tightly scoped controller action that inspects the run trailer, branch ancestry, tree, paths, and content manifest before completing bookkeeping.
- [v] Reject recovery when branch evidence is missing, divergent, ambiguous, or belongs to another run.
- [v] Extend doctor to detect branch-moved/receipt-missing, receipt-present/session-incomplete, index-refresh-pending, and lock-retained recovery cases without modifying the wiki.
- [v] Define lock ownership during post-commit recovery: retain it while safe automatic reconciliation is possible, and require explicit audited displacement/acknowledgement when recovery cannot finish.
- [v] Verify retries never create a second commit or reapply content after the original branch movement.
- [v] Add a failing cron test that injects an exception immediately after session start and confirms the baseline leaves `running` state and a held lock.
- [v] Add cron fault injection at policy load, acquisition handoff load, inbox enumeration, empty-inbox finish, per-file ingest, report write, lint subprocess, finish, terminate, and terminal-report rendering.
- [v] Refactor `inbox_sweep()` into one controller-owned session lifecycle with a guarded terminal/recovery outcome for everything after successful start.
- [v] Snapshot and restore process-level controller environment flags so an exception or repeated in-process test cannot leak controller authority into later work.
- [v] Ensure cleanup does not call termination twice or overwrite a more informative terminal/recovery state when finish/terminate itself fails.
- [v] Preserve raw evidence and ingest transition journals when orchestration fails; never delete or roll back completed preservation.
- [v] Return stable, documented exit meanings for success, no-op, blocked, approval/manual action, recovery required, and failure.
- [v] Introduce `tools/run_store.py` only for the transaction/session/journal/receipt persistence needed by this phase, with atomic writes and context-rooted paths.
- [v] Validate reloaded session and transaction state before recovery actions and reject tampered or semantically impossible stage combinations.
- [v] Update agent operations, trust model, and recovery documentation with post-CAS and cron recovery procedures.
- [v] Run a focused review for failure windows between persisted state, Git state, and lock state; fix all actionable inconsistencies and rerun injections.

## Verification Checklist

- [v] Every task is implemented `[x]` before verification begins.
- [v] Faults before CAS never move the branch and produce an accurate failed/manual outcome.
- [v] Faults after CAS always expose the actual commit and enter a documented recovery state rather than ordinary failure.
- [v] Recovery completes bookkeeping idempotently without creating another commit.
- [v] Doctor identifies each incomplete transaction stage and gives the exact safe next command.
- [v] Cron exceptions at every injected boundary leave one coherent terminal/recovery journal and no unexplained lock.
- [v] Empty inbox, successful ingest, preservation-only, validation failure, and manual-commit workflows retain their existing user-visible behavior.
- [v] Raw evidence and source-transition recovery guarantees remain intact during cron failures.
- [v] Commit receipt, transaction journal, run record, session, branch trailer, changed paths, and content manifest reconcile.
- [v] Focused tests, full template/root suites, schema validation, AST/compile checks, doctor, and diff hygiene pass.
- [v] Phase completion review finds no unpersisted irreversible transition or duplicate terminalisation path; fixes are applied and checks rerun.
- [v] All completed tasks are independently marked `[v]` only after the recorded checks pass.

## Verification Evidence

- 171 template tests passed in 153.599 seconds; 26 root release tests passed in 40.817 seconds.
- Five post-CAS/fault scenarios cover every pre/post branch boundary, idempotent session and controller recovery, lost branch-stage persistence, divergence rejection, and retained-lock behavior.
- Four cron exception-safety tests cover acquisition, policy, enumeration, empty finish, per-file ingest, report, lint, finish, terminate/reporting, environment restoration, preserved raw transitions, and post-commit recovery.
- All 22 Draft 2020-12 schemas meta-validate; every template Python file parses; doctor reports no incomplete run, transaction, ingest, or provenance state; distribution sync and `git diff --check` pass.

## Tests To Add Or Run

```text
wiki-template/tests/test_post_cas_fault_injection.py
wiki-template/tests/test_commit_receipt_contract.py
wiki-template/tests/test_cron_exception_safety.py
wiki-template/tests/test_commit_closure.py
wiki-template/tests/test_commit_report_linkage.py
wiki-template/tests/test_run_state_machine.py
wiki-template/tests/test_cron_run_integration.py
wiki-template/tests/test_ingest_failure_recovery.py
tests/test_wiki_doctor.py
tests/test_sustained_operations.py
```

## Phase Exit Criteria

For every injected failure, an operator can determine whether the branch moved, identify the exact commit and content manifest when it did, and safely resume or acknowledge the run without duplicate work. Cron-controlled ingestion never strands an unexplained active session or lock.
