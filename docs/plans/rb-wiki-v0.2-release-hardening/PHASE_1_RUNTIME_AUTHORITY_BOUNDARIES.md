# Phase 1: Runtime Contract and Authority Walking Skeleton

## Phase Goal

Make one complete external-agent session fail closed from start through finish using executable lane contracts, clean-base authority identity binding, unambiguous checks, and correct blocked-state handling.

## Scope

- Characterization and regression tests for confirmed lane, authority, duplicate-check, and contention failures.
- Runtime loading and enforcement of versioned lane contracts.
- Central working/base authority identity validation.
- External-check parsing and closure semantics.
- Correct blocked-state persistence and single terminalisation.
- Initial extraction of contract, authority, and lane responsibilities only where required by this vertical slice.

## Non-scope

- Post-CAS commit recovery.
- Cron-wide exception cleanup.
- Migration/provenance reverse scanning.
- Capability/cache redesign.
- Broad module decomposition.

## Dependencies

- Current v0.2 implementation and its 154-test baseline.
- Existing lane, authority, policy, run-record, and check-result schemas.
- Disposable Git-wiki fixture and external-session fake-agent harness.

## Task Checklist

- [v] Capture the current full-suite baseline and preserve the eight adversarial reproduction commands/fixtures as review evidence.
- [v] Add a failing integration test proving scheduled maintenance with a broad grant cannot edit or auto-commit an ordinary wiki page when its lane contract has `substantive_wiki_edits: false`.
- [v] Add negative tests for substantive edits in every lane/mode combination whose contract forbids them, including ingest and acquire grants with accidentally broad writable paths.
- [v] Add a failing test for a committed authority file whose requested filename ID differs from its internal `authority_id` in manual-assist start.
- [v] Extend authority-identity tests across managed run, external start/finish, cron, break-lock, and resolution callers.
- [v] Add a failing test showing `CHECK=fail` followed by the same `CHECK=pass` cannot close successfully.
- [v] Add malformed, empty, duplicate, excessive-count, and controller-ID collision tests for external checks.
- [v] Add a failing external-session contention test that asserts journal/latest state and result remain `blocked`, with the expected transient-contention exit meaning.
- [v] Introduce a root-scoped context object sufficient for contract and authority loading in disposable/test wikis without module-level root substitution.
- [v] Introduce or consolidate `tools/contracts.py` for size-bounded YAML/JSON loading, JSON Schema validation, requested identity/version binding, and semantic validator dispatch.
- [v] Implement deterministic lane-contract discovery keyed by `controller_lane` and reject zero, duplicate, incompatible-version, or ambiguous matches.
- [v] Validate every shipped lane contract at runtime and test missing, malformed, unknown-field, symlinked, and duplicate-controller-lane files.
- [v] Store the selected lane contract identity and deterministic digest in the session/run record so finish cannot silently select a different contract.
- [v] Enforce lane `allowed_modes`, `actions_by_mode`, `required_checks`, `produces`, and `substantive_wiki_edits` at start and closure.
- [v] Define exact controller-owned output-class mappings for lane `produces` values and reject grants or final paths that exceed them except for explicitly declared shared audit/runtime outputs.
- [v] Preserve the stricter existing exact proposal/apply payload rules and route them through lane-runtime specialisation rather than weakening them.
- [v] Introduce `tools/authority.py` or an equivalently cohesive module for working-tree and base-commit policy/grant loading.
- [v] Require the requested authority ID to equal the loaded grant's `authority_id` before any returned authority is used.
- [v] Bind manifest/policy identifiers and versions to requested/expected values wherever the path or run record implies an identity.
- [v] Ensure scheduled/autonomous working-tree policy cannot expand clean-base authority and manual-assist records cannot label one committed grant as another.
- [v] Parse and validate all external checks before transitioning the run to validating state or writing closure artifacts.
- [v] Reject duplicate check IDs, including duplicate statuses that happen to agree.
- [v] Gate on the complete validated check list and record provenance as `external-attestation` or `controller-executed`.
- [v] Prevent an external check from impersonating or replacing a controller-owned check ID.
- [v] Refactor start-session error handling so lock contention is terminalised once as `blocked`; other preflight failures remain `failed` with one coherent record.
- [v] Add state/result/timestamp assertions to focused tests even before the full semantic invariant validator arrives in Phase 4.
- [v] Update lane-contract and external-session operator documentation with executable rules and exact diagnostics.
- [v] Run a focused review for contract/runtime duplication and remove superseded hard-coded mappings rather than retaining two policy sources.

## Verification Checklist

- [v] Every task is implemented `[x]` before verification begins.
- [v] Scheduled maintenance ordinary-page edits fail closure and never move the branch, even under a broad scoped-auto grant.
- [v] All lanes enforce their selected contract's mode, action, output, required-check, and substantive-edit constraints.
- [v] Every authority caller rejects filename/internal-ID mismatch before mutation or audit displacement.
- [v] Duplicate or controller-impersonating checks are rejected and no `fail` can be masked.
- [v] Lock contention produces exactly one terminal `blocked` outcome in journal/latest state.
- [v] Existing valid manual, scheduled proposal, ingest, maintenance, and autonomous-apply workflows still pass.
- [v] Session/run artifacts contain a stable lane-contract identity/digest and distinguish check provenance.
- [v] Focused tests, full template tests, root tests, schema validation, AST/compile checks, and `git diff --check` pass.
- [v] Phase completion review finds no remaining duplicated lane/authority decision path or untested caller; fixes are applied and checks rerun.
- [v] All completed tasks are independently marked `[v]` only after the recorded checks pass.

## Verification Evidence

- 160 standalone template/runtime tests passed after the review-and-fix cycle.
- 25 root release/distribution tests passed.
- 20 Draft 2020-12 schemas meta-validated; all six executable lane contracts loaded and passed semantic validation.
- 95 Python files parsed successfully; distribution sync and `git diff --check` passed.
- Doctor and capability reporting completed read-only. Doctor reported only the expected governance-dirt warning for this uncommitted implementation worktree.
- Review fixes added fail-fast page-type enforcement, mode-specific action rejection, contract-driven closure profiles, proposal/approval/consequence-policy identity binding, and controller-output impersonation coverage. No blocking Phase 1 finding remains.

## Tests To Add Or Run

```text
wiki-template/tests/test_lane_runtime_enforcement.py
wiki-template/tests/test_authority_identity_binding.py
wiki-template/tests/test_external_check_integrity.py
wiki-template/tests/test_external_session_contention.py
wiki-template/tests/test_lane_contracts.py
wiki-template/tests/test_run_session_protocol.py
wiki-template/tests/test_scheduled_propose_enforcement.py
wiki-template/tests/test_lock_leases.py
wiki-template/tests/test_fake_agent_scenarios.py
wiki-template/tests/test_cron_run_integration.py
```

## Phase Exit Criteria

A cooperating external agent can start and close every supported lane only when the clean-base authority and selected versioned lane contract agree. Broad grants cannot override lane safety, contradictory checks cannot be hidden, and contention remains an explicit blocked outcome.
