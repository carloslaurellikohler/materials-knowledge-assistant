import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Enum, Integer, LargeBinary, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


def _now() -> datetime:
    return datetime.now(tz=timezone.utc)


IndexingStatus = Enum(
    "pending", "processing", "chunking", "embedding", "indexed", "error",
    name="indexing_status",
)


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    filename: Mapped[str] = mapped_column(String(512), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(512), nullable=False)
    storage_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(128), nullable=False)
    size: Mapped[int] = mapped_column(Integer, nullable=False)
    indexing_status: Mapped[str] = mapped_column(IndexingStatus, nullable=False, default="pending")
    indexing_error: Mapped[str | None] = mapped_column(Text, nullable=True, default=None)
    chunk_count: Mapped[int | None] = mapped_column(Integer, nullable=True, default=None)
    embedding_model: Mapped[str | None] = mapped_column(String(128), nullable=True, default=None)
    qdrant_collection: Mapped[str] = mapped_column(String(256), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)


class DocumentBlob(Base):
    """Bytes do PDF persistidos no próprio Postgres (substitui o Supabase Storage).

    Tabela separada de ``documents`` para manter as listagens de metadados leves —
    o conteúdo binário só é carregado na ingestão/download, nunca no GET /documents.
    Chaveada por ``storage_path`` (mesma chave lógica usada pelo StorageProvider).
    """

    __tablename__ = "document_blobs"

    storage_path: Mapped[str] = mapped_column(String(1024), primary_key=True)
    document_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    content: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    mime_type: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
