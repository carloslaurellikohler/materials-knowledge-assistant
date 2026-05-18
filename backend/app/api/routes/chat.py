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
    user_id: str | None,
) -> AsyncGenerator[dict, None]:
    import logging
    logger = logging.getLogger(__name__)
    try:
        async for token, citations in stream_chat(client, payload.message, payload.metadata_filters, request_id=request_id, user_id=user_id):
            if citations is not None:
                yield {"event": "citations", "data": json.dumps([c.model_dump() for c in citations])}
            else:
                yield {"event": "token", "data": token}
        yield {"event": "done", "data": "ok"}
    except Exception as exc:
        logger.exception("stream_chat error: %s", exc)
        yield {"event": "error", "data": str(exc)}


@router.post("/chat")
async def chat(
    request: Request,
    payload: ChatRequest,
    current_user: dict = Depends(get_current_user),
    client: AsyncQdrantClient = Depends(get_qdrant_client),
) -> EventSourceResponse:
    request_id = getattr(request.state, "request_id", None)
    user_id = current_user.get("sub")
    return EventSourceResponse(_stream_events(client, payload, request_id, user_id))
