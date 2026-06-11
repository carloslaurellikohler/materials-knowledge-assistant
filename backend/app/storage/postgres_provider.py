"""Storage provider que persiste os bytes dos PDFs no próprio Postgres.

Substitui o antigo SupabaseStorageProvider, mantendo o mesmo contrato
(``StorageProvider`` em ``app/storage/provider.py``): métodos async para o
FastAPI e variantes ``sync_*`` para o worker Celery. Os bytes ficam na tabela
``document_blobs`` (ver ``app/db/models.py``), chaveada por ``storage_path``.

Assim como o provider anterior, os métodos async apenas embrulham as variantes
síncronas via ``asyncio.to_thread`` — a I/O de banco usa o engine síncrono
(psycopg2), evitando bloquear o event loop.
"""

import asyncio
import logging

from sqlalchemy import delete as sql_delete
from sqlalchemy import select

from app.db.database import SyncSessionLocal
from app.db.models import DocumentBlob

logger = logging.getLogger(__name__)


def _document_id_from_path(path: str) -> str:
    """Extrai o document_id de ``{user_id}/{document_id}/{filename}``.

    Usado apenas para preencher a coluna indexável ``document_id`` (debug/cleanup);
    a chave real é o ``storage_path``. Degrada para "" se o formato for inesperado.
    """
    parts = path.split("/")
    return parts[1] if len(parts) >= 3 else ""


class PostgresStorageProvider:
    # --- variantes síncronas (worker Celery) ---
    def sync_upload(self, path: str, content: bytes, mime_type: str) -> str:
        with SyncSessionLocal() as session:
            # merge = upsert pela PK (storage_path), portável entre Postgres e SQLite
            session.merge(
                DocumentBlob(
                    storage_path=path,
                    document_id=_document_id_from_path(path),
                    content=content,
                    mime_type=mime_type,
                )
            )
            session.commit()
        return path

    def sync_download(self, path: str) -> bytes:
        with SyncSessionLocal() as session:
            result = session.execute(
                select(DocumentBlob.content).where(DocumentBlob.storage_path == path)
            )
            content = result.scalar_one_or_none()
        if content is None:
            raise FileNotFoundError(f"No document blob stored at path={path}")
        return content

    def sync_delete(self, path: str) -> None:
        with SyncSessionLocal() as session:
            session.execute(sql_delete(DocumentBlob).where(DocumentBlob.storage_path == path))
            session.commit()

    # --- variantes async (FastAPI) ---
    async def upload(self, path: str, content: bytes, mime_type: str) -> str:
        return await asyncio.to_thread(self.sync_upload, path, content, mime_type)

    async def download(self, path: str) -> bytes:
        return await asyncio.to_thread(self.sync_download, path)

    async def delete(self, path: str) -> None:
        await asyncio.to_thread(self.sync_delete, path)


_provider: PostgresStorageProvider | None = None


def get_storage() -> PostgresStorageProvider:
    global _provider
    if _provider is None:
        _provider = PostgresStorageProvider()
    return _provider
