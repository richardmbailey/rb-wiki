#!/usr/bin/env python3
"""Check or refresh the one deliberate copied design reference."""

from __future__ import annotations

import argparse
import hashlib
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COPIES = {
    ROOT / "skills" / "rb-wiki" / "references" / "design.md": ROOT / "llm-wiki-system-instructions.md",
}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check unavoidable RB Wiki distributed copies")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--write", action="store_true")
    args = parser.parse_args(argv)
    mismatches: list[str] = []
    for destination, source in COPIES.items():
        if args.write:
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, destination)
        if not destination.is_file() or digest(destination) != digest(source):
            mismatches.append(f"{destination.relative_to(ROOT)} != {source.relative_to(ROOT)}")
    if mismatches:
        for mismatch in mismatches:
            print(f"FAIL: {mismatch}")
        return 1
    print(f"PASS: {len(COPIES)} distributed copy is in sync")
    return 0


if __name__ == "__main__":
    sys.exit(main())
