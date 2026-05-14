from __future__ import annotations

import time
import uuid
from collections.abc import AsyncGenerator

from qdrant_client import AsyncQdrantClient

from app.api.schemas.chat import Citation
from app.core.config import settings
from app.core.metrics_store import RequestMetric, get_store
from app.integrations.openai_client import embed_texts, stream_answer
from app.services.reranking import get_reranker
from app.services.retrieval import retrieve_context


async def stream_chat(
    client: AsyncQdrantClient,
    message: str,
    metadata_filters: dict,
    request_id: str | None = None,
) -> AsyncGenerator[tuple[str, list[Citation] | None], None]:
    """Yield (token, None) per streamed token, then ("", citations) at the end."""
    rid = request_id or str(uuid.uuid4())
    retrieval_ms = 0.0
    llm_ms = 0.0
    cited = False

    t0 = time.monotonic()
    query_vector = (await embed_texts([message]))[0]
    candidates = await retrieve_context(
        client,
        query_vector=query_vector,
        metadata_filters=metadata_filters,
        limit=settings.retrieval_top_k_candidates,
    )
    reranker = get_reranker()
    if reranker and candidates:
        chunks = await reranker.rerank(message, candidates, top_k=settings.retrieval_top_k_final)
    else:
        chunks = candidates[: settings.retrieval_top_k_final]
    retrieval_ms = (time.monotonic() - t0) * 1000

    if not chunks:
        yield "A literatura técnica indexada não fornece evidência suficiente para responder a esta questão.", None
        yield "", []
        get_store().add(RequestMetric(request_id=rid, retrieval_latency_ms=retrieval_ms, llm_latency_ms=0.0, cited=False, error=False))
        return

    citations = [
        Citation(
            source=chunk.source,
            chapter=chunk.chapter,
            section=chunk.section,
            page=chunk.page,
            excerpt=chunk.text[:220],
        )
        for chunk in chunks
    ]
    cited = bool(citations)

    t1 = time.monotonic()
    async for token in stream_answer(message, [chunk.text for chunk in chunks]):
        yield token, None
    llm_ms = (time.monotonic() - t1) * 1000

    yield "", citations

    get_store().add(
        RequestMetric(
            request_id=rid,
            retrieval_latency_ms=retrieval_ms,
            llm_latency_ms=llm_ms,
            cited=cited,
            error=False,
        )
    )
