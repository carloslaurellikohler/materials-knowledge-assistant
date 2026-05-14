import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status

from app.api.deps import get_current_user
from app.core.config import settings
from app.workers.tasks import ingest_single_pdf_task

router = APIRouter(tags=["upload"])


@router.post("/upload/pdf")
async def upload_pdf(
    request: Request,
    file: UploadFile = File(...),
    _: dict = Depends(get_current_user),
) -> dict:
    safe_name = Path(file.filename or "upload.pdf").name
    if not safe_name.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Only PDF files are accepted",
        )

    contents = await file.read()
    max_bytes = settings.max_upload_mb * 1024 * 1024
    if len(contents) > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=f"File exceeds maximum size of {settings.max_upload_mb}MB",
        )

    dest = Path(settings.books_dir) / safe_name
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(contents)

    ingest_single_pdf_task.delay(str(dest))

    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    return {"status": "queued", "filename": safe_name, "request_id": request_id}
