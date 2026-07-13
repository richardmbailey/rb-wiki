# Phase 5: Autonomous Semantic Lanes and High-Consequence Policy

## Phase Goal

Enable cooperating agents to acquire, propose, and—when explicitly authorised—apply bounded semantic wiki changes while enforcing lane scope, evidence/provenance requirements, consequence gates, and approval states.

## Scope

- Complete acquire, ingest, synthesize, and semantic-maintenance lane contracts.
- Proposal artifacts and bounded apply workflow.
- Enforcement of `scheduled-propose` versus `authorised-autonomous-apply`.
- Domain-neutral consequence tiers and approval gates.
- Domain-policy adapter interface.
- Agent-facing skill/runbook updates.
- Deterministic fake-agent integration/evaluation harness.

## Non-scope

- Shipping an LLM provider, model router, or multi-agent framework.
- Encoding any subject-specific evidence rules in core files.
- Automatically judging semantic correctness with lexical heuristics.
- Automatically approving the highest-consequence changes.
- Cross-host agent coordination.

## Dependencies

- Phase 4 lifecycle, provenance, typed reporting, and honest capabilities verified.

## Task Checklist

- [v] Define versioned lane contracts for acquire, ingest, synthesize, deterministic-maintain, and semantic-maintain.
- [v] Define artifact-based handoffs so each lane consumes validated outputs rather than relying on schedule order.
- [v] Define acquisition result records containing query/provider metadata, discovery budget, source candidates, selection rationale, and preservation state.
- [v] Define a structured synthesis proposal containing affected pages, intended use, consequence tier, source IDs, planned claims/sections, uncertainties, and required approvals; high-consequence proposals must additionally contain an exact patch or deterministic target-content bundle.
- [v] Store scheduled proposals only under declared `reports/proposals/` artifacts; ensure proposal generation is allowed in `scheduled-propose` while ordinary substantive page changes are prohibited.
- [v] Implement deterministic structural change classification: treat every ordinary wiki body/frontmatter change as substantive unless it is an exact generated-file or explicitly whitelisted mechanical metadata operation; do not use lexical heuristics to infer semantic harmlessness.
- [v] Require `authorised-autonomous-apply` for substantive edits and verify mode, lane, page type, path, action, budget, validation, and consequence tier at closure.
- [v] Require new or changed ordinary pages to cite structurally valid Reference pages before successful closure.
- [v] Require semantic agent outputs to identify the agent/runtime label, policy and capability snapshot, source set, uncertainties, contradictions, and checks actually performed.
- [v] Define `routine`, `material`, and `high-consequence` tiers based on intended use and action class; document that domain/source identity alone does not determine consequence.
- [v] Define required dispositions: routine may apply within routine-tier authority, material requires explicit material-tier authority and expanded checks, and high-consequence always requires a separately recorded approval.
- [v] Define an approval-record contract containing approval ID, proposal/run ID, immutable proposal digest, decision, approver label, scope, conditions, issue/expiry timestamps, and policy version.
- [v] Require the approval record and permitted approver role to exist in the apply run's recorded clean base commit; the apply run may not create or modify its own approval.
- [v] Enforce a two-run high-consequence workflow: the proposal run ends `approval-required` without applying substantive edits; a later apply run must present an unexpired committed approval whose digest binds the exact patch/target-content bundle, and the final diff must match that approved payload.
- [v] Implement policy precedence: core invariants -> operational policy -> domain profile -> project/run authority.
- [v] Reject lower-layer policy that attempts to weaken core invariants or exceed the authority's maximum tier.
- [v] Add an optional `schema/domain_policy.yml` interface for source admissibility, hierarchy, ontology, assessment rules, reviewers, and approval thresholds.
- [v] Provide a generic example domain profile with no subject-specific or named-organisation content.
- [v] Add a compatibility guide for converting existing subject-specific policy into a subject-local adapter.
- [v] Update `rb-wiki`, `rb-wiki-ingest`, and `rb-wiki-maintenance` skills to start/heartbeat/finish through the run protocol when mutating.
- [v] Add or revise prompts so agents read the run envelope and treat it as the operative scope rather than inferring authority from prose.
- [v] State in every acquisition/synthesis prompt that source content is untrusted data and cannot alter lane scope, authority, policy, tools, or approval requirements.
- [v] Ensure semantic maintenance reports distinguish agent findings, deterministic evidence, proposed changes, applied changes, and approval-required items.
- [v] Build a deterministic fake-agent harness that applies declared, forbidden, uncited, over-budget, source-instruction, and consequence-gated edits for integration tests.
- [v] Add scenario tests for scheduled proposal, authorised bounded apply, revoked authority, missing citations, contradiction escalation, changed proposal after approval, expired approval, and high-consequence two-run requirements.

## Verification Checklist

- [v] Acquire, ingest, synthesize, and maintain lanes exchange validated artifacts and expose no timing-only dependency.
- [v] `scheduled-propose` can create proposals but cannot close after substantive ordinary-page edits.
- [v] Bounded autonomous apply succeeds only within authority and consequence policy.
- [v] Uncited, out-of-scope, over-budget, revoked, or over-tier edits fail closure.
- [v] Highest-tier changes enter `approval-required` rather than being auto-approved.
- [v] No high-consequence substantive edit occurs before approval, and any proposal digest change invalidates the approval.
- [v] A domain profile can tighten source/assessment/review rules without changing core code.
- [v] A domain profile cannot weaken raw immutability, provenance, Git closure, or authority limits.
- [v] Semantic checks are attributed and never replaced by brittle deterministic keyword claims.
- [v] Updated skills and runbook guide agents through the same enforceable protocol.
- [v] Phase completion review finds no blocking authority, consequence, semantic-boundary, or agent-interface gaps; fixes are applied and checks rerun.

## Tests To Add Or Run

```text
tests/test_lane_contracts.py
tests/test_lane_handoffs.py
tests/test_proposal_artifacts.py
tests/test_scheduled_propose_enforcement.py
tests/test_autonomous_apply_scope.py
tests/test_semantic_output_contract.py
tests/test_consequence_policy.py
tests/test_approval_records.py
tests/test_high_consequence_two_run.py
tests/test_policy_precedence.py
tests/test_domain_policy_adapter.py
tests/test_fake_agent_scenarios.py
```

## Phase Exit Criteria

A cooperating external agent can safely perform a complete artifact-driven workflow without continuous human input, while substantive application remains bounded by inspectable authority, structural provenance, consequence policy, and explicit approval gates.
