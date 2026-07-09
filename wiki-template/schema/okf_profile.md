# OKF Profile

This wiki is an OKF-compatible Markdown bundle with a stricter local producer profile named `llm-wiki-profile/0.1`.

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

