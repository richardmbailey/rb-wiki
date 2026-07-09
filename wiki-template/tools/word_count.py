#!/usr/bin/env python3
"""Check ordinary wiki page body word counts."""

from __future__ import annotations

import sys

from wiki_lib import body_word_count, iter_markdown_pages, parse_frontmatter, wiki_relative

WORD_LIMIT = 1000


def main() -> int:
    warnings: list[str] = []
    pages = iter_markdown_pages(include_reserved=False)
    for path in pages:
        _frontmatter, body, parse_error = parse_frontmatter(path)
        if parse_error:
            continue
        count = body_word_count(body)
        if count > WORD_LIMIT:
            warnings.append(f"{wiki_relative(path)}: {count} words exceeds {WORD_LIMIT}")

    if warnings:
        print("WARN: oversized pages found")
        for warning in warnings:
            print(f"- {warning}")
        return 0

    print(f"PASS: {len(pages)} ordinary pages are within {WORD_LIMIT} words")
    return 0


if __name__ == "__main__":
    sys.exit(main())

