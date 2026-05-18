from __future__ import annotations

import re
import unicodedata
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.api.schemas.documents import DocumentResponse, UploadResponse
from app.core.config import settings
from app.db.database import get_db
from app.db.models import Document
from app.storage.supabase_provider import get_storage
from app.workers.tasks import ingest_document_task

router = APIRouter(tags=["documents"])

# ASCII-only: letters, digits, hyphen, dot, underscore
_SAFE_NAME = re.compile(r"[^A-Za-z0-9\-._]")


def _sanitize(filename: str) -> str:
    # Decompose accented characters (ê→e, ç→c, ã→a) then drop non-ASCII
    normalized = unicodedata.normalize("NFKD", filename)
    ascii_only = normalized.encode("ascii", "ignore").decode("ascii")
    name = _SAFE_NAME.sub("_", ascii_only)
    return name[:255] or "upload.pdf"


@router.post("/documents", response_model=UploadResponse, status_code=status.HTTP_202_ACCEPTED)
async def upload_document(
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UploadResponse:
    if file.content_type not in ("application/pdf", "application/octet-stream"):
        if not (file.filename or "").lower().endswith(".pdf"):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Only PDF files are accepted",
            )

    contents = await file.read()
    max_bytes = settings.max_upload_mb * 1024 * 1024
    if len(contents) > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds maximum size of {settings.max_upload_mb}MB",
        )

    user_id: str = current_user["sub"]
    document_id = str(uuid.uuid4())
    original_filename = file.filename or "upload.pdf"
    safe_name = _sanitize(original_filename)
    storage_path = f"{user_id}/{document_id}/{safe_name}"

    storage = get_storage()
    await storage.upload(storage_path, contents, "application/pdf")

    doc = Document(
        id=document_id,
        user_id=user_id,
        filename=safe_name,
        original_filename=original_filename,
        storage_path=storage_path,
        mime_type="application/pdf",
        size=len(contents),
        indexing_status="pending",
        embedding_model=settings.openai_embedding_model,
        qdrant_collection=settings.qdrant_collection,
    )
    db.add(doc)
    await db.commit()

    ingest_document_task.delay(document_id)

    return UploadResponse(document_id=document_id, indexing_status="pending")


@router.get("/documents", response_model=list[DocumentResponse])
async def list_documents(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[DocumentResponse]:
    user_id: str = current_user["sub"]
    result = await db.execute(
        select(Document).where(Document.user_id == user_id).order_by(Document.created_at.desc())
    )
    return list(result.scalars().all())


@router.get("/documents/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DocumentResponse:
    user_id: str = current_user["sub"]
    result = await db.execute(
        select(Document).where(Document.id == document_id, Document.user_id == user_id)
    )
    doc = result.scalar_one_or_none()
    if doc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    return doc


@router.delete("/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    document_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    user_id: str = current_user["sub"]
    result = await db.execute(
        select(Document).where(Document.id == document_id, Document.user_id == user_id)
    )
    doc = result.scalar_one_or_none()
    if doc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    # Delete vectors from Qdrant
    from qdrant_client import QdrantClient
    from qdrant_client.http.models import FieldCondition, Filter, FilterSelector, MatchValue

    qdrant = QdrantClient(url=settings.qdrant_url)
    qdrant.delete(
        collection_name=settings.qdrant_collection,
        points_selector=FilterSelector(
            filter=Filter(must=[FieldCondition(key="document_id", match=MatchValue(value=document_id))])
        ),
    )

    # Delete file from Supabase Storage
    storage = get_storage()
    await storage.delete(doc.storage_path)

    # Delete DB record
    await db.delete(doc)
    await db.commit()
