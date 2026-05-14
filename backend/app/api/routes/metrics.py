from fastapi import APIRouter

from app.core.metrics_store import get_store

router = APIRouter(tags=["metrics"])


@router.get("/metrics")
async def metrics() -> dict:
    return get_store().get_summary()
