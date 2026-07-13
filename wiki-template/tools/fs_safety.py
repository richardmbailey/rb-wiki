"""No-follow filesystem boundaries for operational wiki paths."""

from __future__ import annotations

import os
from pathlib import Path, PurePosixPath

from errors import ContractError, RunError
from wiki_context import WikiContext


def lexical_relative(value: str) -> PurePosixPath:
    path = PurePosixPath(value)
    if value in {"", "."} or path.is_absolute() or ".." in path.parts or "\\" in value:
        raise ContractError(f"unsafe relative path: {value}")
    return path


def checked_root(root: Path | WikiContext) -> Path:
    path = root.root if isinstance(root, WikiContext) else root
    path = path.absolute()
    if path.is_symlink() or not path.is_dir():
        raise ContractError(f"operational root must be a real directory: {path}")
    return path


def symlink_component(path: Path, root: Path | WikiContext, *, include_final: bool = True) -> Path | None:
    boundary = checked_root(root)
    candidate = path.absolute()
    try:
        relative = candidate.relative_to(boundary)
    except ValueError as exc:
        raise ContractError(f"path escapes operational root: {candidate}") from exc
    current = boundary
    parts = relative.parts if include_final else relative.parts[:-1]
    for part in parts:
        current = current / part
        if current.is_symlink():
            return current
    return None


def safe_path(
    root: Path | WikiContext,
    relative: str,
    *,
    allow_missing: bool = False,
    final_type: str = "file",
) -> Path:
    boundary = checked_root(root)
    lexical = lexical_relative(relative)
    path = boundary.joinpath(*lexical.parts)
    unsafe = symlink_component(path, boundary)
    if unsafe is not None:
        raise ContractError(f"operational path traverses a symlink: {unsafe.relative_to(boundary)}")
    if not path.exists():
        if allow_missing:
            parent_unsafe = symlink_component(path, boundary, include_final=False)
            if parent_unsafe is not None:
                raise ContractError(f"planned output parent traverses a symlink: {parent_unsafe.relative_to(boundary)}")
            return path
        raise ContractError(f"operational path is missing: {relative}")
    if final_type == "file" and not path.is_file():
        raise ContractError(f"operational path is not a regular file: {relative}")
    if final_type == "directory" and not path.is_dir():
        raise ContractError(f"operational path is not a directory: {relative}")
    return path


def enumerate_regular_files(root: Path | WikiContext, relative: str, suffix: str | None = None) -> list[Path]:
    boundary = checked_root(root)
    directory = safe_path(boundary, relative, final_type="directory")
    results: list[Path] = []
    for current, directories, files in os.walk(directory, topdown=True, followlinks=False):
        current_path = Path(current)
        unsafe_directories = [name for name in directories if (current_path / name).is_symlink()]
        if unsafe_directories:
            names = ", ".join(sorted((current_path / name).relative_to(boundary).as_posix() for name in unsafe_directories))
            raise ContractError(f"operational enumeration encountered symlinked directories: {names}")
        directories[:] = sorted(directories)
        for name in sorted(files):
            path = current_path / name
            if path.is_symlink():
                raise ContractError(
                    f"operational enumeration encountered a symlinked file: {path.relative_to(boundary).as_posix()}"
                )
            if suffix is None or path.suffix == suffix:
                results.append(path)
    return results


def ensure_safe_parent(path: Path, root: Path | WikiContext) -> None:
    """Reject an output whose lexical parent chain escapes or traverses a symlink."""
    boundary = checked_root(root)
    target = path.absolute()
    try:
        relative = target.relative_to(boundary)
    except ValueError as exc:
        raise RunError(f"output path is outside the wiki root: {path}") from exc
    current = boundary
    for part in relative.parts[:-1]:
        current /= part
        if current.is_symlink():
            raise RunError(f"output parent must not be a symlink: {current}")
        if current.exists() and not current.is_dir():
            raise RunError(f"output parent is not a directory: {current}")
