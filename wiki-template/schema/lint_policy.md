# Lint Policy

The linter checks wiki health and writes reports. It may repair unambiguous metadata only when the correction is certain.

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

