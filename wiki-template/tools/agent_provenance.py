"""Bounded, optional provenance for cooperating external agents."""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path, PurePosixPath
from typing import Any

from contracts import validate_contract
from errors import ContractError

SECRET_PATTERN = re.compile(r"(?i)(token|password|secret|api[_-]?key|bearer\s+[a-z0-9._-]+)")
LOCAL_EVIDENCE_PATTERN = re.compile(r"^reports/[A-Za-z0-9._/-]{1,232}$")
MAX_EVIDENCE_BYTES = 1024 * 1024


def validate_check_evidence_reference(value: str, root: Path | None = None) -> str:
    """Validate a bounded reference to a local durable artifact without embedding its content."""
    if LOCAL_EVIDENCE_PATTERN.fullmatch(value) is None:
        raise ContractError("external check evidence must be a bounded local reports/ path")
    path = PurePosixPath(value)
    if any(part in {"", ".", ".."} for part in path.parts) or SECRET_PATTERN.search(value):
        raise ContractError("external check evidence reference is unsafe")
    if root is None:
        return value
    from fs_safety import safe_path

    evidence = safe_path(root, value)
    if not evidence.is_file() or evidence.stat().st_size > MAX_EVIDENCE_BYTES:
        raise ContractError("external check evidence must be a regular local artifact no larger than 1 MiB")
    return value


def validate_agent_provenance(value: dict[str, Any] | None, root: Path) -> dict[str, Any] | None:
    if value is None:
        return None
    validate_contract(value, "agent-provenance", root)
    serialized = json.dumps(value, sort_keys=True)
    if SECRET_PATTERN.search(serialized):
        raise ContractError("agent provenance must not contain tokens, credentials, or secret-like values")
    if len(serialized.encode("utf-8")) > 16_384:
        raise ContractError("agent provenance exceeds the 16 KiB bounded metadata limit")
    trace = value["trace_reference"]
    if trace is not None:
        trace_path = PurePosixPath(trace)
        if any(part in {"", ".", ".."} for part in trace_path.parts) or SECRET_PATTERN.search(trace):
            raise ContractError("agent trace reference is unsafe")
    if value["started_at"] and value["finished_at"]:
        started = datetime.fromisoformat(value["started_at"].replace("Z", "+00:00"))
        finished = datetime.fromisoformat(value["finished_at"].replace("Z", "+00:00"))
        if finished < started:
            raise ContractError("agent provenance finish time precedes start time")
    return value
