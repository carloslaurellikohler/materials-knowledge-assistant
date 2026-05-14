import json
from collections.abc import AsyncGenerator

from fastapi import APIRouter, Depends, Request
from qdrant_client import AsyncQdrantClient
from sse_starlette import EventSourceResponse

from app.api.deps import get_current_user, get_qdrant_client
from app.api.schemas.chat import ChatRequest
from app.services.chat import stream_chat

router = APIRouter(tags=["chat"])


async def _stream_events(
    client: AsyncQdrantClient,
    payload: ChatRequest,
    request_id: str | None,
) -> AsyncGenerator[dict, None]:
    async for token, citations in stream_chat(client, payload.message, payload.metadata_filters, request_id=request_id):
        if citations is not None:
            yield {"event": "citations", "data": json.dumps([c.model_dump() for c in citations])}
        else:
            yield {"event": "token", "data": token}
    yield {"event": "done", "data": "ok"}


@router.post("/chat")
async def chat(
    request: Request,
    payload: ChatRequest,
    _: dict = Depends(get_current_user),
    client: AsyncQdrantClient = Depends(get_qdrant_client),
) -> EventSourceResponse:
    request_id = getattr(request.state, "request_id", None)
    return EventSourceResponse(_stream_events(client, payload, request_id))
