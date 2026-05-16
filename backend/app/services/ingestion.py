from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pypdf import PdfReader
from qdrant_client import QdrantClient
from qdrant_client.http.models import Distance, FieldCondition, Filter, MatchValue, PointStruct, VectorParams

from app.core.config import settings
from app.integrations.openai_client import embed_texts_sync


def _extract_metadata(pdf: Path) -> dict[str, str | None]:
    """Best-effort extraction of author, title, and document_type from a PDF."""
    try:
        from pypdf import PdfReader as _PdfReader
        reader = _PdfReader(str(pdf))
        meta = reader.metadata or {}
        author = str(meta.get("/Author", "") or "").strip() or None
        title = str(meta.get("/Title", "") or "").strip() or None
    except Exception:
        author = None
        title = None

    stem_lower = pdf.stem.lower()
    if any(kw in stem_lower for kw in ("iso", "astm", "norm", "standard", "din", "ansi", "ieee", "nbr")):
        document_type = "standard"
    elif any(kw in stem_lower for kw in ("paper", "article", "proceedings")):
        document_type = "paper"
    else:
        document_type = "book"

    return {"author": author, "title": title, "document_type": document_type}


def _file_sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            chunk = f.read(1024 * 1024)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def _point_id(checksum: str, page_num: int, chunk_idx: int) -> int:
    raw = f"{checksum}-{page_num}-{chunk_idx}".encode("utf-8")
    digest = hashlib.sha256(raw).hexdigest()
    # Fit in unsigned 63-bit range for broad Qdrant compatibility.
    return int(digest[:16], 16) & 0x7FFFFFFFFFFFFFFF


_MAX_CHUNK_CHARS = 8_000  # mirrors openai_client._MAX_CHARS; digits tokenize 1 char/token


def _chunk_text(text: str, size: int = 1200, overlap: int = 200) -> list[str]:
    tokens = text.split()
    if not tokens:
        return []
    chunks = []
    step = max(size - overlap, 1)
    for start in range(0, len(tokens), step):
        subset = tokens[start : start + size]
        if not subset:
            break
        chunk = " ".join(subset)
        # Guard against pathological pages (tables, merged numbers) that exceed token limit
        if len(chunk) > _MAX_CHUNK_CHARS:
            chunk = chunk[:_MAX_CHUNK_CHARS]
        chunks.append(chunk)
    return chunks


_MATERIAL_KEYWORDS: dict[str, str | None] = {
    "steel": "steel", "aço": "steel", "iron": "iron", "ferro": "iron",
    "copper": "copper", "cobre": "copper", "aluminum": "aluminum",
    "aluminium": "aluminum", "alumínio": "aluminum", "polymer": "polymer",
    "polímero": "polymer", "ceramic": "ceramic", "cerâmica": "ceramic",
    "composite": "composite", "compósito": "composite",
}

_HEADING_PATTERN = re.compile(
    r"(?m)^(?:"
    r"(\d+\.\d+(?:\.\d+)?\s+\S.{0,80})"
    r"|([A-Z][A-Z\s]{3,79})"
    r")"
)


def _detect_structure(page_text: str) -> dict[str, str | None]:
    """Heuristically detect chapter, section, and material_type from page text."""
    chapter: str | None = None
    section: str | None = None
    material_type: str | None = None

    lines = page_text.splitlines()
    for line in lines[:10]:
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.isupper() and len(stripped) >= 4 and stripped[-1] not in ".,:":
            chapter = stripped[:120]
            break
        if re.match(r"(?i)^(chapter|capítulo|cap\.?)\s+\d+", stripped):
            chapter = stripped[:120]
            break

    for line in lines:
        stripped = line.strip()
        if re.match(r"^\d+\.\d+(\.\d+)?\s+\S", stripped):
            section = stripped[:120]
            break

    text_lower = page_text.lower()
    for kw, mat in _MATERIAL_KEYWORDS.items():
        if kw in text_lower and mat:
            material_type = mat
            break

    return {"chapter": chapter, "section": section, "material_type": material_type}


def _chunk_by_structure(
    page_text: str, size: int = 1200, overlap: int = 200
) -> list[tuple[str, str | None]]:
    """Split page text by structural headings, then word-chunk within each section.

    Returns list of (chunk_text, section_heading_or_None).
    """
    matches = list(_HEADING_PATTERN.finditer(page_text))
    if not matches:
        return [(_c, None) for _c in _chunk_text(page_text, size, overlap)]

    sections: list[tuple[str | None, str]] = []
    if matches[0].start() > 0:
        pre = page_text[: matches[0].start()].strip()
        if pre:
            sections.append((None, pre))

    for i, m in enumerate(matches):
        heading = (m.group(1) or m.group(2)).strip()
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(page_text)
        body = page_text[start:end].strip()
        if body:
            sections.append((heading, body))

    result: list[tuple[str, str | None]] = []
    for heading, body in sections:
        for chunk in _chunk_text(body, size, overlap):
            result.append((chunk, heading))
    return result


