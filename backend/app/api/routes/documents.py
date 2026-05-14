from fastapi import APIRouter, Depends

from app.api.deps import get_current_user
from app.api.schemas.documents import DocumentItem
from app.services.documents import list_books

router = APIRouter(tags=["documents"])


@router.get("/documents", response_model=list[DocumentItem])
async def documents(_: dict = Depends(get_current_user)) -> list[DocumentItem]:
    # Keep read-only corpus visibility for clients.
    return [DocumentItem(source=name, indexed=True) for name in list_books()]
