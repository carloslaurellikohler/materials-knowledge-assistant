"""Testes do PostgresStorageProvider (bytes do PDF persistidos no Postgres).

Usa um engine SQLite in-memory compartilhado (StaticPool) no lugar do Postgres,
monkeypatchando o ``SyncSessionLocal`` que o provider importa. ``LargeBinary``
mapeia para BLOB no SQLite, então o roundtrip de bytes funciona normalmente.
"""

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.database import Base
from app.db.models import DocumentBlob


@pytest.fixture
def provider(monkeypatch):
    # check_same_thread=False + StaticPool: o mesmo banco in-memory é visível
    # também na thread usada por asyncio.to_thread (métodos async).
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    TestSession = sessionmaker(engine, expire_on_commit=False)

    import app.storage.postgres_provider as pg

    monkeypatch.setattr(pg, "SyncSessionLocal", TestSession)

    yield pg.PostgresStorageProvider(), TestSession

    engine.dispose()


def test_sync_upload_download_roundtrip(provider):
    storage, _ = provider
    path = "user-1/doc-abc/relatorio.pdf"
    content = b"%PDF-1.4 conteudo binario \x00\x01\x02"

    returned = storage.sync_upload(path, content, "application/pdf")

    assert returned == path
    assert storage.sync_download(path) == content


def test_sync_delete_removes_blob(provider):
    storage, _ = provider
    path = "user-1/doc-abc/file.pdf"
    storage.sync_upload(path, b"data", "application/pdf")

    storage.sync_delete(path)

    with pytest.raises(FileNotFoundError):
        storage.sync_download(path)


def test_download_missing_raises(provider):
    storage, _ = provider
    with pytest.raises(FileNotFoundError):
        storage.sync_download("user-1/missing/none.pdf")


def test_upload_is_upsert(provider):
    storage, TestSession = provider
    path = "user-1/doc-abc/file.pdf"

    storage.sync_upload(path, b"versao-1", "application/pdf")
    storage.sync_upload(path, b"versao-2", "application/pdf")

    assert storage.sync_download(path) == b"versao-2"
    with TestSession() as session:
        count = session.execute(select(func.count()).select_from(DocumentBlob)).scalar_one()
    assert count == 1


def test_document_id_extracted_from_path(provider):
    storage, TestSession = provider
    path = "user-1/doc-xyz-123/relatorio.pdf"
    storage.sync_upload(path, b"data", "application/pdf")

    with TestSession() as session:
        blob = session.get(DocumentBlob, path)
    assert blob.document_id == "doc-xyz-123"
    assert blob.mime_type == "application/pdf"


async def test_async_roundtrip(provider):
    storage, _ = provider
    path = "user-2/doc-async/file.pdf"
    content = b"async-bytes"

    await storage.upload(path, content, "application/pdf")
    assert await storage.download(path) == content

    await storage.delete(path)
    with pytest.raises(FileNotFoundError):
        await storage.download(path)
