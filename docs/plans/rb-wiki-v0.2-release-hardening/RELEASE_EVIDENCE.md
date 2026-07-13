# RB Wiki v0.2 release-hardening evidence

Date: 2026-07-13

Scope: Phases 1–5 of the release-hardening implementation plan, including the original adversarial reproductions, the persisted-contract/capability/cache audit, incremental module extraction, bounded external-agent evidence, standalone distribution, and final review.

## Final release matrix

- Template suite: 202 tests passed in 218.512 seconds in the final current-state run.
- Root release suite: 40 tests passed in 51.131 seconds.
- Focused final review sets: 28 state/recovery/evidence tests, 36 ownership/authority/cron tests, 38 lane/semantic/commit tests, 12 provenance/ingest semantic tests, and 11 doctor tests passed after their respective fixes.
- All 30 Draft 2020-12 schemas meta-validated.
- All 112 repository Python files parsed and compiled in memory without bytecode output.
- `/tmp/rb-wiki-venv/bin/python -m pip check`: no broken requirements.
- `scripts/sync_distributed.py --check`: the deliberate design copy is in sync.
- Capability snapshot validated with digest `b04403bfbc00cc8ca1b78f9341fffeed50e1e9fa4faf654e470fadcfba73c734`; unavailable BM25, vector, hybrid, and HTML extraction remain explicit rather than aliased.
- Doctor exited successfully. The implementation worktree is `attention` only because its uncommitted governance implementation is intentionally dirty; dependencies, versions/policies, filesystem boundaries, locks, run/transaction/ingest state, resolution links, provenance, capability contracts, and proposal snapshots pass.
- Global bidirectional provenance passed.
- Controller-owned quick and full lint both reported green with report writes suppressed.
- Graph cache was validated and reused at 27 nodes and 177 edges; a graph-neighbour query succeeded.
- `git diff --check` passed.
- The final review caught and fixed a rare CLI-token ambiguity: URL-safe randomness can begin with `-`, which `argparse` interpreted as an option. Generated run tokens now have a fixed `run_` prefix, with a deterministic regression covering the case.
- Human-driven and agent-driven onboarding is now explicit in both READMEs, generated setup notes, agent instructions, and canonical operations guidance. Five documented authority examples validate against the current schema and lane contracts.
- The template seed now registers the current v0.2 system instructions as active, preserves the 9 July source as superseded historical evidence, and produces 25 profile 0.2 pages in a fresh generated wiki.
- No commit, push, network model call, provider credential, or live-agent dependency was used.

## Requirement audit

| Requirement | Completion evidence |
|---|---|
| H1 Executable lane contracts | Six runtime-selected contracts own modes, actions, artifacts, checks, page scope, and closure profiles; lane and broad-grant adversarial tests pass. |
| H2 Authority and policy identity | Working-tree/base loaders and all start, finish, cron, lock, resolution, proposal, approval, manifest, and policy callers enforce requested identity/version; substitution tests pass. |
| H3 Checks and closure semantics | Checks are fully parsed before mutation, duplicates/controller impersonation fail, every failure gates closure, contention stays blocked, and terminal-state invariants pass. |
| H4 Recoverable Git closure | Prepare through reconciliation stages, durable post-CAS evidence, retained recovery lock, idempotent recovery, trailer/path/content checks, and every injected failure boundary pass. |
| H5 Scheduled orchestration | Cron owns one session/outcome, restores process flags, preserves evidence, and survives every injected post-start/terminal failure with an explained terminal or recovery record. |
| H6 Filesystem and symlink safety | Shared no-follow/root-bound primitives cover migration, policy, controller, state, cache, provenance, resolution, source, and report paths; escape/leak tests pass. |
| H7 Bidirectional provenance | Forward registry/evidence/citation checks and reverse raw/Reference enumeration reconcile globally, with explicit recovery-required treatment for valid incomplete ingest. |
| H8 Persisted contracts and invariants | All emitted versions have registered schemas; write/load consumers validate bounded structure plus run/transaction/ingest semantic invariants and explicit compatibility behavior. |
| H9 Capability and envelope honesty | Manifest/registry/controller/envelope/run/proposal/apply snapshots share an exact digest, executable preconditions are probed, and doctor reports all drift/unavailability classes. |
| H10 Routing-cache integrity | Versioned source-bound graph cache validation, atomic rebuild, read-only fallback, staleness/symlink/malformed/interruption tests, reuse checks, and latency measurement pass. |
| H11 Resolution evidence | Full commit-object IDs, ancestry, trailers, run/base/path/content evidence, and bounded acknowledgement fields are validated; fake/wrong/unrelated evidence fails. |
| H12 Incremental modularisation | Context, contracts, filesystem, authority, lane, transaction, and run-store owners are extracted; dependency tests prove acyclicity and prevent reverse/CLI imports. |
| H13 Agent observability and evals | Optional metadata/evidence references are versioned, bounded, local, source-labelled, and secret-filtered; fake-agent and sustained/fault suites require no live model. |
| H14 Documentation and distribution | Root/template docs, prompts, skills, system instructions, migration, canonical ownership, distribution sync, and clean standalone new-wiki workflows agree and pass. |

