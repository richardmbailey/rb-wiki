from __future__ import annotations

import shutil
import sys
import tempfile
import unittest
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import ingest  # noqa: E402
import wiki_cron  # noqa: E402
from pdf_extract import extract_pdf_text, is_pdf_path  # noqa: E402
from wiki_test_support import make_git_wiki, run  # noqa: E402


def write_minimal_pdf(path: Path, text: str) -> None:
    safe_text = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    stream = f"BT /F1 24 Tf 72 720 Td ({safe_text}) Tj ET".encode("ascii")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length " + str(len(stream)).encode("ascii") + b" >>\nstream\n" + stream + b"\nendstream",
    ]
    content = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for index, obj in enumerate(objects, start=1):
        offsets.append(len(content))
        content.extend(f"{index} 0 obj\n".encode("ascii"))
        content.extend(obj)
        content.extend(b"\nendobj\n")
    xref_offset = len(content)
    content.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    content.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        content.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    content.extend(
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF\n".encode("ascii")
    )
    path.write_bytes(bytes(content))


class PdfIngestTests(unittest.TestCase):
    def test_pdf_suffix_is_supported_by_ingest_and_cron(self) -> None:
        self.assertIn(".pdf", ingest.SUPPORTED_SUFFIXES)
        self.assertIn(".pdf", wiki_cron.SUPPORTED_SUFFIXES)
        self.assertTrue(is_pdf_path(Path("source.PDF")))

    @unittest.skipUnless(shutil.which("pdftotext"), "Poppler pdftotext is not installed")
    def test_extract_pdf_text_from_generated_pdf(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            pdf_path = Path(tmp) / "sample.pdf"
            write_minimal_pdf(pdf_path, "Reliable PDF Ingest Test")

            text, method = extract_pdf_text(pdf_path)

        self.assertIn("Reliable PDF Ingest Test", text)
        self.assertEqual(method, "pdftotext -layout")

    def test_extraction_failure_preserves_pdf_and_archives_with_raw_only_access(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = make_git_wiki(Path(temporary))
            pdf = root / "inbox" / "broken.pdf"
            pdf.write_bytes(b"%PDF-1.4\nnot a complete pdf\n")
            completed = run(
                [sys.executable, "tools/ingest.py", "inbox/broken.pdf"],
                root,
                check=False,
                env_overrides={"RB_WIKI_RUN_CONTROLLER": "1"},
            )
            self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
            journals = list((root / ".wiki_state" / "sources").glob("*.json"))
            self.assertEqual(len(journals), 1)
            journal = json.loads(journals[0].read_text(encoding="utf-8"))
            self.assertEqual(journal["access_level"], "raw-only")
            self.assertTrue((root / journal["raw_path"]).is_file())
            reference = (root / journal["reference_path"]).read_text(encoding="utf-8")
            self.assertIn("source_access_level: raw-only", reference)
            self.assertIn("OCR or manual review", reference)
            self.assertFalse(pdf.exists())
            self.assertTrue((root / journal["processed_path"]).is_file())

    def test_symlinked_derivative_directory_cannot_redirect_pdf_output(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            parent = Path(temporary)
            root = make_git_wiki(parent)
            outside = parent / "outside-derived"
            outside.mkdir()
            derived = root / "sources" / "derived"
            if derived.exists():
                shutil.rmtree(derived)
            derived.symlink_to(outside, target_is_directory=True)
            pdf = root / "inbox" / "redirect.pdf"
            pdf.write_bytes(b"%PDF-1.4\nnot a complete pdf\n")
            completed = run(
                [sys.executable, "tools/ingest.py", "inbox/redirect.pdf"],
                root,
                check=False,
                env_overrides={"RB_WIKI_RUN_CONTROLLER": "1"},
            )
            self.assertNotEqual(completed.returncode, 0)
            self.assertEqual(list(outside.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
