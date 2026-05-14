import logging
import uuid
from collections.abc import AsyncGenerator
from functools import lru_cache

import jwt
from fastapi import Depends, Header, HTTPException, Request, status
from jwt import PyJWKClient
from qdrant_client import AsyncQdrantClient

from app.core.config import settings

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def _get_jwks_client() -> PyJWKClient:
    return PyJWKClient(settings.clerk_jwks_url)


def _decode_token(token: str) -> dict:
    if settings.clerk_jwks_url:
        signing_key = _get_jwks_client().get_signing_key_from_jwt(token)
        return jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            options={"verify_aud": False},
        )
    # Fallback HS256 para dev/test — emite warning fora desses ambientes
    if settings.app_env not in ("dev", "test"):
        logger.warning(
            "CLERK_JWKS_URL não configurada — usando HS256 inseguro. "
            "Defina CLERK_JWKS_URL para validação RS256 em produção."
        )
    return jwt.decode(token, settings.clerk_jwt_secret, algorithms=["HS256"])


def get_request_id(request: Request) -> str:
    request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
    request.state.request_id = request_id
    return request_id


def get_current_user(authorization: str = Header(default="")) -> dict:
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token")
    token = authorization.split(" ", 1)[1]
    try:
        payload = _decode_token(token)
        return {"sub": payload.get("sub", "unknown")}
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token") from exc


async def get_qdrant_client() -> AsyncGenerator[AsyncQdrantClient, None]:
    client = AsyncQdrantClient(url=settings.qdrant_url)
    try:
        yield client
    finally:
        await client.close()


AuthenticatedUser = Depends(get_current_user)
RequestId = Depends(get_request_id)
QdrantClientDep = Depends(get_qdrant_client)