## Adversarial regression mapping

| Required reproduction | Executable evidence |
|---|---|
| Scheduled maintenance cannot use a broad grant to edit/commit substantive pages | `test_lane_runtime_enforcement.py`, especially `test_maintenance_grant_cannot_include_substantive_page_scope` and `test_forbidden_page_change_cannot_move_the_branch_at_closure` |
| Requested authority identity cannot resolve to a differently identified grant | `test_authority_identity_binding.py` covers working/base, start/finish, managed/cron, break-lock, and resolution callers |
| A failed external check cannot be masked by a later pass | `test_external_check_integrity.py::test_duplicate_check_cannot_mask_an_earlier_failure` and parser/closure failure cases |
| Lock contention remains one `blocked` result | `test_external_session_contention.py` and walking-skeleton competing-process cases |
| Every post-CAS failure records the commit and recovers without a duplicate commit | `test_post_cas_fault_injection.py` covers all pre/post stages, lost branch-stage persistence, divergence, controller recovery, and retained lock |
| Every cron exception has one explained terminal/recovery result | `test_cron_exception_safety.py` covers pre-start, post-start, environment restoration, terminalisation, and post-commit recovery; `test_cron_run_integration.py` covers normal and contention paths |
| Migration parent/root symlinks leak no external content | `test_migration_parent_symlink_safety.py` and `test_migration_path_safety.py` cover target/template operational parents, final components, broken/chained/relative/absolute roots, and marker non-disclosure |
| Orphan raw evidence and orphan/duplicate References fail | `test_provenance_reverse_reconciliation.py`, `test_provenance.py`, and `test_provenance_citation_chain.py` cover both scan directions, incomplete recovery, symlinks, and citation escapes |
| Resolution rejects fake, wrong-type, unrelated, or wrong-run commit evidence | `test_resolution_commit_validation.py` covers nonexistent IDs, blobs, trees, unrelated commits, wrong trailers, human acknowledgement, and exact managed reconciliation |
| Manifest/proposal/controller capability drift fails explicitly | `test_capabilities.py`, `test_proposal_artifacts.py`, `test_fake_agent_scenarios.py`, and `test_wiki_doctor.py::test_doctor_reports_stale_proposal_capability_snapshot` |
| Stale or unsafe graph cache is never silently used | `test_graph_cache_integrity.py` covers add/edit/delete/rename, malformed/old/symlinked caches, interrupted publication, identical reuse, and symlinked source input |
| Schema-shaped but semantically impossible run/transition state is rejected | `test_runtime_semantic_invariants.py`, ingest recovery tests, and `test_wiki_doctor.py::test_doctor_rejects_schema_shaped_but_semantically_impossible_run` |

## Phase 3 evidence

- `fs_safety.py` owns lexical relative paths, explicit roots, no-follow component checks, planned-output parent checks, and safe enumeration.
- Migration validates both roots and every bounded read immediately before use. All ordinary dry-run, local-override, patch-output, and idempotent apply tests remain green.
- Provenance accounts for every raw file and Reference page, distinguishes a validated incomplete journal as `recovery-required`, never deletes evidence, and discloses when source-filtered validation skips global reverse scans.
- Resolution validates full object IDs, Git type, ancestry, trailers, run/base/path/content evidence, actor/reason bounds, and acknowledgement classification without rewriting the original outcome.
- The cross-command path audit fixed graph-source symlink reads, recovery-state parent redirects, run/source enumeration, report enumeration, lane discovery, and doctor runtime/durable paths; each discovered case has a regression.

