# Wiki Template

This directory is a reusable starting point for new LLM-wikis.

To create a new wiki:

1. Prefer the public setup script:

```bash
python3 skills/rb-new-wiki/scripts/new_wiki.py \
  --template wiki-template \
  --parent .. \
  --name example-wiki \
  --title "Example Wiki" \
  --subject "example subject" \
  --tag example \
  --description "Example Wiki is a local-first LLM-wiki for example subject."
```

2. If copying manually, copy this directory to a new sibling directory named after the wiki.
3. Enter the copied directory.
4. Update `README.md`, `AGENTS.md`, `wiki/overview.md`, `wiki/log.md`, and generated index/graph outputs for the new subject.
5. Review `tools/ingest.py`, `tools/lint.py`, and schema prompts for any subject-specific wording before the first ingest.
6. Keep the schema, tools, and operating-model pages unless the new wiki has a specific reason to diverge.
7. Run:

```bash
python3 tools/lint.py --quick
```

The template intentionally includes the seed LLM-wiki design source so new wikis begin with cited operating-model pages, deterministic tooling, and a green lint baseline.
