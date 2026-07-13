# Phase 3: Filesystem and Provenance Integrity

## Phase Goal

Make every operational path remain inside the intended wiki/template root without traversing any symlink component, and make provenance reconcile registered and unregistered artifacts in both directions.

## Scope

- Shared lexical/root/symlink safety primitives.
- Migration source/template and target path hardening.
- Bidirectional raw/registry/Reference/citation provenance.
- Recovery-aware handling of extra preserved evidence.
- Git-object and evidential validation for resolution commits.
- Negative path tests across all affected public commands.

## Non-scope

- Semantic truth or claim-support assessment.
- Deleting orphan evidence automatically.
- Applying migration patches automatically.
- Capability/cache redesign.

## Dependencies

- Phase 1 context/contract/authority boundaries.
- Phase 2 run-store and recovery-state definitions, especially incomplete ingest/commit diagnostics.
- Existing path-safety helpers, migration dry-run, source registry, and provenance validator.

## Task Checklist

- [v] Add a failing migration test with a symlinked target `tools/` parent pointing outside the wiki and assert no external marker reaches stdout, stderr, patch text, or plan JSON.
- [v] Add equivalent parent-symlink tests for template `tools/`, contracts, lanes, prompts, docs, policies, reports, manifest, registry, and legacy Reference inputs.
- [v] Add broken, chained, relative, absolute, directory, and final-component symlink cases for both migration roots.
- [v] Add failing provenance tests for an unregistered raw file, orphan Reference, duplicate Reference for one source ID, and Reference path not present in the registry.
- [v] Add provenance tests for extra artifacts explained by valid incomplete source-transition journals versus unexplained extras.
- [v] Add symlinked raw directory, nested Reference directory, individual evidence file, and ordinary-page citation escape tests.
- [v] Add failing resolution tests for nonexistent commit hashes, tree/blob object IDs, unrelated commits, and commits claiming another run trailer.
- [v] Introduce `tools/fs_safety.py` with explicit lexical relative-path validation, root containment, parent-component symlink detection, final object-type checks, and safe enumeration helpers.
- [v] Make safety helpers operate on a supplied `WikiContext`/root and never infer a boundary from a conveniently named ancestor directory.
- [v] Define behavior for missing final paths separately from unsafe parent chains so planned outputs can be validated without following links.
- [v] Replace duplicated path/symlink logic in migration, provenance, resolution, policy/report/cache access, and affected ingest/controller paths one caller at a time.
- [v] Reject a symlinked or escaped migration template root or target root before enumerating canonical files.
- [v] Validate every migration read path against its declared root immediately before reading and bound file sizes for text/YAML/JSON inputs.
- [v] Ensure migration manual-review/error output contains paths and diagnostics only, never content read through an unsafe path.
- [v] Keep migration dry-run/patch-only, deterministic, idempotent, and local-override preserving after the safety refactor.
- [v] Reverse-enumerate `sources/raw/` without following symlinked directories and map every regular file to exactly one valid registry entry.
- [v] Reverse-enumerate all wiki Reference pages without following symlinks and map every page to exactly one registry entry/path/source ID.
- [v] Preserve forward checks for source ID, digest, raw path, Reference path, type, access level, and ordinary-page citations.
- [v] Define provenance outcomes for artifacts associated with a valid incomplete ingest journal as `recovery-required`, not `PASS` and not automatic deletion.
- [v] Treat unexplained extra raw/Reference artifacts as provenance failure with an exact registration, quarantine-review, or recovery action.
- [v] Ensure source-filtered provenance validation documents whether reverse global checks are skipped or still required; do not give a misleading global `PASS`.
- [v] Use `git cat-file` or equivalent plumbing to require resolution hashes to name real commit objects.
- [v] For managed-commit resolution, verify the run trailer and reconcile expected base/path/content evidence; otherwise explicitly classify the record as a human acknowledgement.
- [v] Bound and validate resolution actor/reason/evidence fields and retain the original run outcome unchanged.
- [v] Extend doctor to surface migration-root hazards, bidirectional provenance failures, and invalid resolution links read-only.
- [v] Update upgrade, provenance, trust-model, and recovery documentation with reverse-reconciliation and no-follow guarantees.
- [v] Run a cross-command path-safety review to identify remaining direct `resolve()`, `rglob()`, `glob()`, `read_text()`, or `read_bytes()` calls on operational input paths without shared safety checks.
- [v] Fix actionable review findings and add a regression for each newly discovered unsafe caller before phase closure.

## Verification Checklist

- [v] Every task is implemented `[x]` before verification begins.
- [v] No migration source or target symlink component is followed, and no external marker content appears in any output.
- [v] Safe ordinary migration dry-runs and reviewed-patch idempotency still pass.
- [v] Every raw file and Reference page is either uniquely registered, tied to an explicit recovery journal, or reported as an error.
- [v] Missing registered artifacts and unregistered extra artifacts are both detected.
- [v] Provenance never follows symlinked directories/files and ordinary citations remain root-bounded.
- [v] Resolution rejects nonexistent, wrong-type, and unrelated commits while accepting reconciled managed commits and explicit acknowledgements.
- [v] Doctor remains read-only and reports all new integrity failures with exact next actions.
- [v] Focused tests, full suites, provenance, doctor, migration regression, schema validation, compile checks, and diff hygiene pass.
- [v] Phase completion review finds no operational path read/write outside the shared safety boundary in scope; fixes are applied and checks rerun.
- [v] All completed tasks are independently marked `[v]` only after the recorded checks pass.

## Verification Evidence

- The final 202-test template suite and current 36-test root release suite passed; the root suite includes the complete migration no-follow and reviewed-patch regression matrix.
- Bidirectional provenance validation passed globally. Reverse raw/Reference reconciliation, incomplete-ingest classification, citation containment, and no-follow behavior are covered by dedicated adversarial tests.
- Resolution tests reject nonexistent, wrong-type, unrelated, and wrong-run objects while accepting exact managed evidence and explicit human acknowledgements without changing the original outcome.
- Doctor, both lint modes, all 30 schema checks, all 112 Python parse/compile checks, distribution sync, and `git diff --check` passed.
- The path-safety review centralised the in-scope boundary rules in `fs_safety.py` and added regressions for migration roots/parents, graph inputs, runtime state, report and source enumeration, recovery paths, and operational policy reads. No unresolved Phase 3 path escape remains.
- Full command output and the adversarial mapping are retained in [`RELEASE_EVIDENCE.md`](RELEASE_EVIDENCE.md).

## Tests To Add Or Run

```text
tests/test_migration_parent_symlink_safety.py
tests/test_migration_path_safety.py
tests/test_migration_dry_run.py
tests/test_migration_v01_to_v02.py
wiki-template/tests/test_provenance_reverse_reconciliation.py
wiki-template/tests/test_provenance.py
wiki-template/tests/test_provenance_citation_chain.py
wiki-template/tests/test_resolution_commit_validation.py
wiki-template/tests/test_link_path_safety.py
wiki-template/tests/test_ingest_input_safety.py
wiki-template/tests/test_policy_contracts.py
tests/test_wiki_doctor.py
```

## Phase Exit Criteria

Migration, provenance, resolution, and shared operational reads cannot cross their declared roots through any symlink component. Provenance accounts for every raw file and Reference page without deleting evidence or hiding incomplete recovery.
