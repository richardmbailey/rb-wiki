#!/usr/bin/env python3
"""Shared expected-error types for RB Wiki runtime modules."""

from __future__ import annotations


class RunError(RuntimeError):
    """Base class for an expected run-controller error."""


class CommittedRecoveryRequired(RunError):
    """The branch moved, but local controller bookkeeping is incomplete."""

    def __init__(self, message: str, commit_hash: str, tree_hash: str, stage: str) -> None:
        super().__init__(message)
        self.commit_hash = commit_hash
        self.tree_hash = tree_hash
        self.stage = stage


class DependencyError(RunError):
    """A required runtime dependency is unavailable."""


class ContractError(RunError):
    """Policy or record data does not satisfy its declared contract."""
