#!/usr/bin/env python3
"""Identity-bound authority and operational-policy loading for RB Wiki."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from contracts import bind_identity, load_yaml_contract, load_yaml_text
from errors import ContractError
from run_lib import ROOT, git_show, parse_utc, validate_safe_paths
from wiki_context import WikiContext


def _validate_policy_binding(manifest: dict[str, Any], policy: dict[str, Any], source: str) -> None:
    bind_identity(policy, "policy_id", manifest["agent_policy_id"], source)


def load_runtime_policy(root: Path = ROOT) -> tuple[dict[str, Any], dict[str, Any]]:
    context = WikiContext(root)
    manifest = load_yaml_contract(context.root / "wiki-manifest.yml", "wiki-manifest", context.root)
    policy = load_yaml_contract(context.root / "schema" / "agent_policy.yml", "agent-policy", context.root)
    _validate_policy_binding(manifest, policy, "schema/agent_policy.yml")
    return manifest, policy


def _validate_authority_id(authority_id: str) -> None:
    if not authority_id or any(
        character not in "abcdefghijklmnopqrstuvwxyz0123456789-" for character in authority_id
    ):
        raise ContractError("authority ID must use lowercase letters, digits, and hyphens")


def _validate_authority_paths(authority: dict[str, Any]) -> None:
    validate_safe_paths(authority["input_roots"], "input root")
    validate_safe_paths(authority["writable_paths"], "writable")


def load_authority(authority_id: str, root: Path = ROOT) -> dict[str, Any]:
    _validate_authority_id(authority_id)
    context = WikiContext(root)
    path = context.authorities_dir / f"{authority_id}.yml"
    authority = load_yaml_contract(path, "authority-grant", context.root)
    if authority["authority_id"] != authority_id:
        raise ContractError("authority filename and authority_id do not match")
    _validate_authority_paths(authority)
    return authority


def load_base_policy(
    base: str, authority_id: str, root: Path = ROOT
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    _validate_authority_id(authority_id)
    context = WikiContext(root)
    manifest = load_yaml_text(
        git_show(base, "wiki-manifest.yml", context.root),
        "wiki-manifest",
        "base wiki-manifest.yml",
        context.root,
    )
    policy = load_yaml_text(
        git_show(base, "schema/agent_policy.yml", context.root),
        "agent-policy",
        "base schema/agent_policy.yml",
        context.root,
    )
    _validate_policy_binding(manifest, policy, "base schema/agent_policy.yml")
    relative = f"schema/authorities/{authority_id}.yml"
    authority = load_yaml_text(
        git_show(base, relative, context.root),
        "authority-grant",
        f"base {relative}",
        context.root,
    )
    if authority["authority_id"] != authority_id:
        raise ContractError("base authority filename and authority_id do not match")
    _validate_authority_paths(authority)
    return manifest, policy, authority


def validate_authority(
    authority: dict[str, Any],
    policy: dict[str, Any],
    lane: str,
    mode: str,
    now: datetime | None = None,
) -> None:
    """Validate global grant constraints; lane-specific decisions belong to lane_runtime."""
    current = now or datetime.now(timezone.utc)
    if not authority["enabled"]:
        raise ContractError(f"authority {authority['authority_id']} is disabled")
    if mode not in policy["permitted_modes"] or mode not in authority["modes"]:
        raise ContractError(f"mode {mode} is not authorised")
    if lane not in authority["lanes"]:
        raise ContractError(f"lane {lane} is not authorised")
    issued = parse_utc(authority["issued_at"])
    expires = parse_utc(authority["expires_at"])
    if expires <= issued:
        raise ContractError("authority expires_at must be later than issued_at")
    if current < issued or current >= expires:
        raise ContractError(f"authority {authority['authority_id']} is outside its validity window")
    if authority["revoked_at"] is not None and parse_utc(authority["revoked_at"]) <= current:
        raise ContractError(f"authority {authority['authority_id']} is revoked")
    budgets = authority["budgets"]
    if budgets["max_runtime_seconds"] > policy["limits"]["max_runtime_seconds"]:
        raise ContractError("authority runtime exceeds the global policy limit")
    if budgets["max_changed_paths"] > policy["limits"]["max_changed_files"]:
        raise ContractError("authority changed-path budget exceeds the global policy limit")
    if budgets["max_acquired_sources"] > policy["limits"]["max_acquired_sources"]:
        raise ContractError("authority source budget exceeds the global policy limit")
    if authority["commit_policy"] not in policy["permitted_commit_policies"]:
        raise ContractError("authority commit policy is not globally permitted")
    if authority["commit_policy"] == "scoped-auto" and authority["commit_identity"] is None:
        raise ContractError("scoped-auto authority requires an explicit commit identity")
