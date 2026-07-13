# Phase 4: Contracts, Capabilities, and Cache Integrity

## Phase Goal

Make every persisted/exchanged runtime artifact semantically valid, every capability declaration reconcilable, and every graph cache provably current before agents or tools rely on it.

## Scope

- Missing JSON Schema contracts and version-aware readers.
- Cross-field semantic invariants for run and ingest state.
- Capability manifest/registry/controller/proposal reconciliation.
- Exact capability snapshots in envelopes and records.
- Versioned, source-bound graph cache with stale detection.
- Doctor diagnostics and compatibility behavior.

## Non-scope

- Implementing BM25, vector, hybrid, or new semantic capabilities.
- Adding an agent provider/framework.
- Changing page semantics or performing semantic review.
- Broad final module decomposition.

## Dependencies

- Verified Phase 1 lane/authority/check contracts.
- Verified Phase 2 transaction/run-store stages.
- Verified Phase 3 filesystem-safety primitives.

## Task Checklist

- [v] Inventory every `schema_version` emitted or loaded by production tools and produce a test that fails when no registered schema/validator exists.
- [v] Add versioned JSON Schemas for ingest reports, commit receipts, runtime sessions, run envelopes, `.wiki_state/latest.json`, and tracked `reports/latest.json` as distinct contracts where their shapes differ.
- [v] Validate each artifact before atomic write and immediately after load at every consumer boundary.
- [v] Add size limits, unknown-field rejection for current producers, and explicitly version-aware compatibility readers where older data is supported.
- [v] Define semantic invariant validators in `tools/contracts.py` in addition to JSON Schema shape validation.
- [v] Enable explicit JSON Schema format checking and enforce parseable UTC timestamps plus legal chronological ordering where records carry start/update/finish/lease times.
- [v] Enforce run `state`, `result`, `finished_at`, `error`, `next_action`, `material`, `report_class`, `commit_hash`, recovery-stage, and unique check-ID/provenance consistency.
- [v] Enforce legal ordered prefixes for ingest `completed_transitions` and reconcile `state`, `outcome`, `failed_transition`, `next_transition`, error, processed path, and access level.
- [v] Add malformed-but-schema-valid fixtures for every impossible combination and assert all reload/recovery/doctor paths reject or diagnose them.
- [v] Define and register the `lifecycle-metadata` capability or remove it from the manifest, with an explicit rationale and compatibility effect.
- [v] Add deterministic manifest-to-registry reconciliation for enabled, available, optional, unavailable, auxiliary, and unknown capabilities.
- [v] Upgrade capability availability checks from file existence to relevant schema validity, dependency/version presence, executable availability, and supported runtime preconditions.
- [v] Keep auxiliary ingest-format capabilities clearly distinguished from manifest-enabled top-level workflow capabilities.
- [v] Include the exact capability snapshot and deterministic digest in external start envelopes, sessions, and run records.
- [v] Require proposal policy snapshots to contain the exact controller capability snapshot/digest rather than any object with a schema version.
- [v] At autonomous apply, compare the base-committed proposal snapshot with the active clean-base controller snapshot and fail on drift.
- [v] Add capability-snapshot compatibility behavior for pre-hardening v0.2 proposal artifacts: explicit rejection or reviewed migration, never silent acceptance.
- [v] Extend doctor to report manifest-only, registry-only, enabled-but-unavailable, dependency-blocked, proposal-snapshot-stale, and capability-contract errors.
- [v] Define a versioned graph-cache contract containing graph schema version, generation time, canonical node/edge data, and a deterministic source-manifest digest.
- [v] Define the source manifest from all Markdown routing inputs and any schema/configuration that changes graph interpretation.
- [v] Validate graph-cache path safety, JSON size/shape, version, and source digest before use.
- [v] In mutating/controller contexts, rebuild stale cache atomically and verify the rebuilt digest before publication.
- [v] In read-only contexts, either build an in-memory current graph or return an explicit stale/unavailable diagnostic; never silently use stale content.
- [v] Add tests for page addition/edit/deletion/rename, malformed JSON, symlinked cache, old schema version, interrupted cache write, and identical-source cache reuse.
- [v] Ensure routing/index guidance to agents exposes cache freshness and does not claim generated data is current when validation was not run.
- [v] Measure source-manifest and graph validation on representative fixture sizes and document any material latency tradeoff.
- [v] Update capability matrix, agent operations, schema documentation, and trust model after behavior is verified.
- [v] Review all persisted state consumers for unvalidated direct `json.loads`/YAML reads and migrate in-scope callers to contract APIs.
- [v] Fix actionable review findings, add regressions, and rerun the full contract/capability/cache matrix.

