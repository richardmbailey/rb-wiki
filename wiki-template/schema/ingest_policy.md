# Ingest Policy

The ingest flow preserves raw evidence before synthesis.

1. Place raw files in `inbox/`.
2. Compute a SHA-256 hash.
3. Copy the original file into `sources/raw/` without editing it.
4. Add or update `sources/_source_registry.yml`.
5. Create a reference page in `wiki/references/`.
6. Route through index, frontmatter, graph, and search before reading many page bodies.
7. Update wiki pages only with citations to reference pages.
8. Rebuild `wiki/index.md` and `.wiki_cache/graph.json`.
9. Run validation and quick lint.
10. Move successfully processed direct inbox files into `inbox/processed/YYYY-MM-DD/`.
11. Write an ingest report under `reports/ingest/`.

Unsupported, ambiguous, failed, encrypted, or very large inbox files stay in `inbox/` for review. The agent must not delete inbox or raw files without explicit approval.
