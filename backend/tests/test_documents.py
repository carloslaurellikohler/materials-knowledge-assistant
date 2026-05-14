from app.services.documents import list_books


def test_list_books_returns_list() -> None:
    assert isinstance(list_books(), list)

