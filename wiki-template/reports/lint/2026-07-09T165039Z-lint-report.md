# Lint Report - 2026-07-09

# Summary

Overall health status: Green
Mode: quick

# 1. Reserved File Check

Status: Pass

```text
PASS: reserved files exist and reserved-file rules are respected
```

# 2. Schema Integrity

Status: Pass

```text
PASS: validated frontmatter for 24 ordinary wiki pages
```

# 3. Broken Links and OKF Links

Status: Pass

```text
PASS: checked 158 local Markdown links
```

# 4. Page Size

Status: Pass

```text
PASS: 24 ordinary pages are within 1000 words
```

# 5. Duplicate Detection

Status: Pass

```text
PASS: no duplicate slugs, titles, or descriptions found
```

# 6. Index Freshness

Status: Pass

```text
PASS: wrote wiki/index.md with 24 ordinary page entries
```

# 7. Graph Build

Status: Pass

```text
PASS: wrote .wiki_cache/graph.json with 26 nodes and 158 edges
```

# 8. Source Registry Integrity

Status: Pass

- Validated 1 source registry entry; no issues found.

# 9. Source Coverage

Status: Pass

- No issues found.

# 10. Orphan Check

Status: Pass

- No issues found.

# Overall Health

| Check | Status |
|---|---|
| Reserved File Check | Pass |
| Schema Integrity | Pass |
| Broken Links and OKF Links | Pass |
| Page Size | Pass |
| Duplicate Detection | Pass |
| Index Freshness | Pass |
| Graph Build | Pass |
| Source Registry Integrity | Pass |
| Source Coverage | Pass |
| Orphan Check | Pass |

# Next Steps

1. Ingest source material specific to this wiki.
2. Review pages marked `needs-review` after new sources are registered.
3. Decide whether to create recurring upkeep automations.

# Log Entry

- `2026-07-09`: Ran quick lint. Overall status: Green.
