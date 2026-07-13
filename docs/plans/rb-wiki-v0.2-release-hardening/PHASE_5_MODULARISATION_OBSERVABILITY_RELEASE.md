# Phase 5: Modularisation, Observability, and Release Qualification

## Phase Goal

Finish the incremental controller boundary cleanup, add bounded external-agent provenance and evaluation evidence, synchronise every distributed interface, and qualify the hardened release against both the ordinary and adversarial matrices.

## Scope

- Completion of test-protected module extractions begun in earlier phases.
- Explicit dependency direction and root-scoped context use.
- Optional bounded agent/runtime/trace provenance.
- Structured evidence references for external attestations.
- Fake-agent evaluations and sustained-operation recovery scenarios.
- Documentation, skills, template distribution, setup, migration, and release qualification.

## Non-scope

- Adopting or hosting an LLM-agent framework.
- Persisting full prompts, secrets, unrestricted tool logs, or model chain-of-thought.
- Adding provider routing, retrieval backends, remote tracing infrastructure, or multi-host scheduling.
- Further feature development unrelated to the hardening review.

## Dependencies

- All Phase 1–4 tasks implemented and independently verified.
- Stable contract, filesystem, authority, lane, transaction, run-store, capability, and cache boundaries.
- Existing distribution sync and new-wiki end-to-end fixtures.

## Task Checklist

- [v] Inventory remaining responsibilities and imports in `wiki_run.py`, `run_lib.py`, `wiki_cron.py`, `ingest.py`, `wiki_migrate.py`, and `wiki_lib.py` after Phases 1–4.
- [v] Define and test an explicit dependency direction: context and filesystem safety at the base; contracts above them; authority/lane/run-store/Git transaction as siblings with narrow interfaces; CLI orchestration at the top.
- [v] Migrate all production callers from module-level mutable `ROOT` assumptions to an explicit `WikiContext` or root parameter while preserving CLI defaults.
- [v] Complete `tools/contracts.py` ownership of schema discovery, bounded parsing, structural validation, identity/version binding, and semantic invariant dispatch.
- [v] Complete `tools/fs_safety.py` ownership of lexical path and no-symlink boundary checks.
- [v] Complete `tools/authority.py` ownership of working/base manifest, policy, grant, and consequence/domain precedence loading.
- [v] Complete `tools/lane_runtime.py` ownership of lane selection, action/output/check/substantive-edit rules, and lane-specific closure dispatch.
- [v] Complete `tools/git_transaction.py` ownership of temporary-index preparation, commit/CAS/recovery evidence, and reconciliation.
- [v] Complete `tools/run_store.py` ownership of atomic session, journal, latest, durable report, receipt, retention, and reload validation.
- [v] Reduce `wiki_run.py` to CLI parsing, high-level orchestration, and explicit calls into the extracted boundaries.
- [v] Reduce or remove `run_lib.py` compatibility exports after all internal callers and tests use canonical modules; do not leave duplicated implementations.
- [v] Add import-boundary tests or a lightweight static dependency check that prevents lower-level modules from importing CLI orchestration.
- [v] Preserve every public CLI command, documented exit meaning, schema version rule, and standalone copied-wiki behavior unless an earlier safety decision explicitly changes it.
- [v] Add characterization tests before each remaining move and run focused tests after each caller migration rather than combining all moves into one diff.
- [v] Define optional bounded external-agent provenance fields: agent label, runtime name/version, provider/model label when voluntarily supplied, prompt/policy digest, trace reference, started/finished timing, and aggregate tool-call summary.
- [v] Add a versioned agent-provenance/check-evidence schema or bounded definitions in the relevant run/artifact contracts.
- [v] Distinguish controller-executed evidence from external-attestation evidence and permit references to local durable artifacts without embedding arbitrary content.
- [v] Validate URI/identifier syntax and strict lengths; redact or reject run tokens, credentials, secret-like values, full prompts, and unrestricted tool arguments.
- [v] Ensure missing optional observability metadata never fabricates values and is reported as unavailable/not supplied rather than inferred.
- [v] Add fake-agent scenarios for valid metadata, absent metadata, malformed trace references, oversized evidence, secret leakage attempts, conflicting checks, low-confidence/blocked semantic output, and interrupted handoff.
- [v] Add sustained-operation scenarios covering repeated no-op runs, bounded telemetry, restart after recoverable Git/cron/ingest failures, proposal/apply handoff, and high-consequence approval expiry.
- [v] Record deterministic fixture/version information needed to reproduce fake-agent evaluations; do not require live provider credentials or network calls.
- [v] Update `wiki-template/AGENTS.md`, template/root README, agent operations, trust model, upgrade guide, capability matrix, schemas, prompts, system instructions, and all four wiki skills to match verified behavior.
- [v] Generalise any residual medical/cardiology terminology to the agreed high-consequence language while preserving subject-neutral policy semantics.
- [v] Extend canonical ownership and distribution-sync rules for new modules, schemas, docs, prompts, and any deliberate copies.
- [v] Verify new-wiki setup copies all required files, excludes runtime state and source repository metadata, initialises a clean standalone Git repository, and passes doctor/capability/cache/provenance checks.
- [v] Verify migration dry-run understands every new versioned file/contract and preserves declared local overrides without automatic apply.
- [v] Run the complete adversarial matrix from the top-level plan on disposable repositories and retain concise reproducible evidence in phase notes.
- [v] Run the complete release command matrix, schema meta-validation, Python parse/compile checks, dependency health, distribution sync, and diff hygiene.
- [v] Perform a final architecture and diff review for bugs, regression, duplicated policy, hidden fallbacks, unvalidated state, documentation drift, secret exposure, and unbounded telemetry.
- [v] Fix every release-blocking or in-scope actionable finding, rerun focused and full checks, and repeat review when fixes are material.
- [v] Record accepted residual risks explicitly; do not mark the release verified while any original review finding lacks implementation and test evidence.

