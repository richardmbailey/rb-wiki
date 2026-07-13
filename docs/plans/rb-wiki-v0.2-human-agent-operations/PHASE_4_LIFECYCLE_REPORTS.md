# Phase 4: Lifecycle-Aware Lint, Reports, and Capability Honesty

## Phase Goal

Make structural health, evidence maturity, check execution, and available tooling explicit enough that agents can select work accurately and growing wikis do not remain permanently Yellow for expected intermediate states.

## Scope

- Orthogonal lifecycle metadata under profile 0.2.
- Complete deterministic provenance chain through ordinary-page `sources` fields.
- Typed lint outcomes, severities, and dispositions.
- Grace-period-aware Reference integration checks.
- Honest semantic-check and search capability reporting.
- Structured reports, latest state, and retention classes.
- Source-format capability consistency.

## Non-scope

- Performing semantic staleness, contradiction, or quality assessment without an agent.
- Implementing BM25, vector search, or embeddings.
- Domain-specific evidence hierarchies.
- Automatic deletion of durable audit reports.

## Dependencies

- Phase 3 recoverable ingest states and provenance foundation verified.

## Task Checklist

- [v] Define profile 0.2 lifecycle fields and domain-neutral allowed values, preserving canonical ownership: registry/journal owns ingest/access; Reference frontmatter owns integration/assessment/review.
- [v] Keep ordinary page `status` semantics unchanged and document the boundary between page status and workflow state.
- [v] Add a versioned page-frontmatter JSON Schema and migrate frontmatter reading to the safe YAML layer, normalise explicitly allowed scalar types, reject unsafe tags/malformed structures, and avoid reserialising unchanged pages.
- [v] Update frontmatter validation to apply profile-version-aware requirements while continuing to read profile 0.1 pages permissively.
- [v] Add integration/assessment/review metadata to newly generated Reference pages and migration defaults for existing complete References; do not duplicate source-owned ingest/access truth unless the mirror is explicitly validated.
- [v] Extend provenance validation so every ordinary-page `sources` path resolves to a Reference that reconciles to one valid registry/raw record.
- [v] Detect duplicate source IDs, duplicate hashes with conflicting identities, shared raw paths, mismatched source types, and citations to non-Reference pages.
- [v] Harden local Markdown-link resolution so relative/absolute wiki links cannot traverse or resolve outside `wiki/`, including through symlinks.
- [v] Introduce a typed lint check result with `outcome`, `severity`, `disposition`, `check_id`, affected paths/source IDs, evidence, and recommended action.
- [v] Require every lint section to use the typed result and validate against the report contract.
- [v] Represent unimplemented semantic checks as `not_run` with `agent-required`, never `pass`.
- [v] Add a seven-day default Reference integration grace period with policy overrides and priority-aware escalation.
- [v] Treat newly validated unintegrated References inside the grace period as informational.
- [v] Escalate overdue, high-priority, or high-consequence unintegrated References according to policy.
- [v] Distinguish ordinary-page orphans from expected newly ingested Reference states.
- [v] Replace hard-coded full-lint editorial messages with explicit capability/check records.
- [v] Make `query.py bm25`, `vector`, and `hybrid` return an unavailable-capability diagnostic unless their actual adapters exist; retain lexical `search` as implemented.
- [v] Reconcile `SOURCE_TYPES_BY_SUFFIX`, ingest-supported formats, manifest capabilities, and documentation.
- [v] Mark HTML ingestion unavailable in v0.2 and reject it before registration/preservation unless a future explicit preservation-only authority is used; align registry, capabilities, and documentation.
- [v] Finalise canonical JSON report validation and deterministic Markdown rendering.
- [v] Implement report classes: ephemeral telemetry, durable mutation, durable failure/recovery, durable approval, and durable governance.
- [v] Keep ephemeral attempt telemetry under ignored `.wiki_state/runs/` and promote policy-defined durable records into `reports/runs/`.
- [v] Maintain `.wiki_state/latest.json` for every attempt and `reports/latest.json` only for durable/material state, including current blockers, overdue actions, and capability snapshot.
- [v] Add explicit pruning for completed ephemeral attempts older than 30 days; never prune active/incomplete state or durable records, and provide a dry-run listing.
- [v] Update README, schemas, prompts, and maintenance skill to consume typed results and prioritise by outcome/severity/disposition.
- [v] Add tests for profile compatibility, lifecycle queues, grace periods, provenance chains, capability errors, report validation, and retention classification.

## Verification Checklist

- [v] Profile 0.1 pages remain readable and profile 0.2 producer pages validate strictly.
- [v] Complex quoted scalars, dates, lists, malformed YAML, and unsafe tags behave predictably without bulk page churn.
- [v] A newly validated Reference inside its grace period does not cause a Yellow overall health result by itself.
- [v] An overdue unintegrated Reference escalates predictably with affected source/path data.
- [v] An ordinary synthesis orphan remains a meaningful warning.
- [v] Every deterministic citation chain mismatch is detected.
- [v] Semantic checks without agent evidence report `not_run`, never `pass`.
- [v] Search commands never claim unavailable backends.
- [v] HTML/source-format behavior is consistent across registry, ingest, capabilities, and docs.
- [v] All run and lint JSON records validate and render reproducibly to Markdown.
- [v] Routine all-pass telemetry does not create unbounded tracked files.
- [v] Phase completion review finds no blocking compatibility, provenance, severity, capability, or retention gaps; fixes are applied and checks rerun.

## Tests To Add Or Run

```text
tests/test_profile_02_lifecycle.py
tests/test_profile_01_compatibility.py
tests/test_frontmatter_yaml_contract.py
tests/test_provenance_citation_chain.py
tests/test_link_path_safety.py
tests/test_lint_result_contract.py
tests/test_lint_grace_periods.py
tests/test_semantic_check_outcomes.py
tests/test_search_capabilities.py
tests/test_source_format_capabilities.py
tests/test_structured_reports.py
tests/test_report_retention_classes.py
```

## Phase Exit Criteria

Agents can distinguish broken structure from healthy intermediate work, select actionable queues from lifecycle state, trust capability and lint results, and consume validated JSON reports without interpreting ambiguous Markdown or accumulating unlimited tracked telemetry.
