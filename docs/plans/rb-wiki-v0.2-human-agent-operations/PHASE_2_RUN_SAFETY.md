# Phase 2: Authority, Session Protocol, and Git Closure

## Phase Goal

Extend the walking skeleton into a reusable run-safety protocol for external agents, with full authority validation, heartbeat/lease handling, path and page-type enforcement, Git closure, and explicit commit policy.

## Scope

- Complete authority contract for all three operating modes.
- Persistent external-agent session lifecycle.
- Lease, heartbeat, status, failure, and explicit lock recovery.
- Initial/final Git snapshots and path-scope enforcement.
- Manual and scoped automatic commit closure.
- Stop conditions and bounded run budgets.

## Non-scope

- Source-level recoverable ingest transitions.
- Semantic evaluation of proposed prose.
- Cross-host distributed locks.
- Domain-specific policy adapters.

## Dependencies

- Phase 1 contracts, lock, run records, capability registry, and walking skeleton verified.

## Task Checklist

- [v] Expand authority validation to cover owner label, issue/expiry/revocation, modes, lanes, actions, input roots, writable paths, page types, budgets, required checks, consequence tier, commit policy, and optional commit identity.
- [v] Require scheduled/autonomous authority and manifest files to match the recorded clean base commit.
- [v] Implement deterministic authority selection with no “closest match” or implicit fallback.
- [v] Implement run state transitions and reject invalid, repeated, or regressive transitions.
- [v] Add `wiki_run.py start`, `heartbeat`, `status`, `finish`, `cancel`, and `fail` commands for external agent sessions.
- [v] Return a machine-readable run envelope containing run ID, random run token, permitted actions, input roots, writable paths, required checks, expiry, and stop conditions.
- [v] Require the run token for session mutation/control commands, store it only under `.wiki_state/`, and redact it from durable reports and ordinary command output after start.
- [v] Add 60-second heartbeat renewal and five-minute lease-expiry diagnostics using an injectable clock for reliable tests.
- [v] Add explicit `wiki_run.py break-lock` requiring manual-assist or governance-maintenance authority, a reason, actor label, observed lock record, same-host process-liveness check, and durable audit report.
- [v] Do not automatically break a lock solely because its timestamp is old.
- [v] Implement initial Git status snapshot including tracked, staged, unstaged, and untracked paths.
- [v] Define mode-specific dirty-state rules: scheduled/autonomous require a clean base outside declared inputs; ingest may accept only snapshotted direct untracked files beneath declared inbox roots; manual-assist uses a protected initial snapshot.
- [v] Normalise all input and writable paths relative to the wiki root and reject absolute paths, `..`, symlinks, and resolved escapes.
- [v] Implement final path reconciliation against initial state and declared writable paths.
- [v] Inspect changed wiki page frontmatter to enforce permitted page types for substantive lanes.
- [v] Implement stop conditions for maximum runtime, maximum changed paths, maximum acquired sources, and validation failure.
- [v] Implement commit policies `forbidden`, `manual`, and local-only `scoped-auto`; never push automatically.
- [v] Reject `scoped-auto` on detached HEAD, unresolved merge, dirty real index, unsupported sparse/submodule path, missing commit identity, or changed base branch.
- [v] For `scoped-auto`, create a temporary index under `.wiki_state/`, seed it from the base commit, and stage only explicit reconciled pathspecs without touching unrelated real-index state.
- [v] Verify the temporary index path set and deterministic non-audit content-manifest hash against the durable pre-commit report.
- [v] Create the commit with Git plumbing and a `RB-Wiki-Run: <run-id>` trailer, then compare-and-swap update the current local branch only when it still points to the base commit; do not execute repository commit hooks.
- [v] After a successful branch update, safely refresh the previously clean real index, verify changed paths/content manifest, and store actual tree/commit hashes only in the final `.wiki_state/` runtime receipt.
- [v] End safely as `manual-commit-required` when changes are valid but automatic closure is forbidden or unsafe.
- [v] Permit manual-assist closure with unrelated initial dirt only when changed paths do not overlap, no automatic commit occurs, and both initial and final path sets are recorded.
- [v] Add a linked resolution-record command for later human commit/recovery acknowledgement without silently rewriting the original terminal outcome.
- [v] Prevent policy, authority, schema, and core tool changes unless the authority explicitly grants governance-maintenance scope.
- [v] Add structured diagnostics for authority expiry, revocation, mode mismatch, lane mismatch, input/path escape, page-type violation, budget exhaustion, unexpected changes, token mismatch, and changed `HEAD`.
- [v] Update `docs/AGENT_OPERATIONS.md` with session examples and recovery rules.
- [v] Add unit and integration tests for every authority field, transition, heartbeat, Git state, path/page scope, stop condition, and commit policy.

## Verification Checklist

- [v] An external fake agent can start, heartbeat, inspect, and finish a bounded run.
- [v] Expired, revoked, dirty, altered, or incompatible authority blocks before mutation.
- [v] A stale heartbeat produces diagnosis but never an automatic second writer.
- [v] Break-lock requires explicit metadata and leaves a durable audit record.
- [v] Manual-assist preserves unrelated initial changes and never stages them.
- [v] Scheduled/autonomous runs reject unexpected dirty bases while accepting only declared, snapshotted direct untracked inbox inputs.
- [v] Out-of-scope paths and page types block closure.
- [v] `scoped-auto` commits only declared reconciled paths.
- [v] `scoped-auto` leaves unrelated real-index state untouched, does not execute hooks or push, and fails without moving the branch when compare-and-swap preconditions change.
- [v] The durable report's non-audit content manifest, commit trailer, committed changed paths, and final runtime receipt reconcile.
- [v] Failed validation and exhausted budgets prevent commit.
- [v] Every terminal state has a valid JSON record and exact next action.
- [v] Phase completion review finds no blocking state-machine, Git-safety, or authority gaps; fixes are applied and checks rerun.

## Tests To Add Or Run

```text
tests/test_authority.py
tests/test_run_state_machine.py
tests/test_run_session_protocol.py
tests/test_run_tokens.py
tests/test_lock_leases.py
tests/test_git_preflight.py
tests/test_declared_inputs.py
tests/test_path_and_page_scope.py
tests/test_commit_closure.py
tests/test_commit_report_linkage.py
tests/test_scoped_auto_plumbing.py
tests/test_scoped_auto_cas.py
tests/test_run_budgets.py
```

## Phase Exit Criteria

A cooperating external agent can hold a durable, policy-bounded run session. The system detects expiry, contention, dirty state, out-of-scope changes, failed checks, and unsafe commit conditions before declaring success or creating a commit.
