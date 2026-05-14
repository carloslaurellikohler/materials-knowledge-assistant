import pytest
from unittest.mock import AsyncMock, patch

from app.api.schemas.chat import Citation
from app.services.retrieval import RetrievedChunk


@pytest.fixture
def mock_client():
    return AsyncMock()


@pytest.fixture
def sample_chunk():
    return RetrievedChunk(source="callister.pdf", text="Carbon steel corrodes in marine environments.", page=42)


async def _collect_stream(gen):
    results = []
    async for item in gen:
        results.append(item)
    return results


async def fake_stream_answer(query, context_chunks):
    for token in ["Carbon", " steel", " corrodes."]:
        yield token


@pytest.mark.asyncio
async def test_stream_chat_yields_tokens_then_citations(mock_client, sample_chunk):
    from app.services.chat import stream_chat

    with (
        patch("app.services.chat.embed_texts", return_value=[[0.1] * 1536]),
        patch("app.services.chat.retrieve_context", return_value=[sample_chunk]),
        patch("app.services.chat.stream_answer", fake_stream_answer),
    ):
        results = await _collect_stream(stream_chat(mock_client, "What corrodes?", {}))

    tokens = [token for token, citations in results if citations is None]
    final = [(token, citations) for token, citations in results if citations is not None]

    assert tokens == ["Carbon", " steel", " corrodes."]
    assert len(final) == 1
    _, citations = final[0]
    assert len(citations) == 1
    assert isinstance(citations[0], Citation)
    assert citations[0].source == "callister.pdf"
    assert citations[0].page == 42
    assert citations[0].excerpt.startswith("Carbon steel")


@pytest.mark.asyncio
async def test_stream_chat_empty_retrieval_yields_fallback(mock_client):
    from unittest.mock import MagicMock
    from app.services.chat import stream_chat

    mock_stream_answer = MagicMock()

    with (
        patch("app.services.chat.embed_texts", return_value=[[0.0] * 1536]),
        patch("app.services.chat.retrieve_context", return_value=[]),
        patch("app.services.chat.stream_answer", mock_stream_answer),
    ):
        results = await _collect_stream(stream_chat(mock_client, "unknown query", {}))

    mock_stream_answer.assert_not_called()

    tokens = [token for token, citations in results if citations is None]
    final = [(token, citations) for token, citations in results if citations is not None]

    assert len(tokens) == 1
    assert "não fornece evidência suficiente" in tokens[0]
    assert len(final) == 1
    _, citations = final[0]
    assert citations == []


@pytest.mark.asyncio
async def test_stream_chat_calls_embed_with_message(mock_client, sample_chunk):
    from app.services.chat import stream_chat

    with (
        patch("app.services.chat.embed_texts", return_value=[[0.1] * 1536]) as mock_embed,
        patch("app.services.chat.retrieve_context", return_value=[sample_chunk]),
        patch("app.services.chat.stream_answer", fake_stream_answer),
    ):
        await _collect_stream(stream_chat(mock_client, "test query", {}))

    mock_embed.assert_called_once_with(["test query"])
