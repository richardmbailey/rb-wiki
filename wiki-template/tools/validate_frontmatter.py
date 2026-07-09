#!/usr/bin/env python3
"""Validate local-profile frontmatter for ordinary wiki pages."""

from __future__ import annotations

import sys
from pathlib import Path

from wiki_lib import (
    ALLOWED_CONFIDENCE,
    ALLOWED_STATUSES,
    ALLOWED_TYPES,
    DATE_RE,
    LOCAL_PROFILE,
    REQUIRED_FIELDS,
    TIMESTAMP_RE,
    WIKI_DIR,
    iter_markdown_pages,
    parse_frontmatter,
    wiki_relative,
)


def validate_page(path: Path) -> list[str]:
    errors: list[str] = []
    frontmatter, _body, parse_error = parse_frontmatter(path)
    label = wiki_relative(path)
    if parse_error:
        return [f"{label}: {parse_error}"]

    for field in REQUIRED_FIELDS:
        if field not in frontmatter:
            errors.append(f"{label}: missing required field `{field}`")

    page_type = frontmatter.get("type")
    if page_type and page_type not in ALLOWED_TYPES:
        errors.append(f"{label}: invalid type `{page_type}`")

    status = frontmatter.get("status")
    if status and status not in ALLOWED_STATUSES:
        errors.append(f"{label}: invalid status `{status}`")

    confidence = frontmatter.get("confidence")
    if confidence and confidence not in ALLOWED_CONFIDENCE:
        errors.append(f"{label}: invalid confidence `{confidence}`")

    profile = frontmatter.get("profile")
    if profile and profile != LOCAL_PROFILE:
        errors.append(f"{label}: invalid profile `{profile}`")

    timestamp = frontmatter.get("timestamp")
    if timestamp and not TIMESTAMP_RE.match(str(timestamp)):
        errors.append(f"{label}: timestamp must be YYYY-MM-DDTHH:MM:SSZ")

    created = frontmatter.get("created")
    if created and not DATE_RE.match(str(created)):
        errors.append(f"{label}: created must be YYYY-MM-DD")

    tags = frontmatter.get("tags")
    if "tags" in frontmatter and not isinstance(tags, list):
        errors.append(f"{label}: tags must be a list")

    sources = frontmatter.get("sources")
    if "sources" in frontmatter and not isinstance(sources, list):
        errors.append(f"{label}: sources must be a list")

    return errors


def main() -> int:
    if not WIKI_DIR.exists():
        print("FAIL: wiki/ directory is missing")
        return 1

    all_errors: list[str] = []
    pages = iter_markdown_pages(include_reserved=False)
    for path in pages:
        all_errors.extend(validate_page(path))

    if all_errors:
        print("FAIL: frontmatter validation failed")
        for error in all_errors:
            print(f"- {error}")
        return 1

    print(f"PASS: validated frontmatter for {len(pages)} ordinary wiki pages")
    return 0


if __name__ == "__main__":
    sys.exit(main())

