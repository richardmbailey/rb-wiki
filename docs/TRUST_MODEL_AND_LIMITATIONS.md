# Trust model, residual risks, and known limitations

RB Wiki v0.2 coordinates cooperating agents and tools. It does not sandbox or defeat a process that ignores the controller and writes directly to the repository. Git snapshots, exact path/content reconciliation, locks, authority, contracts, and durable reports make compliant behavior inspectable and fail closed at closure; host-level permissions remain the enforcement layer against non-cooperating software.

Accepted v0.2 limitations:

- Mutation is supported on one host with one writable worktree. Cross-host and multiple-writer coordination are deferred.
- A stale lease is diagnostic; it never automatically breaks a lock. Recovery requires explicit audited governance authority and process-liveness checks.
- `scoped-auto` commits locally and never pushes. Repository hooks are intentionally bypassed by `commit-tree`; controller validation is therefore mandatory.
- Scoped commits use a local transaction journal around commit creation, branch compare-and-swap, index refresh, receipt publication, session reconciliation, and lock release. Once the branch moves, failures retain the lock and expose the exact commit as `committed-recovery-required`; recovery verifies Git and content evidence and never creates another commit.
- Structural provenance proves identity/path/hash/citation reconciliation, not truth, sufficiency, or semantic claim support.
- Provenance reconciliation is bidirectional and no-follow: registered artifacts must exist and every discovered raw file/Reference must be uniquely registered or explicitly tied to an incomplete recovery journal. Extra evidence is reported and never deleted automatically.
- Semantic work is performed by an external agent; no provider, model router, or adversarial prompt-injection sandbox ships in the toolkit. Source content is treated as untrusted data in every lane.
- Checks supplied to external-session `finish` are optional cooperating-agent attestations. The controller records and gates on them, but quick lint, scope, provenance, payload, approval, budget, and Git checks run independently under controller ownership. External agents cannot report those controller-owned checks as passed.
- Controller-owned `--quick --no-report` lint is read-only. Constrained apply cannot rebuild routing artifacts; normal quick lint and scheduled deterministic maintenance own index/graph regeneration.
- The scheduled apply entrypoint is deterministic code, not an LLM workflow: it selects one base-committed candidate, validates final-page frontmatter and target history before mutation, and writes only exact payload/semantic artifacts before controller closure.
- Optional agent/runtime/model/trace attribution is bounded, voluntarily supplied metadata. It is not inferred, does not grant authority, and rejects tokens, credentials, full prompts, unrestricted arguments, and remote trace payloads.
- High-consequence approval validates exact payload, role, scope, policy, and time. Free-text approval conditions are review evidence, not automatically interpreted policy.
- Runtime state is local and ignored by Git. Durable material records are tracked, but active sessions and post-commit transaction recovery do not survive cloning without copying `.wiki_state/`.
- Migration is read-only and patch-generating. The human maintainer owns review, backup, external patch application, and resolution of ambiguous local policy.
- Migration rejects symlinked roots or any symlink component beneath the declared source/target boundary before reading it; diagnostics do not echo unsafe external content.
- Advanced retrieval backends and automatic semantic lint are not implemented.
- Capability snapshots are exact and digest-bound; manifest claims that are unknown or unavailable are release-blocking diagnostics. Auxiliary input formats are not presented as top-level workflows.
- Graph routing caches are treated as derived, untrusted data until their schema and complete source-manifest digest validate. Read-only callers fall back to an in-memory graph rather than silently using stale bytes.
- Report retention prunes only old terminal ephemeral journals when explicitly applied; durable audit records are not deleted automatically.

Post-v0.2 roadmap: design a repository-wide or service-backed lease/transaction model for cross-host and multiple-writable-worktree mutation before enabling either topology.
