from collections.abc import AsyncGenerator, Generator

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import settings


class Base(DeclarativeBase):
    pass


# Async engine for FastAPI
_async_engine = create_async_engine(settings.database_url, echo=False)
AsyncSessionLocal = async_sessionmaker(_async_engine, expire_on_commit=False)

# Sync engine for Celery workers
_sync_url = settings.database_url.replace("postgresql+asyncpg://", "postgresql+psycopg2://")
_sync_engine = create_engine(_sync_url, echo=False)
SyncSessionLocal = sessionmaker(_sync_engine, expire_on_commit=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session


def get_sync_db() -> Generator[Session, None, None]:
    with SyncSessionLocal() as session:
        yield session


async def create_tables() -> None:
    async with _async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
