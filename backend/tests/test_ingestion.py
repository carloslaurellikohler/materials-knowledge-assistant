import hashlib
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.services.ingestion import (
    _already_indexed,
    _chunk_by_structure,
    _chunk_text,
    _detect_structure,
    _extract_pages,
    _file_sha,
    _point_id,
    ingest_single_pdf,
    reindex_books,
)


def test_chunk_text_basic():
    text = " ".join(["word"] * 1500)
    chunks = _chunk_text(text, size=1200, overlap=200)
    assert len(chunks) > 1
    for chunk in chunks:
        assert len(chunk.split()) <= 1200


def test_chunk_text_empty():
    assert _chunk_text("") == []
    assert _chunk_text("   ") == []


def test_chunk_text_smaller_than_size():
    text = "hello world foo bar"
    chunks = _chunk_text(text, size=1200, overlap=200)
    assert len(chunks) == 1
    assert chunks[0] == text


def test_chunk_text_overlap():
    words = list(range(1000))
    text = " ".join(str(w) for w in words)
    chunks = _chunk_text(text, size=10, overlap=3)
    assert len(chunks) > 1
    # Second chunk should start 7 words after first chunk's start
    first_words = chunks[0].split()
    second_words = chunks[1].split()
    assert second_words[0] == first_words[7]


def test_point_id_is_deterministic():
    id1 = _point_id("abc123", 1, 0)
    id2 = _point_id("abc123", 1, 0)
    assert id1 == id2


def test_point_id_differs_for_different_inputs():
    id1 = _point_id("abc123", 1, 0)
    id2 = _point_id("abc123", 1, 1)
    id3 = _point_id("abc123", 2, 0)
    assert id1 != id2
    assert id1 != id3


def test_point_id_fits_in_63_bits():
    pid = _point_id("checksum", 5, 10)
    assert 0 <= pid <= 0x7FFFFFFFFFFFFFFF


def test_file_sha_returns_hex_string(tmp_path):
    f = tmp_path / "test.pdf"
    f.write_bytes(b"fake pdf content")
    sha = _file_sha(f)
    assert len(sha) == 64
    assert all(c in "0123456789abcdef" for c in sha)


def test_reindex_books_raises_if_dir_missing():
    with patch("app.services.ingestion.settings") as mock_settings:
        mock_settings.books_dir = "/nonexistent/path/xyz"
        mock_settings.qdrant_url = "http://localhost:6333"
        mock_settings.qdrant_collection = "test"
        mock_settings.qdrant_vector_size = 1536
        with pytest.raises(FileNotFoundError):
            reindex_books()


def test_ingest_single_pdf_raises_if_file_missing():
    with pytest.raises(FileNotFoundError):
        ingest_single_pdf("/nonexistent/file.pdf")


def test_reindex_books_processes_pdfs(tmp_path):
    books_dir = tmp_path / "livros"
    books_dir.mkdir()
    # Create a minimal fake PDF (pypdf will fail, but we mock _extract_pages)
    pdf_file = books_dir / "test.pdf"
    pdf_file.write_bytes(b"%PDF-1.4 fake")

    mock_qdrant = MagicMock()
    mock_qdrant.get_collections.return_value.collections = []
    mock_qdrant.scroll.return_value = ([], None)  # not already indexed

    with (
        patch("app.services.ingestion.settings") as mock_settings,
        patch("app.services.ingestion.QdrantClient", return_value=mock_qdrant),
        patch("app.services.ingestion._extract_pages", return_value=[(1, "carbon steel corrosion")]),
        patch("app.services.ingestion.embed_texts_sync", return_value=[[0.1] * 1536]),
    ):
        mock_settings.books_dir = str(books_dir)
        mock_settings.qdrant_url = "http://localhost:6333"
        mock_settings.qdrant_collection = "test_col"
        mock_settings.qdrant_vector_size = 1536
        mock_settings.ocr_backend = "none"
        mock_settings.ocr_min_chars = 50

        result = reindex_books(verbose=False)

    assert result["documents"] == 1
    assert result["chunks"] >= 1
    mock_qdrant.upsert.assert_called()


# --- Gap 2: _detect_structure ---

def test_detect_structure_chapter_all_caps():
    text = "INTRODUCTION\nSome content about materials."
    result = _detect_structure(text)
    assert result["chapter"] == "INTRODUCTION"


def test_detect_structure_chapter_keyword():
    text = "Chapter 3 Corrosion Mechanisms\nDetails here."
    result = _detect_structure(text)
    assert result["chapter"] is not None
    assert "Chapter 3" in result["chapter"]


def test_detect_structure_section_numbered():
    text = "Some intro\n3.2 Galvanic Corrosion\nThis section covers galvanic effects."
    result = _detect_structure(text)
    assert result["section"] is not None
    assert "3.2" in result["section"]


def test_detect_structure_material_type():
    text = "The copper conductor degrades due to oxidation."
    result = _detect_structure(text)
    assert result["material_type"] == "copper"


