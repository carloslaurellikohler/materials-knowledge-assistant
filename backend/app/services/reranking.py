from __future__ import annotations

from app.core.config import settings
from app.services.retrieval import RetrievedChunk


class CohereReranker:
    def __init__(self, api_key: str, model: str) -> None:
        import cohere
        self._client = cohere.AsyncClientV2(api_key=api_key)
        self._model = model

    async def rerank(self, query: str, chunks: list[RetrievedChunk], top_k: int) -> list[RetrievedChunk]:
        if not chunks:
            return []
        documents = [chunk.text for chunk in chunks]
        response = await self._client.rerank(
            model=self._model,
            query=query,
            documents=documents,
            top_n=min(top_k, len(chunks)),
        )
        return [chunks[result.index] for result in response.results]


_reranker: CohereReranker | None = None


def get_reranker() -> CohereReranker | None:
    global _reranker
    if _reranker is None and settings.cohere_api_key:
        _reranker = CohereReranker(settings.cohere_api_key, settings.reranker_model)
    return _reranker
