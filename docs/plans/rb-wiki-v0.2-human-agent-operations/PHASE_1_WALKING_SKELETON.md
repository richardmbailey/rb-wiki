# Phase 1: Safe Scheduled-Propose Walking Skeleton

## Phase Goal

Deliver the thinnest runnable end-to-end safety path: a `scheduled-propose` deterministic maintenance run loads committed policy, reports truthful capabilities, atomically acquires a per-wiki lock, performs the authoritative Git preflight under that lock, runs bounded maintenance, validates its changes, writes a structured run result, reconciles changed paths, and releases the lock.

## Scope

- Manifest and minimal operational policy.
- Explicit YAML dependency and validated policy loading.
- Versioned JSON Schema contracts, canonical JSON run record, and Markdown rendering.
- Truthful capability command.
- Minimal atomic one-writer lock.
- Clean-base Git preflight for scheduled runs.
- Managed deterministic maintenance invocation.
- Temporary versus durable report separation.

## Non-scope

- External-agent session protocol and heartbeats.
- Automatic commits.
- Recoverable ingest refactor.
- Semantic synthesis or editorial lint.
- Cross-host/worktree locking.
- Applied migrations.

## Dependencies

- Existing Python CLI tools and `unittest` suite.
- Git available for scheduled mutation mode.
- Python 3.10+, PyYAML 6.x, and `jsonschema` 4.x.

## Task Checklist

- [v] Add a distributable `wiki-template/pyproject.toml` declaring Python 3.10+, PyYAML 6.x, and `jsonschema` 4.x, with reproducible test/setup instructions; add root contributor setup that exercises the same declared dependency set.
- [v] Add a fail-fast dependency check that explains how to install missing required packages and never falls back to the handwritten YAML parser.
- [v] Add `wiki-template/wiki-manifest.yml` with template/profile/tool/policy/report versions and enabled capabilities.
- [v] Add minimal `wiki-template/schema/agent_policy.yml` defining conservative permitted modes/limits, an empty `schema/authorities/` grant directory, and a disabled example grant; do not ship an active authority.
- [v] Add versioned JSON Schema contracts under `wiki-template/schema/contracts/` for the manifest, agent policy, authority grant, run record, and check result.
- [v] Implement size-bounded `yaml.safe_load` plus JSON Schema validation in `tools/run_lib.py`, rejecting unsafe tags, unknown producer fields, invalid enums, invalid paths, and schema-version mismatches before constructing internal dataclasses.
- [v] Implement atomic JSON writing, stable UTC timestamps, run-ID generation, and deterministic JSON serialisation helpers.
- [v] Implement `tools/capabilities.py --json` from an explicit capability registry rather than command names or documentation claims.
- [v] Report lexical search as implemented and BM25/vector/hybrid as unavailable aliases unless real backends are detected.
- [v] Add `.wiki_state/` to the template ignore rules, document it as non-cache recoverable runtime state, and ensure cache cleanup does not touch it.
- [v] Implement a per-wiki mutation lock using atomic creation of `.wiki_state/mutation.lock/`; store run, process, host, lane, mode, and acquisition metadata inside the owned lock directory.
- [v] Diagnose an owner-metadata write failure as an incomplete held lock; never interpret a lock directory without metadata as unlocked.
- [v] Acquire the mutation lock before the authoritative clean-base Git preflight for `scheduled-propose`; record base commit and initial status, then re-read and validate manifest/policy from that base while still holding the lock.
- [v] Detect additional Git worktrees for the same repository and block scheduled/autonomous mutation as unsupported in v0.2.
- [v] Implement `tools/wiki_run.py run --lane maintain --mode scheduled-propose --authority ID` as a managed wrapper around bounded deterministic quick maintenance.
- [v] Add a controller-owned output mode to subordinate build/lint tools so the walking skeleton does not create nested legacy reports or independent closure decisions.
- [v] Declare the maintenance lane's writable paths and reconcile the final changed-path set before successful closure.
- [v] Write an incrementally updated attempt journal under `.wiki_state/runs/` and atomically finalise it.
- [v] Keep no-op, all-pass, and transient pre-mutation blocked attempts under `.wiki_state/runs/`; promote mutation, post-mutation failure/recovery, manual-action, approval, and governance records into `reports/runs/<run-id>.json`.
- [v] Update `.wiki_state/latest.json` for every attempt and update tracked `reports/latest.json` only when durable/material state changes.
- [v] Ensure lock release occurs on success and handled failure; preserve diagnostics when cleanup is incomplete.
- [v] Add canonical `wiki-template/docs/AGENT_OPERATIONS.md` describing the walking-skeleton command, trust boundary, states, and failure recovery; make root documentation and skills link to it rather than creating hand-maintained copies.
- [v] Update template README and relevant skills to describe only Phase 1 capabilities and avoid claiming autonomous apply support.
- [v] Add unit tests for safe YAML/JSON Schema validation, unsafe tags, unknown fields, capability JSON, atomic record writes, and lock contention.
- [v] Add root disposable-wiki integration tests that create a time-bounded fixture grant, then exercise fresh setup, clean successful maintenance, dirty-base blocking, no-op closure, changed-path reconciliation, nested-report suppression, and lock release after failure.

## Verification Checklist

- [v] A fresh template can install declared dependencies and run the complete test suite.
- [v] `capabilities.py --json` validates as JSON and accurately identifies unavailable search backends.
- [v] A clean `scheduled-propose` maintenance run reaches a terminal state and produces a valid run record.
- [v] An unexpected dirty base blocks before lock-protected mutation.
- [v] A repository with multiple Git worktrees is diagnosed and blocked for scheduled/autonomous mutation.
- [v] Two competing mutating processes produce one lock holder and one structured `blocked` result.
- [v] An incomplete lock directory remains blocking and has an explicit recovery diagnostic.
- [v] A forced lane failure releases or clearly diagnoses the lock and preserves the attempt journal.
- [v] Changed paths outside the lane declaration prevent successful closure.
- [v] Repeated all-pass/no-op runs update stable status without unbounded tracked report creation.
- [v] Existing validators and PDF tests pass, and the newly added setup/ingest baseline regression tests preserve current behavior.
- [v] Phase completion review finds no blocking safety, documentation, or test gaps; fixes are applied and checks rerun.

## Tests To Add Or Run

Test paths below are relative to `wiki-template/`; root-level distribution/setup tests may live in a root `tests/` directory when they exercise the public starter kit rather than one copied wiki.

```text
tests/test_policy_contracts.py
tests/test_capabilities.py
tests/test_run_records.py
tests/test_run_lock.py
tests/test_unsupported_worktree_topology.py
tests/test_run_walking_skeleton.py
tests/test_report_retention.py
existing tests/test_pdf_ingest.py
```

Run all mutation-producing integration tests against temporary copied wikis and temporary Git repositories.

## Phase Exit Criteria

A cooperating scheduled agent can invoke one documented command on a clean wiki and receive an auditable, truthful, bounded result through the entire policy -> preflight -> lock -> maintenance -> validation -> report -> closure path. Contention, dirty state, unavailable capability, and failure paths are explicit and tested.