def _already_indexed(client: QdrantClient, checksum: str) -> bool:
    """Return True if any Qdrant point with source_id == checksum already exists."""
    results, _ = client.scroll(
        collection_name=settings.qdrant_collection,
        scroll_filter=Filter(must=[FieldCondition(key="source_id", match=MatchValue(value=checksum))]),
        limit=1,
        with_payload=False,
        with_vectors=False,
    )
    return len(results) > 0


def _ocr_page_with_vision(pdf_path: Path, page_num: int) -> str:
    """Render PDF page as PNG and send to GPT-4o for text extraction."""
    import base64

    try:
        import fitz  # pymupdf
    except ImportError:
        return ""

    from app.integrations.openai_client import _get_sync_client
    from app.rag.prompts import VISION_PROMPT

    doc = fitz.open(str(pdf_path))
    page = doc[page_num - 1]
    pix = page.get_pixmap(dpi=150)
    img_bytes = pix.tobytes("png")
    doc.close()

    b64 = base64.b64encode(img_bytes).decode()
    response = _get_sync_client().chat.completions.create(
        model=settings.openai_vision_model,
        messages=[{"role": "user", "content": [
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
            {"type": "text", "text": VISION_PROMPT},
        ]}],
        max_tokens=500,
    )
    return response.choices[0].message.content or ""


def _extract_pages(path: Path) -> list[tuple[int, str]]:
    reader = PdfReader(str(path))
    pages = []
    for idx, page in enumerate(reader.pages, start=1):
        text = (page.extract_text() or "").strip()
        if len(text) < settings.ocr_min_chars and settings.ocr_backend == "vision":
            text = _ocr_page_with_vision(path, idx)
        if text.strip():
            pages.append((idx, text))
    return pages


def _load_checkpoint(checkpoint_file: Path | None) -> dict[str, Any]:
    if checkpoint_file is None or not checkpoint_file.exists():
        return {"processed_docs": [], "documents": 0, "chunks": 0}
    return json.loads(checkpoint_file.read_text(encoding="utf-8"))


def _save_checkpoint(checkpoint_file: Path | None, data: dict[str, Any]) -> None:
    if checkpoint_file is None:
        return
    checkpoint_file.parent.mkdir(parents=True, exist_ok=True)
    checkpoint_file.write_text(json.dumps(data, ensure_ascii=True, indent=2), encoding="utf-8")


def _ensure_collection(client: QdrantClient, recreate: bool) -> None:
    if recreate:
        client.recreate_collection(
            collection_name=settings.qdrant_collection,
            vectors_config=VectorParams(size=settings.qdrant_vector_size, distance=Distance.COSINE),
        )
    else:
        collections = {c.name for c in client.get_collections().collections}
        if settings.qdrant_collection not in collections:
            client.create_collection(
                collection_name=settings.qdrant_collection,
                vectors_config=VectorParams(size=settings.qdrant_vector_size, distance=Distance.COSINE),
            )


def _flush_pending(
    client: QdrantClient,
    pending: list[tuple[int, dict, str]],
    verbose: bool,
    total_chunks: int,
) -> None:
    if not pending:
        return
    texts = [text for _, _, text in pending]
    vectors = embed_texts_sync(texts)
    points = [
        PointStruct(id=point_id, vector=vector, payload=payload)
        for (point_id, payload, _), vector in zip(pending, vectors)
    ]
    client.upsert(collection_name=settings.qdrant_collection, points=points)
    if verbose:
        print(f"  flushed batch ({len(points)}) - total chunks: {total_chunks}")


