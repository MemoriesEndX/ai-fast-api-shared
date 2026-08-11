import io
import pytest
from fastapi import HTTPException
from app.services.pdf_service import PDFService
from app.services.text_cleaning_service import TextCleaningService

# Minimal valid raw text-based PDF bytes
SAMPLE_PDF_BYTES = b"""%PDF-1.4
1 0 obj <</Type /Catalog /Pages 2 0 R>> endobj
2 0 obj <</Type /Pages /Kids [3 0 R] /Count 1>> endobj
3 0 obj <</Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources <</Font <</F1 4 0 R>>>> /Contents 5 0 R>> endobj
4 0 obj <</Type /Font /Subtype /Type1 /BaseFont /Helvetica>> endobj
5 0 obj <</Length 68>> stream
BT
/F1 12 Tf
100 700 Td
(Safety Induction LMS Module Page 1) Tj
ET
endstream
endobj
xref
0 6
0000000000 65535 f 
0000000009 00000 n 
0000000058 00000 n 
0000000115 00000 n 
0000000244 00000 n 
0000000313 00000 n 
trailer <</Size 6 /Root 1 0 R>>
startxref
432
%%EOF"""


def test_text_cleaning_service():
    cleaner = TextCleaningService()
    raw = "  Safety    Induction \r\n\r\n\r\nPage 1 of 10\n  \n  Alat  Pelindung   Diri  "
    cleaned = cleaner.clean_text(raw)
    assert "Safety Induction" in cleaned
    assert "Alat Pelindung Diri" in cleaned
    assert "Page 1 of 10" not in cleaned


def test_pdf_validation_extension():
    service = PDFService()
    with pytest.raises(HTTPException) as exc_info:
        service.validate_pdf_file("document.txt", b"dummy")
    assert exc_info.value.status_code == 400
    assert exc_info.value.detail["code"] == "INVALID_FILE_TYPE"


def test_pdf_validation_empty_file():
    service = PDFService()
    with pytest.raises(HTTPException) as exc_info:
        service.validate_pdf_file("document.pdf", b"")
    assert exc_info.value.status_code == 400
    assert exc_info.value.detail["code"] == "EMPTY_FILE"


def test_pdf_text_extraction():
    service = PDFService()
    pages, doc_hash, total_pages = service.extract_structured_text(SAMPLE_PDF_BYTES)
    assert total_pages == 1
    assert len(pages) == 1
    assert pages[0]["page"] == 1
    assert "Safety Induction LMS Module Page 1" in pages[0]["text"]
    assert len(doc_hash) == 64  # SHA-256 length
