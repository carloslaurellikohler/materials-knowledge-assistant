from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.retrieval import RetrievedChunk


def _make_chunks(n: int) -> list[RetrievedChunk]:
    return [
        RetrievedChunk(source=f"doc{i}.pdf", text=f"Chunk text {i}", page=i)
        for i in range(n)
    ]


@pytest.mark.asyncio
async def test_reranker_reorders_by_score():
    from app.services.reranking import CohereReranker

    chunks = _make_chunks(3)

    mock_result_0 = MagicMock(index=2, relevance_score=0.9)
    mock_result_1 = MagicMock(index=0, relevance_score=0.7)
    mock_result_2 = MagicMock(index=1, relevance_score=0.3)
    mock_response = MagicMock(results=[mock_result_0, mock_result_1, mock_result_2])

    mock_client = AsyncMock()
    mock_client.rerank = AsyncMock(return_value=mock_response)

    with patch("cohere.AsyncClientV2", return_value=mock_client):
        reranker = CohereReranker(api_key="test-key", model="rerank-english-v3.0")
        reranker._client = mock_client

    result = await reranker.rerank("corrosion in steel", chunks, top_k=3)

    assert len(result) == 3
    assert result[0].source == "doc2.pdf"
    assert result[1].source == "doc0.pdf"
    assert result[2].source == "doc1.pdf"


@pytest.mark.asyncio
async def test_reranker_respects_top_k():
    from app.services.reranking import CohereReranker

    chunks = _make_chunks(5)

    mock_results = [MagicMock(index=i, relevance_score=1.0 - i * 0.1) for i in range(3)]
    mock_response = MagicMock(results=mock_results)

    mock_client = AsyncMock()
    mock_client.rerank = AsyncMock(return_value=mock_response)

    with patch("cohere.AsyncClientV2", return_value=mock_client):
        reranker = CohereReranker(api_key="test-key", model="rerank-english-v3.0")
        reranker._client = mock_client

    result = await reranker.rerank("query", chunks, top_k=3)

    assert len(result) == 3
    _, kwargs = mock_client.rerank.call_args
    assert kwargs.get("top_n") == 3 or mock_client.rerank.call_args[0][3] == 3  # top_n=3


@pytest.mark.asyncio
async def test_reranker_empty_chunks_returns_empty():
    from app.services.reranking import CohereReranker

    mock_client = AsyncMock()
    with patch("cohere.AsyncClientV2", return_value=mock_client):
        reranker = CohereReranker(api_key="test-key", model="rerank-english-v3.0")
        reranker._client = mock_client

    result = await reranker.rerank("query", [], top_k=5)

    assert result == []
    mock_client.rerank.assert_not_called()


def test_get_reranker_returns_none_when_no_api_key():
    from app.services.reranking import get_reranker
    import app.services.reranking as reranking_module

    original = reranking_module._reranker
    reranking_module._reranker = None

    with patch("app.services.reranking.settings") as mock_settings:
        mock_settings.cohere_api_key = ""
        mock_settings.reranker_model = "rerank-english-v3.0"
        result = get_reranker()

    reranking_module._reranker = original
    assert result is None


def test_get_reranker_instantiates_when_key_present():
    from app.services.reranking import get_reranker
    import app.services.reranking as reranking_module

    original = reranking_module._reranker
    reranking_module._reranker = None

    with (
        patch("app.services.reranking.settings") as mock_settings,
        patch("cohere.AsyncClientV2"),
    ):
        mock_settings.cohere_api_key = "test-cohere-key"
        mock_settings.reranker_model = "rerank-english-v3.0"
        result = get_reranker()

    reranking_module._reranker = original
    assert result is not None
