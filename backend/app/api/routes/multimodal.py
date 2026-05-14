from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status

from app.api.deps import get_current_user
from app.core.config import settings
from app.integrations.openai_client import describe_image, transcribe_audio

router = APIRouter(tags=["multimodal"])

_ACCEPTED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
_ACCEPTED_AUDIO_TYPES = {"audio/mpeg", "audio/mp3", "audio/wav", "audio/x-wav", "audio/mp4", "audio/m4a", "audio/ogg"}


@router.post("/upload/image")
async def upload_image(
    file: UploadFile = File(...),
    _: dict = Depends(get_current_user),
) -> dict:
    contents = await file.read()
    max_bytes = settings.max_image_upload_mb * 1024 * 1024
    if len(contents) > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=f"Image exceeds maximum size of {settings.max_image_upload_mb}MB",
        )

    mime_type = file.content_type or "image/jpeg"
    description = await describe_image(contents, mime_type)
    return {"status": "analyzed", "description": description, "filename": file.filename}


@router.post("/upload/audio")
async def upload_audio(
    file: UploadFile = File(...),
    _: dict = Depends(get_current_user),
) -> dict:
    contents = await file.read()
    max_bytes = settings.max_audio_upload_mb * 1024 * 1024
    if len(contents) > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=f"Audio exceeds maximum size of {settings.max_audio_upload_mb}MB",
        )

    transcript = await transcribe_audio(contents, file.filename or "audio.mp3")
    return {"status": "transcribed", "transcript": transcript, "filename": file.filename}
