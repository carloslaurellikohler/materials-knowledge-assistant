import asyncio
import logging
from functools import cached_property

from supabase import Client, create_client

from app.core.config import settings

logger = logging.getLogger(__name__)


class SupabaseStorageProvider:
    @cached_property
    def _client(self) -> Client:
        return create_client(settings.supabase_url, settings.supabase_key)

    def _sync_upload(self, path: str, content: bytes, mime_type: str) -> str:
        try:
            self._client.storage.from_(settings.supabase_bucket).upload(
                path=path,
                file=content,
                file_options={"content-type": mime_type, "upsert": "true"},
            )
        except Exception as exc:
            # Log the Supabase response body when available for easier diagnosis
            body = ""
            if hasattr(exc, "response") and exc.response is not None:
                try:
                    body = exc.response.text
                except Exception:
                    pass
            logger.error("Supabase Storage upload failed | path=%s | error=%s | body=%s", path, exc, body)
            raise
        return path

    def _sync_delete(self, path: str) -> None:
        self._client.storage.from_(settings.supabase_bucket).remove([path])

    def _sync_download(self, path: str) -> bytes:
        return self._client.storage.from_(settings.supabase_bucket).download(path)

    async def upload(self, path: str, content: bytes, mime_type: str) -> str:
        return await asyncio.to_thread(self._sync_upload, path, content, mime_type)

    async def delete(self, path: str) -> None:
        await asyncio.to_thread(self._sync_delete, path)

    async def download(self, path: str) -> bytes:
        return await asyncio.to_thread(self._sync_download, path)

    # Sync variants for Celery workers
    def sync_upload(self, path: str, content: bytes, mime_type: str) -> str:
        return self._sync_upload(path, content, mime_type)

    def sync_delete(self, path: str) -> None:
        self._sync_delete(path)

    def sync_download(self, path: str) -> bytes:
        return self._sync_download(path)


_provider: SupabaseStorageProvider | None = None


def get_storage() -> SupabaseStorageProvider:
    global _provider
    if _provider is None:
        _provider = SupabaseStorageProvider()
    return _provider