## Verification Checklist

- [v] Every task is implemented `[x]` before verification begins.
- [v] Module responsibilities and dependency direction match the target architecture without circular imports or duplicate compatibility logic.
- [v] `wiki_run.py` and `run_lib.py` are materially narrower by ownership, and every moved behavior has characterization/regression coverage.
- [v] All public workflows work in the canonical template and a freshly generated standalone wiki.
- [v] Optional agent provenance is bounded, schema-valid, source-labelled, and free of tokens/secrets/full prompt content.
- [v] External attestations cannot become controller-executed evidence or implicit authority.
- [v] Fake-agent and sustained-operation evaluations cover success, blocked, failure, approval, recovery, and malformed-output paths without live model access.
- [v] Every original adversarial reproduction now fails safely or enters the intended explicit recovery path.
- [v] Root/template documentation, skills, prompts, schemas, migration, and distribution copies describe the same behavior.
- [v] Full template/root suites, all new tests, schema meta-validation, capability/doctor/provenance/lint checks, distribution sync, new-wiki workflow, migration regression, Python checks, dependency health, and `git diff --check` pass.
- [v] Final review has no unresolved release blocker; any nonblocking residual risk has an owner, rationale, and follow-up.
- [v] All completed tasks are independently marked `[v]` only after the recorded checks pass.

## Verification Evidence

- The final 202-test template suite and current 36-test root release suite passed after the review-and-fix cycle, including fresh-wiki setup, migration, doctor, sustained-operation, fake-agent, and adversarial workflows.
- Static boundary tests prove the declared lower-layer graph is acyclic, prevent lower layers from importing CLI orchestration, and prevent `run_lib.py` from delegating back into extracted owners.
- `run_lib.py` is reduced from the reviewed 687-line baseline to 453 shared/compatibility lines with no authority or transaction implementation. Lane closure dispatch is owned by `lane_runtime.py`; `wiki_run.py` retains high-level orchestration and CLI sequencing.
- Optional agent provenance and evidence references are structurally validated, bounded, secret-filtered, source-labelled, and covered for present, absent, malformed, oversized, low-confidence, conflicting, and interrupted cases without a live model.
- Documentation/distribution checks pass, fresh generated wikis are clean and operational, and searches outside historical source/plan material found no medicine- or cardiology-specific policy terminology.
- The final architecture/diff review found and fixed one rare leading-hyphen run-token CLI ambiguity. A deterministic regression now forces that case; all focused and full checks passed afterward.
- Accepted constraints and owners are recorded in [`RELEASE_EVIDENCE.md`](RELEASE_EVIDENCE.md); no original adversarial finding or release blocker remains unresolved.

## Tests To Add Or Run

```text
wiki-template/tests/test_module_boundaries.py
wiki-template/tests/test_context_root_isolation.py
wiki-template/tests/test_agent_provenance_contract.py
wiki-template/tests/test_external_check_evidence.py
wiki-template/tests/test_fake_agent_scenarios.py
wiki-template/tests/test_run_session_protocol.py
wiki-template/tests/test_high_consequence_two_run.py
wiki-template/tests/test_report_retention_classes.py
tests/test_distribution_sync.py
tests/test_new_wiki_v02.py
tests/test_full_v02_workflow.py
tests/test_migration_v01_to_v02.py
tests/test_sustained_operations.py
tests/test_wiki_doctor.py
```

## Phase Exit Criteria

The hardened wiki is a coherent standalone toolkit whose safety rules come from validated contracts, whose irreversible work is recoverable, whose evidence and capabilities reconcile, and whose external-agent interactions are attributable without framework coupling or secret leakage. Every original review finding is closed by executable evidence and the final release matrix is green.
