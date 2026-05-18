from datetime import datetime

from pydantic import BaseModel


class DocumentItem(BaseModel):
    source: str
    indexed: bool = True


class DocumentResponse(BaseModel):
    id: str
    filename: str
    original_filename: str
    size: int
    indexing_status: str
    indexing_error: str | None
    chunk_count: int | None
    embedding_model: str | None
    qdrant_collection: str
    created_at: datetime

    model_config = {"from_attributes": True}


class UploadResponse(BaseModel):
    document_id: str
    indexing_status: str
