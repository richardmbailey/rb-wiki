#!/usr/bin/env python3
"""Check Markdown links in wiki pages."""

from __future__ import annotations

import sys

from wiki_lib import (
    OBSIDIAN_RE,
    WIKI_DIR,
    extract_markdown_links,
    iter_markdown_pages,
    read_text,
    resolve_wiki_link,
    root_relative,
    split_link_target,
)


def main() -> int:
    errors: list[str] = []
    warnings: list[str] = []
    checked_links = 0

    for path in iter_markdown_pages(include_reserved=True):
        label = "/" + path.relative_to(WIKI_DIR).as_posix()
        if path.is_symlink() or not path.resolve().is_relative_to(WIKI_DIR.resolve()):
            errors.append(f"{label}: unsafe page path resolves outside wiki/")
            continue
        text = read_text(path)
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
            if not resolved.is_relative_to(WIKI_DIR.resolve()):
                errors.append(f"{label}: unsafe link escapes wiki/: `{target}`")
                continue
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