def test_detect_structure_no_match_returns_nones():
    text = "1234 some random numbers and words without structure."
    result = _detect_structure(text)
    assert result["chapter"] is None
    assert result["section"] is None


# --- Gap 1: _chunk_by_structure ---

def test_chunk_by_structure_no_headings():
    text = "plain text without any headings or numbered sections here"
    result = _chunk_by_structure(text, size=1200, overlap=200)
    plain = _chunk_text(text, size=1200, overlap=200)
    assert [chunk for chunk, _ in result] == plain
    assert all(section is None for _, section in result)


def test_chunk_by_structure_with_numbered_section():
    body = "galvanic corrosion occurs at " + " ".join(["word"] * 10)
    text = f"3.2 Galvanic Corrosion\n{body}"
    result = _chunk_by_structure(text, size=1200, overlap=200)
    assert len(result) >= 1
    sections = [s for _, s in result if s is not None]
    assert any("3.2" in s for s in sections)


def test_chunk_by_structure_with_caps_heading():
    body = "this chapter introduces " + " ".join(["word"] * 10)
    text = f"INTRODUCTION\n{body}"
    result = _chunk_by_structure(text, size=1200, overlap=200)
    assert len(result) >= 1
    sections = [s for _, s in result if s is not None]
    assert any("INTRODUCTION" in s for s in sections)


def test_chunk_by_structure_pre_heading_text():
    text = "preamble text\n3.1 First Section\nbody content here"
    result = _chunk_by_structure(text, size=1200, overlap=200)
    chunks = [c for c, _ in result]
    full = " ".join(chunks)
    assert "preamble" in full
    assert "body content" in full


# --- Gap 5: _already_indexed ---

def test_already_indexed_returns_true_when_point_exists():
    mock_client = MagicMock()
    mock_client.scroll.return_value = ([MagicMock()], None)
    with patch("app.services.ingestion.settings") as ms:
        ms.qdrant_collection = "test_col"
        result = _already_indexed(mock_client, "abc123")
    assert result is True


def test_already_indexed_returns_false_when_no_points():
    mock_client = MagicMock()
    mock_client.scroll.return_value = ([], None)
    with patch("app.services.ingestion.settings") as ms:
        ms.qdrant_collection = "test_col"
        result = _already_indexed(mock_client, "abc123")
    assert result is False


def test_ingest_single_pdf_skips_duplicate(tmp_path):
    pdf = tmp_path / "test.pdf"
    pdf.write_bytes(b"%PDF-1.4 fake")

    mock_qdrant = MagicMock()
    mock_qdrant.get_collections.return_value.collections = []
    mock_qdrant.scroll.return_value = ([MagicMock()], None)  # already indexed

    with (
        patch("app.services.ingestion.QdrantClient", return_value=mock_qdrant),
        patch("app.services.ingestion.embed_texts_sync") as mock_embed,
        patch("app.services.ingestion.settings") as ms,
    ):
        ms.qdrant_url = "http://localhost:6333"
        ms.qdrant_collection = "test_col"
        ms.qdrant_vector_size = 1536
        ms.ocr_backend = "none"
        ms.ocr_min_chars = 50

        result = ingest_single_pdf(str(pdf), verbose=False)

    mock_embed.assert_not_called()
    assert result["skipped"] is True
    assert result["chunks"] == 0


# --- Gap 3: OCR fallback ---

def test_extract_pages_ocr_fallback_called_when_text_sparse(tmp_path):
    pdf = tmp_path / "scanned.pdf"
    pdf.write_bytes(b"%PDF-1.4 fake")

    with (
        patch("app.services.ingestion.PdfReader") as mock_reader_cls,
        patch("app.services.ingestion.settings") as ms,
        patch("app.services.ingestion._ocr_page_with_vision", return_value="OCR extracted text") as mock_ocr,
    ):
        ms.ocr_backend = "vision"
        ms.ocr_min_chars = 50

        mock_page = MagicMock()
        mock_page.extract_text.return_value = "tiny"  # < 50 chars
        mock_reader_cls.return_value.pages = [mock_page]

        pages = _extract_pages(pdf)

    mock_ocr.assert_called_once()
    assert len(pages) == 1
    assert pages[0][1] == "OCR extracted text"


def test_extract_pages_no_ocr_when_backend_is_none(tmp_path):
    pdf = tmp_path / "native.pdf"
    pdf.write_bytes(b"%PDF-1.4 fake")

    with (
        patch("app.services.ingestion.PdfReader") as mock_reader_cls,
        patch("app.services.ingestion.settings") as ms,
        patch("app.services.ingestion._ocr_page_with_vision") as mock_ocr,
    ):
        ms.ocr_backend = "none"
        ms.ocr_min_chars = 50

        mock_page = MagicMock()
        mock_page.extract_text.return_value = "tiny"
        mock_reader_cls.return_value.pages = [mock_page]

        _extract_pages(pdf)

    mock_ocr.assert_not_called()
