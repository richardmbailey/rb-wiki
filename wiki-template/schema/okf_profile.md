# OKF Profile

This wiki is an OKF-compatible Markdown bundle. Consumers read legacy `llm-wiki-profile/0.1` pages permissively; strict new producer pages use `llm-wiki-profile/0.2`.

## Baseline OKF Rules

- Knowledge pages are Markdown files with YAML frontmatter.
- `wiki/index.md` and `wiki/log.md` are reserved files.
- Standard Markdown links are canonical.
- Consumers should tolerate incomplete external OKF bundles.

## Local Producer Rules

- Ordinary pages must include the full local frontmatter schema from [page schema](page_schema.yml).
- Important claims must cite reference pages.
- Raw evidence must be preserved under `sources/raw/`.
- Reference pages in `wiki/references/` connect raw evidence to the wiki graph.
- Deterministic checks must be run after substantive edits.
- Page `status` describes content publication state. Profile 0.2 review, priority, consequence, integration, and assessment fields describe workflow state and do not replace it.