## Phase 4 evidence

- `test_contract_registry_completeness.py` scans production schema-version literals, and 30 schemas cover all emitted/exchanged artifact versions, including the mutation-lock contract.
- Current producers reject unknown fields and oversized data. Explicit legacy readers exist only where compatibility is supported; unsupported current-state shapes fail with recovery/doctor diagnostics.
- Run records enforce chronological timestamps, terminal/result/error/report-class/lease/check/transaction consistency. Source journals enforce a legal ordered prefix and coherent outcome/failure/next/archive state. Legitimate non-self-referential commit snapshots and repaired ingest retries have dedicated regressions.
- Manifest, registry, envelope, run, proposal, and autonomous-apply capability snapshots reconcile to the exact digest. Availability probes check Python/dependency/executable/schema/YAML/Python-source preconditions.
- Graph cache schema, policy/source digest, no-follow path validation, atomic publication, read-only in-memory fallback, and deterministic reuse are covered by the cache matrix and the measurement above.

## Phase 5 evidence

- `WikiContext`, contract, filesystem, authority, lane, Git-transaction, and run-store responsibilities have explicit roots and documented owners in `MODULE_BOUNDARIES.md`.
- The lower-layer import graph is statically proven acyclic and barred from importing `wiki_run`/`wiki_cron`. `run_lib.py` was reduced from the reviewed 687-line baseline to shared primitives and narrow compatibility names, with no reverse authority/transaction delegation. Lane-specific closure dispatch now lives in `lane_runtime.py`; `wiki_run.py` retains orchestration and CLI sequencing.
- Run-store consumers use validated session/journal/transaction/receipt/latest/durable records; cron’s emergency fallback and doctor’s diagnostics apply semantic run validation.
- Optional agent provenance is versioned, bounded to 16 KiB, local-reference-only, time-ordered, and secret-filtered. Missing values remain null. External evidence references are existing in-root regular report artifacts of at most 1 MiB and never become authority or controller evidence.
- Offline fixture: `rb-wiki-fake-agent-fixture/0.2`; randomness: none (`FIXTURE_RANDOM_SEED = None`). Fake-agent coverage includes supplied/absent/malformed/oversized/secret-like provenance, conflicting checks, exact/uncited/forbidden/over-budget/revoked/over-tier outputs, source-instruction resistance, low-confidence blocked output, interrupted handoff, proposal substitution, and successful routine/high-consequence paths.
- Sustained/fault suites cover repeated no-op bounded telemetry, acquisition/ingest/proposal/apply handoffs, lock overlap, ingest restart, Git/cron recovery, and approval expiry without live model or network access.
- Root/template READMEs, `AGENTS.md`, operations, trust, capability, upgrade/canonical-ownership docs, prompts, system instructions, and all four wiki skills describe the verified behavior. Searches outside historical notes/raw/plan material found no residual medicine/cardiology-specific policy language.
- Fresh-wiki tests prove complete copy, clean standalone Git initialization, no source `.git` or runtime state, no active grant by default, optional bounded grant creation, and healthy doctor/capability/cache/provenance behavior. Migration remains reviewed patch-only and preserves declared overrides.

## Accepted residual risks

| Residual | Owner and follow-up |
|---|---|
| The v0.2 coordinator supports one host, one writable worktree, and one mutating writer. | Maintainer: design a repository-wide or service-backed lease/transaction protocol before enabling multiple writable worktrees or hosts. |
| Cooperating processes can bypass the controller if host filesystem permissions allow direct writes. | Deployment operator: use OS/repository permissions appropriate to the consequence of the wiki; do not describe v0.2 as a hostile-process sandbox. |
| Structural provenance proves identity/path/hash/citation reconciliation, not truth, sufficiency, or semantic support. | Human reviewer and external semantic agent: retain review/approval gates for consequential claims. |
| External check results are attributed attestations; the controller reruns only its deterministic checks. | Operator/agent integrator: run the named external check and attach bounded durable evidence before reporting pass. |
| Stable primitives and imported error/contract names remain in `run_lib.py` for copied-wiki compatibility. | Maintainer: remove only through a future versioned compatibility change; no authority, lane, transaction, or persistence implementation is duplicated there. |

No original adversarial finding remains without implementation and regression evidence, and no unresolved release blocker was found in the final review.