def reindex_books(
    *,
    limit: int | None = None,
    offset: int = 0,
    batch_size: int = 128,
    recreate: bool = False,
    checkpoint_file: str | None = None,
    resume: bool = False,
    verbose: bool = True,
) -> dict:
    books_dir = Path(settings.books_dir)
    if not books_dir.exists():
        raise FileNotFoundError(f"Books directory not found: {books_dir}")

    pdfs = sorted(books_dir.glob("*.pdf"))
    if offset > 0:
        pdfs = pdfs[offset:]
    if limit is not None:
        pdfs = pdfs[:limit]

    cp_path = Path(checkpoint_file) if checkpoint_file else None
    cp_data = _load_checkpoint(cp_path) if resume else {"processed_docs": [], "documents": 0, "chunks": 0}
    processed = set(cp_data.get("processed_docs", []))

    if recreate and resume:
        raise ValueError("resume cannot be used together with recreate")

    client = QdrantClient(url=settings.qdrant_url)
    _ensure_collection(client, recreate)

    total_docs = int(cp_data.get("documents", 0))
    total_chunks = int(cp_data.get("chunks", 0))
    pending: list[tuple[int, dict, str]] = []

    for index, pdf in enumerate(pdfs, start=1):
        if pdf.name in processed:
            if verbose:
                print(f"[skip] {pdf.name} (already in checkpoint)")
            continue

        if verbose:
            print(f"[doc {index}/{len(pdfs)}] processing {pdf.name}")
        total_docs += 1
        checksum = _file_sha(pdf)
        if not recreate and _already_indexed(client, checksum):
            if verbose:
                print(f"  [skip] {pdf.name} already indexed (sha256 match)")
            processed.add(pdf.name)
            continue
        pages = _extract_pages(pdf)
        if verbose:
            print(f"  extracted pages with text: {len(pages)}")

        doc_meta = _extract_metadata(pdf)
        now = datetime.now(tz=timezone.utc).isoformat()
        for page_num, page_text in pages:
            if verbose and (page_num == 1 or page_num % 25 == 0):
                print(f"  page {page_num}/{len(pages)}")
            struct = _detect_structure(page_text)
            for chunk_idx, (chunk, chunk_section) in enumerate(_chunk_by_structure(page_text)):
                total_chunks += 1
                payload: dict[str, Any] = {
                    "source": pdf.name,
                    "source_id": checksum,
                    "page": page_num,
                    "chunk_id": f"{pdf.stem}-{page_num}-{chunk_idx}",
                    "text": chunk,
                    "document_type": doc_meta["document_type"],
                    "ingestion_timestamp": now,
                    "author": doc_meta["author"],
                    "title": doc_meta["title"],
                    "chapter": struct["chapter"],
                    "section": chunk_section or struct["section"],
                    "material_type": struct["material_type"],
                    "environment": None,
                }
                pending.append((_point_id(checksum, page_num, chunk_idx), payload, chunk))
                if len(pending) >= batch_size:
                    _flush_pending(client, pending, verbose, total_chunks)
                    pending = []

        processed.add(pdf.name)
        cp_data = {"processed_docs": sorted(processed), "documents": total_docs, "chunks": total_chunks}
        _save_checkpoint(cp_path, cp_data)
        if verbose:
            print(f"[done] {pdf.name} | accumulated chunks: {total_chunks}")

    if pending:
        _flush_pending(client, pending, verbose, total_chunks)

    return {"documents": total_docs, "chunks": total_chunks, "processed_docs": len(processed)}


def ingest_single_pdf(pdf_path: str, *, batch_size: int = 128, verbose: bool = True) -> dict:
    """Ingest a single PDF into the existing Qdrant collection without recreating it."""
    pdf = Path(pdf_path)
    if not pdf.exists() or not pdf.is_file():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    client = QdrantClient(url=settings.qdrant_url)
    _ensure_collection(client, recreate=False)

    checksum = _file_sha(pdf)
    if _already_indexed(client, checksum):
        if verbose:
            print(f"[skip] {pdf.name} already indexed (sha256 match)")
        return {"documents": 0, "chunks": 0, "source": pdf.name, "skipped": True}

    pages = _extract_pages(pdf)
    if verbose:
        print(f"[ingest] {pdf.name} | pages with text: {len(pages)}")

    doc_meta = _extract_metadata(pdf)
    now = datetime.now(tz=timezone.utc).isoformat()
    pending: list[tuple[int, dict, str]] = []
    total_chunks = 0

    for page_num, page_text in pages:
        struct = _detect_structure(page_text)
        for chunk_idx, (chunk, chunk_section) in enumerate(_chunk_by_structure(page_text)):
            total_chunks += 1
            payload: dict[str, Any] = {
                "source": pdf.name,
                "source_id": checksum,
                "page": page_num,
                "chunk_id": f"{pdf.stem}-{page_num}-{chunk_idx}",
                "text": chunk,
                "document_type": doc_meta["document_type"],
                "ingestion_timestamp": now,
                "author": doc_meta["author"],
                "title": doc_meta["title"],
                "chapter": struct["chapter"],
                "section": chunk_section or struct["section"],
                "material_type": struct["material_type"],
                "environment": None,
            }
            pending.append((_point_id(checksum, page_num, chunk_idx), payload, chunk))
            if len(pending) >= batch_size:
                _flush_pending(client, pending, verbose, total_chunks)
                pending = []

    if pending:
        _flush_pending(client, pending, verbose, total_chunks)

    if verbose:
        print(f"[done] {pdf.name} | chunks: {total_chunks}")
    return {"documents": 1, "chunks": total_chunks, "source": pdf.name}
