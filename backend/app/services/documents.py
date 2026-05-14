from pathlib import Path

from app.core.config import settings


def list_books() -> list[str]:
    books_dir = Path(settings.books_dir)
    if not books_dir.exists():
        return []
    return sorted([p.name for p in books_dir.glob("*.pdf")])

