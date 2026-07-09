#!/usr/bin/env python3
"""Check OKF reserved files under reserved-file rules."""

from __future__ import annotations

import sys

from wiki_lib import LOCAL_PROFILE, WIKI_DIR, parse_frontmatter


def main() -> int:
    errors: list[str] = []
    warnings: list[str] = []

    index = WIKI_DIR / "index.md"
    log = WIKI_DIR / "log.md"
    if not index.exists():
        errors.append("wiki/index.md is missing")
    else:
        frontmatter, _body, parse_error = parse_frontmatter(index)
        if parse_error:
            warnings.append("wiki/index.md has no optional frontmatter or malformed frontmatter")
        else:
            profile = frontmatter.get("profile")
            if profile and profile != LOCAL_PROFILE:
                errors.append(f"wiki/index.md has unexpected profile `{profile}`")

    if not log.exists():
        errors.append("wiki/log.md is missing")

    if errors:
        print("FAIL: reserved file check failed")
        for error in errors:
            print(f"- {error}")
        return 1

    if warnings:
        print("WARN: reserved files exist with warnings")
        for warning in warnings:
            print(f"- {warning}")
        return 0

    print("PASS: reserved files exist and reserved-file rules are respected")
    return 0


if __name__ == "__main__":
    sys.exit(main())

