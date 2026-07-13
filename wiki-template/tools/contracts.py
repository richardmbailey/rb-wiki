#!/usr/bin/env python3
"""Root-scoped, size-bounded loading and validation for RB Wiki contracts."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from errors import ContractError, DependencyError
from wiki_context import WikiContext

MAX_STRUCTURED_BYTES = 1024 * 1024
MAX_YAML_BYTES = MAX_STRUCTURED_BYTES  # Compatibility name used by existing tools.
SemanticValidator = Callable[[Any, WikiContext], None]
_SEMANTIC_VALIDATORS: dict[str, list[SemanticValidator]] = {}


def register_semantic_validator(contract: str, validator: SemanticValidator) -> None:
    """Register a deterministic post-schema validator for one contract type."""
    validators = _SEMANTIC_VALIDATORS.setdefault(contract, [])
    if validator not in validators:
        validators.append(validator)


def _timestamp(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _validate_run_semantics(data: Any, _context: WikiContext) -> None:
    if not isinstance(data, dict):
        return
    started, updated = _timestamp(data["started_at"]), _timestamp(data["updated_at"])
    if updated < started:
        raise ContractError("run updated_at cannot precede started_at")
    if data["finished_at"] is not None:
        finished = _timestamp(data["finished_at"])
        if finished < started or finished > updated:
            raise ContractError("run finished_at must fall between start and last update")
    if (data["heartbeat_at"] is None) != (data["lease_expires_at"] is None):
        raise ContractError("run heartbeat and lease must either both be present or both be absent")
    if data["heartbeat_at"] and data["lease_expires_at"]:
        if _timestamp(data["lease_expires_at"]) < _timestamp(data["heartbeat_at"]):
            raise ContractError("run lease cannot expire before its heartbeat")
    terminal = {"completed", "blocked", "failed", "cancelled", "manual-commit-required", "approval-required"}
    if (data["state"] in terminal) != (data["finished_at"] is not None):
        raise ContractError("terminal run state and finished_at must agree")
    expected_results = {
        "blocked": "blocked", "failed": "failed", "cancelled": "cancelled",
        "manual-commit-required": "manual-commit-required", "approval-required": "approval-required",
        "committed-recovery-required": "committed-recovery-required",
    }
    if data["state"] in expected_results and data["result"] != expected_results[data["state"]]:
        raise ContractError("run state and result are inconsistent")
    if data["state"] == "completed" and data["result"] not in {"success", "no-op"}:
        raise ContractError("completed run requires success or no-op result")
    check_ids = [item["check_id"] for item in data["checks"]]
    if len(check_ids) != len(set(check_ids)):
        raise ContractError("run check IDs must be unique")
    if data["state"] == "completed" and data["error"] is not None:
        raise ContractError("completed run cannot retain an error")
    if data["state"] not in terminal | {"committed-recovery-required"} and data["result"] is not None:
        raise ContractError("non-terminal run cannot have a result")
    if data["state"] == "failed" and data["error"] is None:
        raise ContractError("failed run requires an error")
    durable = data["durable_record"]
    expected_durable = f"reports/runs/{data['run_id']}.json"
    if durable is not None and durable != expected_durable:
        raise ContractError("durable run path must bind to the run ID")
    if data["report_class"] == "ephemeral-telemetry" and durable is not None:
        raise ContractError("ephemeral run cannot point to a durable report")
    if data["report_class"] != "ephemeral-telemetry":
        if not data["material"] or durable is None:
            raise ContractError("durable report class requires material state and a durable path")
    controller_checks = {"semantic-output", "provenance", "proposal-payload", "approval-binding"}
    if any(
        item["provenance"] == "external-attestation" and item["check_id"] in controller_checks
        for item in data["checks"]
    ):
        raise ContractError("external attestation cannot claim a controller-owned check")


def _validate_source_transition_semantics(data: Any, _context: WikiContext) -> None:
    if not isinstance(data, dict):
        return
    order = ["captured", "raw-preserved", "registered", "reference-created", "validated", "inbox-archived"]
    completed = data["completed_transitions"]
    if not completed or completed[0] != "captured":
        raise ContractError("source completed_transitions must begin with captured")
    if completed != order[: len(completed)]:
        raise ContractError("source completed_transitions must be a legal ordered prefix")
    if data["state"] != (completed[-1] if completed else "captured"):
        raise ContractError("source state must match the last completed transition")
    if _timestamp(data["updated_at"]) < _timestamp(data["captured_at"]):
        raise ContractError("source updated_at cannot precede captured_at")
    expected_next = order[len(completed)] if len(completed) < len(order) else None
    last_run = data["last_run_transitions"]
    if len(last_run) != len(set(last_run)) or any(item not in completed for item in last_run):
        raise ContractError("source last_run_transitions must be unique completed transitions")
    if [order.index(item) for item in last_run] != sorted(order.index(item) for item in last_run):
        raise ContractError("source last_run_transitions must retain transition order")
    if data["outcome"] == "complete":
        if completed != order or data["processed_path"] is None or any(
            data[field] is not None for field in ("failed_transition", "error", "next_transition")
        ):
            raise ContractError("complete source transition has inconsistent terminal fields")
        if data["planned_processed_path"] != data["processed_path"]:
            raise ContractError("complete source transition must bind its planned and actual archive path")
    elif data["outcome"] == "recovery-required":
        if data["failed_transition"] is None or data["error"] is None or data["next_transition"] is None:
            raise ContractError("recovery-required source transition needs failure and next-step evidence")
        retry = expected_next or order[-1]
        if data["failed_transition"] != retry or data["next_transition"] != retry:
            raise ContractError("recovery-required source transition must identify the exact retry transition")
    else:
        if data["failed_transition"] is not None or data["error"] is not None or data["next_transition"] != expected_next:
            raise ContractError("in-progress source transition has inconsistent next-step evidence")


register_semantic_validator("run-record", _validate_run_semantics)
register_semantic_validator("source-transition", _validate_source_transition_semantics)


def require_contract_dependencies() -> tuple[Any, Any]:
    """Import structured-contract dependencies or fail with an install command."""
    try:
        import yaml
        import jsonschema
    except ImportError as exc:
        raise DependencyError(
            "required policy dependencies are missing; install them with "
            "`python3 -m pip install -e .` from the wiki base directory"
        ) from exc
    return yaml, jsonschema


def _symlink_component(path: Path, context: WikiContext) -> Path | None:
    from fs_safety import symlink_component

    return symlink_component(path, context)


def _schema(name: str, context: WikiContext) -> dict[str, Any]:
    path = context.contracts_dir / f"{name}.schema.json"
    try:
        unsafe = _symlink_component(path, context)
        if unsafe is not None:
            raise ContractError(f"contract path must not traverse a symlink: {unsafe}")
        if path.stat().st_size > MAX_STRUCTURED_BYTES:
            raise ContractError(f"contract exceeds the {MAX_STRUCTURED_BYTES}-byte limit: {path}")
        schema = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        try:
            relative = path.relative_to(context.root)
        except ValueError:
            relative = path
        raise ContractError(f"cannot load contract {relative}: {exc}") from exc
    if not isinstance(schema, dict):
        raise ContractError(f"contract schema must be a JSON object: {path}")
    return schema


def validate_contract(data: Any, contract: str, root: Path) -> None:
    context = WikiContext(root)
    _yaml, jsonschema = require_contract_dependencies()
    schema = _schema(contract, context)
    validator = jsonschema.Draft202012Validator(schema, format_checker=jsonschema.FormatChecker())
    errors = sorted(validator.iter_errors(data), key=lambda item: list(item.absolute_path))
    if errors:
        error = errors[0]
        location = ".".join(str(part) for part in error.absolute_path) or "<root>"
        raise ContractError(f"{contract} contract violation at {location}: {error.message}")
    for semantic_validator in _SEMANTIC_VALIDATORS.get(contract, []):
        semantic_validator(data, context)


def bind_identity(data: dict[str, Any], field: str, expected: str, source: str) -> None:
    actual = data.get(field)
    if actual != expected:
        raise ContractError(f"{source} {field} does not match requested identity {expected}")


def bind_schema_version(data: dict[str, Any], expected: str, source: str) -> None:
    bind_identity(data, "schema_version", expected, source)


def load_yaml_text(
    text: str,
    contract: str,
    source: str,
    root: Path,
    *,
    expected_identity: tuple[str, str] | None = None,
) -> dict[str, Any]:
    raw = text.encode("utf-8")
    if len(raw) > MAX_STRUCTURED_BYTES:
        raise ContractError(f"{source} exceeds the {MAX_STRUCTURED_BYTES}-byte YAML limit")
    yaml, _jsonschema = require_contract_dependencies()
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise ContractError(f"unsafe or invalid YAML in {source}: {exc}") from exc
    if not isinstance(data, dict):
        raise ContractError(f"{source} must contain a YAML mapping")
    validate_contract(data, contract, root)
    if expected_identity is not None:
        bind_identity(data, expected_identity[0], expected_identity[1], source)
    return data


def load_yaml_contract(
    path: Path,
    contract: str,
    root: Path,
    *,
    expected_identity: tuple[str, str] | None = None,
) -> dict[str, Any]:
    context = WikiContext(root)
    try:
        if path.is_symlink():
            raise ContractError(f"operational YAML must not be a symlink: {path}")
        unsafe = _symlink_component(path, context)
        if unsafe is not None:
            raise ContractError(f"operational YAML path must not traverse a symlink: {unsafe}")
        size = path.stat().st_size
        if size > MAX_STRUCTURED_BYTES:
            raise ContractError(f"{path} exceeds the {MAX_STRUCTURED_BYTES}-byte YAML limit")
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ContractError(f"cannot read {path}: {exc}") from exc
    return load_yaml_text(
        text,
        contract,
        str(path),
        context.root,
        expected_identity=expected_identity,
    )


def load_json_text(
    text: str,
    contract: str,
    source: str,
    root: Path,
    *,
    expected_identity: tuple[str, str] | None = None,
) -> dict[str, Any]:
    if len(text.encode("utf-8")) > MAX_STRUCTURED_BYTES:
        raise ContractError(f"{source} exceeds the {MAX_STRUCTURED_BYTES}-byte JSON limit")
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ContractError(f"invalid JSON in {source}: {exc}") from exc
    if not isinstance(data, dict):
        raise ContractError(f"{source} must contain a JSON object")
    validate_contract(data, contract, root)
    if expected_identity is not None:
        bind_identity(data, expected_identity[0], expected_identity[1], source)
    return data


def load_json_contract(
    path: Path,
    contract: str,
    root: Path,
    *,
    expected_identity: tuple[str, str] | None = None,
) -> dict[str, Any]:
    context = WikiContext(root)
    try:
        if path.is_symlink():
            raise ContractError(f"operational JSON must not be a symlink: {path}")
        unsafe = _symlink_component(path, context)
        if unsafe is not None:
            raise ContractError(f"operational JSON path must not traverse a symlink: {unsafe}")
        if path.stat().st_size > MAX_STRUCTURED_BYTES:
            raise ContractError(f"{path} exceeds the {MAX_STRUCTURED_BYTES}-byte JSON limit")
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ContractError(f"cannot read {path}: {exc}") from exc
    return load_json_text(
        text,
        contract,
        str(path),
        context.root,
        expected_identity=expected_identity,
    )
