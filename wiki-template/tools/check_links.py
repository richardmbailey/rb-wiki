#!/usr/bin/env python3
"""Check Markdown links in wiki pages."""

from __future__ import annotations

import sys

from wiki_lib import (
    OBSIDIAN_RE,
    extract_markdown_links,
    iter_markdown_pages,
    read_text,
    resolve_wiki_link,
    root_relative,
    split_link_target,
    wiki_relative,
)


def main() -> int:
    errors: list[str] = []
    warnings: list[str] = []
    checked_links = 0

    for path in iter_markdown_pages(include_reserved=True):
        text = read_text(path)
        label = wiki_relative(path)
        if OBSIDIAN_RE.search(text):
            warnings.append(f"{label}: contains Obsidian-style wikilinks")
        for raw_target in extract_markdown_links(text):
            target = split_link_target(raw_target)
            if not target:
                continue
            resolved = resolve_wiki_link(path, raw_target)
            if resolved is None:
                continue
            checked_links += 1
            if not resolved.exists():
                errors.append(f"{label}: broken link `{target}` -> {root_relative(resolved)}")

    if errors:
        print("FAIL: link check failed")
        for error in errors:
            print(f"- {error}")
        return 1

    if warnings:
        print(f"WARN: checked {checked_links} local Markdown links")
        for warning in warnings:
            print(f"- {warning}")
        return 0

    print(f"PASS: checked {checked_links} local Markdown links")
    return 0


if __name__ == "__main__":
    sys.exit(main())

