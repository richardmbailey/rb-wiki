#!/usr/bin/env python3
"""PDF text extraction helpers for source ingestion."""

from __future__ import annotations

import importlib.util
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from wiki_lib import ROOT, SOURCES_DIR, now_utc
from run_lib import atomic_write_text, symlink_component

PDF_SUFFIXES = {".pdf"}
DERIVED_DIR = SOURCES_DIR / "derived"


@dataclass(frozen=True)
class PdfExtractionResult:
    status: str
    method: str
    char_count: int
    derived_path: str
    note: str


def is_pdf_path(path: Path) -> bool:
    return path.suffix.lower() in PDF_SUFFIXES


def extract_pdf_text(path: Path) -> tuple[str, str]:
    """Extract PDF text using Poppler first, with an optional pypdf fallback."""
    pdftotext = shutil.which("pdftotext")
    if pdftotext:
        completed = subprocess.run(
            [pdftotext, "-layout", "-enc", "UTF-8", str(path), "-"],
            text=True,
            capture_output=True,
            check=False,
            timeout=120,
        )
        if completed.returncode == 0:
            return normalize_extracted_text(completed.stdout), "pdftotext -layout"
        raise RuntimeError((completed.stderr or completed.stdout or "pdftotext failed").strip())

    if importlib.util.find_spec("pypdf") is not None:
        from pypdf import PdfReader  # type: ignore[import-not-found]

        reader = PdfReader(str(path))
        text = "\n\n".join(page.extract_text() or "" for page in reader.pages)
        return normalize_extracted_text(text), "pypdf"

    raise RuntimeError("PDF text extraction requires Poppler `pdftotext` or the Python package `pypdf`.")


def normalize_extracted_text(text: str) -> str:
    text = text.replace("\x00", "")
    lines = [line.rstrip() for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n")]
    return "\n".join(lines).strip()


def ensure_pdf_text_derivative(entry: dict[str, str], pdf_path: Path) -> PdfExtractionResult:
    """Create or reuse extracted text for a registered PDF source."""
    source_id = entry["source_id"]
    raw_path = entry["raw_path"]
    raw_hash = entry["hash_sha256"]
    derived_path = DERIVED_DIR / f"{source_id}.txt"
    derived_rel = derived_path.relative_to(ROOT).as_posix()

    unsafe = symlink_component(derived_path, ROOT)
    if unsafe is not None:
        raise RuntimeError(f"refusing symlinked PDF derivative path: {unsafe}")
    if derived_path.is_file():
        existing = derived_path.read_text(encoding="utf-8", errors="replace")
        return PdfExtractionResult(
            status="existing",
            method="existing derived text",
            char_count=len(existing),
            derived_path=derived_rel,
            note="Reused existing extracted text derivative.",
        )

    try:
        extracted_text, method = extract_pdf_text(pdf_path)
    except Exception as exc:
        return PdfExtractionResult(
            status="failed",
            method="unavailable",
            char_count=0,
            derived_path="",
            note=str(exc),
        )

    status = "text-extracted" if extracted_text.strip() else "no-text"
    note = "Extracted text from PDF." if status == "text-extracted" else "No extractable text found; OCR or manual review may be required."
    body = build_derived_text(source_id, raw_path, raw_hash, method, status, extracted_text)
    DERIVED_DIR.mkdir(parents=True, exist_ok=True)
    atomic_write_text(derived_path, body, ROOT)
    return PdfExtractionResult(
        status=status,
        method=method,
        char_count=len(extracted_text),
        derived_path=derived_rel,
        note=note,
    )


def build_derived_text(
    source_id: str,
    raw_path: str,
    raw_hash: str,
    method: str,
    status: str,
    extracted_text: str,
) -> str:
    return f"""# Derived PDF Text

source_id: {source_id}
raw_path: {raw_path}
raw_hash_sha256: {raw_hash}
extracted_at: {now_utc()}
extraction_method: {method}
extraction_status: {status}

This file is a generated derivative for search and review. It is not the immutable raw source.

# Extracted Text

{extracted_text}
""".rstrip() + "\n"
