# Phase 3: Recoverable Ingestion and Provenance Foundation

## Phase Goal

Refactor source ingestion into an idempotent, journalled transition system that preserves raw evidence first, safely resumes after interruption, and proves registry/raw/Reference consistency before archiving inbox material.

## Scope

- Source transition journal and idempotency.
- Atomic registry/reference/report writes.
- Crash-safe resume and explicit failure state.
- PDF extraction failure handling.
- Initial deterministic provenance reconciliation.
- Inbox/cron integration through the run controller.

## Non-scope

- Semantic source assessment or synthesis.
- Ordinary-page citation-chain validation beyond structural source resolution.
- HTML ingestion unless explicitly added after capability reconciliation.
- Acquisition provider integrations.

## Dependencies

- Phase 2 run session, lock, authority, Git, and closure behavior verified.

## Task Checklist

- [v] Define the source lifecycle and allowed transitions: `captured`, `raw-preserved`, `registered`, `reference-created`, `validated`, `inbox-archived`, plus explicit blocked/failed metadata.
- [v] Define `captured` precisely as a locked snapshot of direct inbox path, size, SHA-256 digest, and proposed stable source ID; define per-source transition records keyed by that digest and linked to the parent run ID.
- [v] Add atomic write-and-replace helpers for registry, Reference pages, and transition journals.
- [v] Preserve raw data by copying to a same-filesystem temporary file, fsyncing when supported, verifying its digest, and atomically creating a non-existing final raw path; fail rather than overwrite.
- [v] Recheck the captured input identity before/after copy and fail to `recovery-required` if the inbox file changes during preservation.
- [v] Separate raw preservation from later fallible extraction and synthesis steps; never roll raw preservation back.
- [v] Make source ID assignment stable across retries and recover existing incomplete records by hash.
- [v] Add a versioned source-registry JSON Schema and migrate `source_registry.py` to the safe YAML/JSON Schema layer, with deterministic writes and round-trip tests for existing v0.1 registry data.
- [v] Refactor `source_registry.py` to reconcile incomplete entries rather than creating suffix IDs for interrupted repeats.
- [v] Make registry `ingest_state` and `access_level` the canonical source-side lifecycle fields and reconcile them with the transition journal.
- [v] Refactor `ingest.py` into small transition functions with explicit preconditions, postconditions, and idempotent results.
- [v] Add a deterministic resume command for a source or run and report the next incomplete transition.
- [v] Ensure an existing valid transition is a no-op rather than a duplicate write.
- [v] Record PDF derivative extraction independently from raw preservation; extraction/no-text failure must still create a structurally valid Reference with source-side `access_level: raw-only`, preserve the PDF, and remain pending semantic integration.
- [v] Archive a structurally complete PDF inbox copy after provenance validation even when text extraction failed; the Reference/report must expose the access limitation and required next action.
- [v] Reject unsupported source types before preservation by default and leave them in the active inbox with a capability-aware report; allow preservation-only handling only through an explicit authority action and lifecycle state.
- [v] Reject non-direct inbox files, directories, symlinks, path escapes, oversized files, excessive file counts, and source-controlled values that exceed time/resource policy before expensive work.
- [v] Move an inbox file only after complete structural validation and record its processed destination.
- [v] Implement `tools/provenance.py validate` for raw file existence/hash, registry uniqueness, Reference existence/type, source ID, raw path, reference path, hash, and source-type reconciliation.
- [v] Make ingest validation call provenance checks before processed-inbox movement.
- [v] Reconcile `sources/raw/` as append-only: allow additions registered by the current run and reject modification, deletion, or rename of every pre-existing raw path.
- [v] Route `wiki_cron.py inbox` through `wiki_run.py` and the per-wiki mutation lock.
- [v] Remove duplicate lint/report invocations from nested ingest/cron flows so one run owns one validation/report sequence.
- [v] Add deterministic fault-injection hooks at each transition, disabled in production commands.
- [v] Add compatibility handling for existing complete v0.1 registry entries and detection/reporting of incomplete ones; leave versioned migration orchestration to Phase 6.
- [v] Update ingest reports to include transition states, resumed work, idempotent no-ops, artifacts, validation, and next action.
- [v] Add unit and integration tests for every transition, retry, mismatch, failure, and recovery path.

## Verification Checklist

- [v] Re-ingesting identical content produces one raw file, registry entry, and Reference page.
- [v] Failure after each transition leaves a valid journal and exact resume point.
- [v] Resume completes without changing the stable source ID or duplicating artifacts.
- [v] Raw evidence remains present and hash-valid after every simulated failure.
- [v] Modification, deletion, or rename of pre-existing raw evidence blocks closure; a valid newly registered raw addition is allowed.
- [v] Missing raw/reference artifacts are restored only when the registered hash and policy permit it.
- [v] Hash, source ID, raw path, reference path, and source type mismatches are detected.
- [v] PDF extraction failure preserves the PDF and produces an explicit review state without falsely completing integration.
- [v] Changing-input, symlink, traversal, oversized-input, unsafe-filename, and resource-budget fixtures fail closed without modifying paths outside declared scope.
- [v] Inbox material moves exactly once and only after structural validation.
- [v] Concurrent inbox runs cannot both mutate source state.
- [v] Cron produces one coherent run/report chain rather than nested report piles.
- [v] Phase completion review finds no blocking evidence-loss, idempotency, recovery, or provenance gaps; fixes are applied and checks rerun.

## Tests To Add Or Run

```text
tests/test_source_lifecycle.py
tests/test_ingest_idempotency.py
tests/test_ingest_failure_recovery.py
tests/test_registry_reconciliation.py
tests/test_registry_yaml_contract.py
tests/test_provenance.py
tests/test_raw_append_only.py
tests/test_inbox_archive.py
tests/test_ingest_input_safety.py
tests/test_ingest_resource_budgets.py
tests/test_cron_run_integration.py
expanded tests/test_pdf_ingest.py
```

## Phase Exit Criteria

Any interrupted supported-source ingest can be diagnosed and resumed without evidence loss or duplicate identity. Inbox archival is gated on verified raw/registry/Reference consistency, and all mutating ingest paths run under the controller and one-writer lock.
