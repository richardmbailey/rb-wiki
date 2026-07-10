from __future__ import annotations

import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import ingest  # noqa: E402
import wiki_cron  # noqa: E402
from pdf_extract import extract_pdf_text, is_pdf_path  # noqa: E402


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


if __name__ == "__main__":
    unittest.main()
