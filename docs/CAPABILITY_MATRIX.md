# RB Wiki v0.2 capability matrix

| Capability | v0.2 status | Boundary |
|---|---|---|
| Safe manifest/policy/frontmatter parsing | Available | PyYAML and jsonschema are required; no fallback parser for operational contracts. |
| Single-writer managed runs | Available | One host and one writable Git worktree only. |
| External agent sessions | Available | Cooperative agents must follow start/heartbeat/finish and the returned envelope; optional agent-specific `--check` values are recorded attestations, while quick lint and the other controller-owned closure checks run independently. |
| Bounded agent provenance | Available | Optional labels/runtime/model/digests/local trace references are schema-bound and secret-filtered; they never grant authority. |
| Recoverable text/Markdown/PDF ingest | Available | PDF extraction may remain `raw-only`; raw evidence is preserved. |
| HTML ingest | Unavailable | Explicit preservation-only authority can preserve it without claiming extraction. |
| Provenance/citation reconciliation | Available | Structural reconciliation only; it does not judge whether a claim is semantically supported. |
| Typed quick/full lint | Available | Semantic staleness/coverage/contradiction checks are `not_run` until an agent supplies evidence. |
| Lexical search | Available | Implemented by `query.py search`. |
| Source-bound graph cache | Available | Version and complete source-manifest digest are validated; stale/unsafe read-only caches are bypassed in memory. |
| BM25/vector/hybrid search | Unavailable | Commands return unavailable-capability diagnostics; no lexical alias. |
| Artifact-driven semantic proposal/apply | Available | `wiki_cron.py apply` selects at most one eligible committed proposal, preflights exact final pages, and delegates commit/recovery to the existing controller; no LLM provider or model router is included. |
| High-consequence two-run approval | Available | Approval must be separate, committed, role/scope/time/policy valid, and digest-bound. |
| Domain policy adapter | Available | May tighten but never weaken core invariants. |
| Doctor and migration dry-run | Available | Doctor never executes target-wiki code; migration rejects unsafe/symlinked or oversized inputs, emits a reviewed patch, and has no direct apply behavior. |
| Cross-host/multiple-writer coordination | Deferred | Post-v0.2 roadmap item. |

`python3 tools/capabilities.py --json` is the runtime source of truth for optional/environment-dependent details. Its exact registry is digest-bound into run and proposal artifacts. Lifecycle metadata remains a contract feature, not a separately executable top-level capability.
