from typing import Protocol, runtime_checkable


@runtime_checkable
class StorageProvider(Protocol):
    async def upload(self, path: str, content: bytes, mime_type: str) -> str:
        """Upload content to storage and return the storage path."""
        ...

    async def delete(self, path: str) -> None:
        """Delete a file from storage."""
        ...

    async def download(self, path: str) -> bytes:
        """Download file content from storage."""
        ...
