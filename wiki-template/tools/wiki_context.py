#!/usr/bin/env python3
"""Explicit root-scoped paths for reusable RB Wiki tooling."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class WikiContext:
    """Canonical paths for one wiki root without mutable module-level substitution."""

    root: Path

    def __post_init__(self) -> None:
        object.__setattr__(self, "root", self.root.absolute())

    @property
    def contracts_dir(self) -> Path:
        return self.root / "schema" / "contracts"

    @property
    def lanes_dir(self) -> Path:
        return self.root / "schema" / "lanes"

    @property
    def authorities_dir(self) -> Path:
        return self.root / "schema" / "authorities"

    @property
    def state_dir(self) -> Path:
        return self.root / ".wiki_state"


def context_for(root: Path) -> WikiContext:
    return WikiContext(root)

