#!/usr/bin/env python3
"""Detect simple duplicate candidates in wiki pages."""

from __future__ import annotations

import sys
from collections import defaultdict

from wiki_lib import body_word_count, iter_markdown_pages, parse_frontmatter, wiki_relative


def main() -> int:
    duplicate_notes: list[str] = []
    by_slug: dict[str, list[str]] = defaultdict(list)
    by_title: dict[str, list[str]] = defaultdict(list)
    by_description: dict[str, list[str]] = defaultdict(list)

    for path in iter_markdown_pages(include_reserved=False):
        fm, body, error = parse_frontmatter(path)
        if error:
            continue
        label = wiki_relative(path)
        by_slug[path.stem].append(label)
        title = str(fm.get("title", "")).strip().lower()
        description = str(fm.get("description", "")).strip().lower()
        if title:
            by_title[title].append(label)
        if description and body_word_count(body) > 20:
            by_description[description].append(label)

    for name, bucket in [("slug", by_slug), ("title", by_title), ("description", by_description)]:
        for key, paths in sorted(bucket.items()):
            if len(paths) > 1:
                duplicate_notes.append(f"duplicate {name} `{key}`: {', '.join(paths)}")

    if duplicate_notes:
        print("WARN: duplicate candidates found")
        for note in duplicate_notes:
            print(f"- {note}")
        return 0

    print("PASS: no duplicate slugs, titles, or descriptions found")
    return 0


if __name__ == "__main__":
    sys.exit(main())

