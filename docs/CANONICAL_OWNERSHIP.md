# Canonical ownership and distribution

`wiki-template/` is the canonical source for every standalone wiki runtime tool, JSON contract, lane/policy file, prompt, and wiki-local operations document. New wikis and migration patches copy those files from a named template version; subject wikis may declare local overrides in `wiki-manifest.yml`, which migration preserves rather than overwrites.

Root-level skills are workflow entrypoints, not alternate runtime implementations. The only deliberately duplicated design reference is `llm-wiki-system-instructions.md` at `skills/rb-wiki/references/design.md`. Check it with:

```bash
python3 scripts/sync_distributed.py --check
```

Use `--write` only when intentionally publishing a reviewed canonical design update. The seed raw source under `wiki-template/sources/raw/` is historical evidence and is intentionally not synchronized or rewritten.
