from __future__ import annotations

from collections.abc import AsyncIterator

from openai import AsyncOpenAI, OpenAI

from app.core.config import settings
from app.rag.prompts import SYSTEM_PROMPT, VISION_PROMPT

_MAX_BATCH = 256
_MAX_CHARS = 30_000  # ~7500 tokens at 4 chars/token — safely below 8192 token limit


def _safe_truncate(texts: list[str]) -> list[str]:
    return [t[:_MAX_CHARS] for t in texts]

_async_client: AsyncOpenAI | None = None
_sync_client: OpenAI | None = None


def _get_async() -> AsyncOpenAI:
    global _async_client
    if _async_client is None:
        _async_client = AsyncOpenAI(api_key=settings.openai_api_key)
    return _async_client


def _get_sync() -> OpenAI:
    global _sync_client
    if _sync_client is None:
        _sync_client = OpenAI(api_key=settings.openai_api_key)
    return _sync_client


async def embed_texts(texts: list[str]) -> list[list[float]]:
    """Async batch embedding for chat service."""
    client = _get_async()
    all_vectors: list[list[float]] = []
    for i in range(0, len(texts), _MAX_BATCH):
        batch = _safe_truncate(texts[i : i + _MAX_BATCH])
        response = await client.embeddings.create(
            model=settings.openai_embedding_model,
            input=batch,
        )
        all_vectors.extend(item.embedding for item in response.data)
    return all_vectors


def embed_texts_sync(texts: list[str]) -> list[list[float]]:
    """Synchronous batch embedding for Celery tasks and CLI."""
    client = _get_sync()
    all_vectors: list[list[float]] = []
    for i in range(0, len(texts), _MAX_BATCH):
        batch = _safe_truncate(texts[i : i + _MAX_BATCH])
        response = client.embeddings.create(
            model=settings.openai_embedding_model,
            input=batch,
        )
        all_vectors.extend(item.embedding for item in response.data)
    return all_vectors


async def describe_image(image_bytes: bytes, mime_type: str) -> str:
    """Describe an engineering image using GPT-4o vision."""
    import base64
    import io as _io

    client = _get_async()
    b64 = base64.b64encode(image_bytes).decode("utf-8")
    data_url = f"data:{mime_type};base64,{b64}"
    response = await client.chat.completions.create(
        model=settings.openai_vision_model,
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": data_url}},
                    {"type": "text", "text": VISION_PROMPT},
                ],
            }
        ],
        max_tokens=500,
    )
    return response.choices[0].message.content or ""


async def transcribe_audio(audio_bytes: bytes, filename: str) -> str:
    """Transcribe audio to text using Whisper."""
    import io as _io

    client = _get_async()
    audio_file = _io.BytesIO(audio_bytes)
    audio_file.name = filename
    response = await client.audio.transcriptions.create(
        model=settings.openai_whisper_model,
        file=audio_file,
    )
    return response.text


async def stream_answer(query: str, context_chunks: list[str]) -> AsyncIterator[str]:
    """Stream GPT tokens grounded strictly in retrieved context chunks."""
    client = _get_async()
    context = "\n\n---\n\n".join(context_chunks)
    system = SYSTEM_PROMPT.format(context=context)
    stream = await client.chat.completions.create(
        model=settings.openai_chat_model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": query},
        ],
        stream=True,
    )
    async for chunk in stream:
        token = chunk.choices[0].delta.content
        if token:
            yield token
