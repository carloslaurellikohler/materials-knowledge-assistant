from __future__ import annotations

from dataclasses import dataclass

from qdrant_client import AsyncQdrantClient
from qdrant_client.models import FieldCondition, Filter, MatchValue

from app.core.config import settings


@dataclass
class RetrievedChunk:
    source: str
    text: str
    page: int | None = None
    chapter: str | None = None
    section: str | None = None


async def retrieve_context(
    client: AsyncQdrantClient,
    query_vector: list[float],
    metadata_filters: dict,
    limit: int = 5,
    user_id: str | None = None,
) -> list[RetrievedChunk]:
    must = []
    if user_id:
        must.append(FieldCondition(key="user_id", match=MatchValue(value=user_id)))
    for key, value in metadata_filters.items():
        must.append(FieldCondition(key=key, match=MatchValue(value=value)))
    query_filter = Filter(must=must) if must else None
    points = await client.query_points(
        collection_name=settings.qdrant_collection,
        query=query_vector,
        query_filter=query_filter,
        limit=limit,
        with_payload=True,
    )
    chunks: list[RetrievedChunk] = []
    for point in points.points:
        payload = point.payload or {}
        chunks.append(
            RetrievedChunk(
                source=str(payload.get("source", "unknown.pdf")),
                text=str(payload.get("text", "")),
                page=payload.get("page"),
                chapter=payload.get("chapter"),
                section=payload.get("section"),
            )
        )
    return chunks

