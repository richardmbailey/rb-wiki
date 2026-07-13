# Lint Policy

The linter checks wiki health and writes canonical JSON plus deterministic Markdown reports. Every section uses the typed check-result contract: outcome, severity, disposition, affected paths/source IDs, evidence, and recommended action. It may repair unambiguous metadata only when the correction is certain.

The linter must not delete files, merge duplicates, rename pages, rewrite substantive content, resolve contradictions, or change schemas without explicit approval.

Quick lint should check:

- reserved files;
- frontmatter;
- OKF compatibility;
- broken links;
- word counts;
- duplicate slugs and titles;
- source coverage;
- graph orphans.

Full lint should also review:

- staleness;
- coverage gaps;
- overview drift;
- contradiction candidates;
- stale high-degree pages.

Semantic checks without an implemented deterministic adapter must be `not_run` with `agent-required`; they must never be reported as passing. A newly validated unintegrated Reference is informational during the policy grace period. Overdue, high-priority, and high-consequence References are escalated into explicit queues. Ordinary synthesis orphans remain warnings; newly ingested Reference pages are not treated as ordinary orphans.
