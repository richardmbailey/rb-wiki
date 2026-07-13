# Phase 6: Doctor, Migrations, Documentation Sync, and Release Qualification

## Phase Goal

Make v0.2 adoptable by existing subject wikis, prevent toolkit/template/skill drift, and qualify the release through migration fixtures, sustained-run simulations, full regression testing, and final architecture review.

## Scope

- Wiki health/compatibility doctor.
- Versioned migration planning and application policy.
- Local override protection.
- Canonical-spec/template/skill synchronisation.
- Setup-script and distribution updates.
- End-to-end unattended-operation qualification.
- Release documentation and residual-risk statement.

## Non-scope

- Cross-host or multi-writer support.
- Automatic semantic migration of arbitrary local policy.
- Adding advanced retrieval backends.
- Claiming adversarial security against tools that bypass the run controller.

## Dependencies

- Phases 1–5 fully verified and reviewed.

## Task Checklist

- [v] Finalise manifest version fields for template, profile, tools, policies, reports, migrations, and enabled capabilities.
- [v] Implement `tools/wiki_doctor.py` as a read-only inspection command with human and `--json` output.
- [v] Diagnose missing dependencies, unsupported versions, absent policies, dirty governance files, stale locks, incomplete runs, incomplete ingest states, provenance errors, unavailable capabilities, report backlog, and local overrides.
- [v] Define a versioned migration registry with preconditions, postconditions, reversible/mechanical classification, and idempotency keys.
- [v] Implement `tools/wiki_migrate.py --dry-run` to emit exact files, fields, commands, risks, approvals, and expected validation without mutation.
- [v] Implement the v0.2 migration output model as a machine-readable plan plus generated patch for explicit reviewed application; do not add direct-apply behavior in v0.2.
- [v] Ensure migrations never mutate `sources/raw/` and never overwrite manifest-declared local overrides.
- [v] Add v0.1-to-v0.2 migrations for manifest/policy files, lifecycle defaults, report directories, ignore rules, and tool copies.
- [v] Detect ambiguous/local semantic changes and route them to manual review rather than guessing.
- [v] Document canonical ownership with `wiki-template/` as the source for standalone runtime tools/contracts/wiki-local operations docs, and add deterministic sync/build only for unavoidable copied design/skill references.
- [v] Add a drift test that fails when canonical docs/contracts/tools differ from distributed copies unexpectedly.
- [v] Update `new_wiki.py` to create a fully versioned v0.2 wiki with conservative policy and no active authority by default; when the user explicitly opts into automation, generate a time-bounded `scheduled-propose` grant but never an autonomous-apply grant.
- [v] Make `new_wiki.py` build and validate in a temporary sibling directory, atomically rename it to the requested destination only after success, and leave/report a clearly named diagnostic staging directory plus cleanup/retry instructions on failure.
- [v] Update root README, template README/AGENTS, system instructions, schemas, prompts, and all four skills to match implemented behavior.
- [v] Remove or generalise remaining subject-specific upstream examples; retain domain-policy guidance using neutral examples.
- [v] Add clean, dirty, locally overridden, incomplete-ingest, and policy-diverged v0.1 migration fixtures.
- [v] Run accelerated sustained-operation simulations with acquire/propose/ingest/maintain schedules, injected overlap, failures, restarts, and report retention.
- [v] Measure tracked path growth and verify routine no-op/all-pass operation remains bounded.
- [v] Run the full test suite, setup a fresh wiki, ingest text and PDF fixtures, run every supported lane/mode, and validate all generated records.
- [v] Perform a complete implementation diff review for safety regressions, hidden fallbacks, architecture drift, missing tests, and documentation overclaims.
- [v] Fix actionable review findings and rerun focused plus full regression checks.
- [v] Publish a v0.2 upgrade guide, operational runbook, capability matrix, trust-model statement, and known limitations.
- [v] Record deferred cross-host/multi-worktree coordination as an explicit post-v0.2 roadmap item.

## Verification Checklist

- [v] `wiki_doctor.py` is read-only and correctly diagnoses every migration fixture.
- [v] Migration dry-run produces no filesystem changes and accurately predicts the applied diff.
- [v] After explicitly applying a generated migration patch to a fixture, the next dry-run is a no-op and local overrides/raw evidence remain unchanged.
- [v] A fresh v0.2 wiki is structurally valid and safely refuses scheduled/autonomous mutation until an explicit grant exists.
- [v] Injected setup failure leaves no requested destination and provides an inspectable diagnostic staging path; successful setup publishes one complete destination atomically.
- [v] Explicit automation setup can create a bounded `scheduled-propose` grant; no default/template path authorises autonomous substantive apply.
- [v] Canonical/distributed drift tests pass.
- [v] Accelerated sustained runs recover from overlap, interruption, and restart without duplicate sources or unbounded tracked reports.
- [v] Fresh setup, text ingest, PDF ingest, query, graph/index, quick/full lint, provenance, run protocol, and migration regression tests pass.
- [v] Documentation and capabilities describe only implemented, verified behavior.
- [v] Final review has no unresolved blocking findings; accepted residual risks are documented.

## Tests To Add Or Run

```text
tests/test_wiki_doctor.py
tests/test_migration_dry_run.py
tests/test_migration_patch_output.py
tests/test_migration_v01_to_v02.py
tests/test_migration_local_overrides.py
tests/test_distribution_sync.py
tests/test_new_wiki_v02.py
tests/test_new_wiki_atomic_setup.py
tests/test_sustained_operations.py
tests/test_full_v02_workflow.py
full unittest discovery suite
all template validation commands
```

## Phase Exit Criteria

RB Wiki v0.2 can create a new conservative wiki, diagnose and safely migrate representative v0.1 wikis, sustain unattended single-writer workflows under injected failures, and accurately document its capabilities, trust boundary, and remaining limitations.
