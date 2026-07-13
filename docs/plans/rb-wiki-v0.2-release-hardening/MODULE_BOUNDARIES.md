# RB Wiki v0.2 module boundaries

This inventory records the post-hardening ownership boundaries used for release review. Command modules may compose lower layers; lower layers must not import `wiki_run.py` or `wiki_cron.py`.

## Dependency direction

1. `errors.py` and `wiki_context.py` define shared values and a root-scoped context.
2. `fs_safety.py` enforces lexical containment and no-follow filesystem access.
3. `contracts.py` performs bounded parsing, schema discovery, format checking, identity binding, and semantic-validator dispatch.
4. `authority.py`, `lane_runtime.py`, `run_store.py`, and `git_transaction.py` own bounded policy, lane, persistence, and recoverable-commit responsibilities.
5. `run_lib.py` retains shared Git/time/locking and atomic-write primitives plus narrow error/contract re-exports; it does not delegate back into or own authority, lane, Git-transaction, or run-persistence decisions.
6. `wiki_run.py` and `wiki_cron.py` are orchestration/CLI layers. They select workflows and call the owning modules; lower layers are statically prevented from importing them.

The lower-layer import graph is acyclic. `run_lib.py` no longer delegates into the owning authority or Git-transaction modules; production callers use those canonical modules directly. Stable shared primitives and legacy error/contract import names remain for copied-wiki compatibility.

## Responsibility inventory

| Module | Release responsibility | Explicitly delegated responsibility |
|---|---|---|
| `wiki_run.py` | CLI parsing, session/run orchestration, closure sequencing, operator commands | schemas, authority, lane rules, persisted writes, Git transaction mechanics |
| `run_lib.py` | timestamps, run IDs, lock ownership, shared Git/status primitives, compatibility façades | structured parsing, authority decisions, lane policy, transaction journals |
| `wiki_cron.py` | one-session scheduled lifecycle and exception-safe terminalisation | ingest mechanics and session persistence |
| `ingest.py` | resumable source-transition workflow and source artifact construction | controller authority/closure and generic contracts |
| `wiki_migrate.py` | deterministic patch-only migration planning | path safety and contract parsing |
| `wiki_lib.py` | Markdown/frontmatter/link/graph domain helpers | generic structured contract loading and filesystem boundary rules |
| `contracts.py` | bounded YAML/JSON loading, schemas, format and semantic validation | workflow policy decisions |
| `fs_safety.py` | lexical root containment, parent/final symlink rejection, safe enumeration | workflow-specific path permissions |
| `authority.py` | identity-bound working/base policy and grant loading | lane-specific permissions |
| `lane_runtime.py` | contract selection, action/artifact/check/page/substantive-edit enforcement | grant identity and Git closure |
| `run_store.py` | validated atomic journals, sessions, latest snapshots, durable reports, receipts, transactions, retention | run-state orchestration |
| `git_transaction.py` | prepare/commit/CAS/recovery evidence and reconciliation mechanics | terminal state and operator policy |

## Enforced invariants

- Every reusable operation receives its wiki root or constructs `WikiContext` from an explicit root; module constants remain CLI defaults only.
- Persistence validates current contracts before writes and after reloads.
- Path access is root-bounded and no-follow.
- Lower layers cannot import CLI orchestration; `tests/test_module_boundaries.py` enforces this.
- `tests/test_context_root_isolation.py` proves two roots can load different contracts without module-global substitution.

## Accepted compatibility residual

`run_lib.py` retains stable shared primitives and imported error/contract names already used by copied wikis. It contains no reverse delegation or duplicated authority/transaction implementation. Removing those remaining names is owned by the maintainer and requires a future versioned compatibility decision; it is not required for v0.2 safety.