## Verification Checklist

- [v] Every task is implemented `[x]` before verification begins.
- [v] Every production `schema_version` has a registered structural and, where required, semantic validator.
- [v] Schema-valid but semantically impossible run/ingest artifacts are rejected consistently by ordinary load, recovery, and doctor paths.
- [v] Manifest, capability registry, run envelope, run record, proposal, and autonomous apply snapshots reconcile exactly.
- [v] Missing dependencies or executables make affected capabilities unavailable with explicit reasons.
- [v] Existing unavailable BM25/vector/hybrid and unsupported HTML claims remain truthful.
- [v] A stale, malformed, unsafe, or incompatible graph cache is never silently used.
- [v] Current cache reuse and safe rebuild behavior are deterministic and tested.
- [v] Fresh generated wikis validate every new contract and start with reconciled capability/cache state.
- [v] Focused tests, all suites, schema meta-validation, capabilities, doctor, query/graph tests, compile checks, and diff hygiene pass.
- [v] Phase completion review finds no unvalidated persisted/exchanged artifact or stale capability/cache claim in scope; fixes are applied and checks rerun.
- [v] All completed tasks are independently marked `[v]` only after the recorded checks pass.

## Verification Evidence

- A production-version inventory test reconciles every emitted `schema_version`; all 30 Draft 2020-12 schemas meta-validate and current records receive structural plus semantic validation at write/load boundaries.
- Dedicated invariant tests reject schema-shaped impossible run, transaction, ingest, receipt, session, and latest-snapshot states through normal load, recovery, and doctor paths.
- Manifest, controller, envelope, run, proposal, and autonomous-apply capability snapshots bind the same deterministic digest: `b04403bfbc00cc8ca1b78f9341fffeed50e1e9fa4faf654e470fadcfba73c734`.
- Capability and doctor commands passed while reporting BM25, vector, hybrid, and unsupported HTML extraction honestly unavailable; dependency/schema/source precondition failures have negative coverage.
- Graph cache tests cover source add/edit/delete/rename, malformed/old/symlinked data, interrupted publication, current reuse, and read-only fallback. Final builds reused a validated 26-node/158-edge cache twice and a graph-neighbour query succeeded.
- Full command output and contract/cache details are retained in [`RELEASE_EVIDENCE.md`](RELEASE_EVIDENCE.md).

## Tests To Add Or Run

```text
wiki-template/tests/test_contract_registry_completeness.py
wiki-template/tests/test_runtime_semantic_invariants.py
wiki-template/tests/test_commit_receipt_contract.py
wiki-template/tests/test_ingest_idempotency.py
wiki-template/tests/test_graph_cache_integrity.py
wiki-template/tests/test_capabilities.py
wiki-template/tests/test_proposal_artifacts.py
wiki-template/tests/test_fake_agent_scenarios.py
wiki-template/tests/test_run_records.py
wiki-template/tests/test_ingest_failure_recovery.py
wiki-template/tests/test_search_capabilities.py
tests/test_wiki_doctor.py
tests/test_full_v02_workflow.py
tests/test_new_wiki_v02.py
```

## Phase Exit Criteria

Agents and operators can trust that loaded runtime artifacts are both structurally and semantically valid, advertised capabilities match executable reality, proposal/apply capability snapshots are bound, and graph routing data is current or explicitly unavailable.
