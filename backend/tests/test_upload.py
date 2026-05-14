import io
from pathlib import Path
from unittest.mock import MagicMock, patch

import jwt
import pytest
from fastapi.testclient import TestClient

from app.core.config import settings


@pytest.fixture
def dev_token():
    return jwt.encode({"sub": "test-user"}, settings.clerk_jwt_secret, algorithm="HS256")


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setattr("app.core.config.settings.app_env", "test")
    monkeypatch.setattr("app.core.config.settings.books_dir", str(tmp_path / "livros"))
    from app.main import app
    return TestClient(app)


def test_upload_pdf_queues_task(client, dev_token, tmp_path, monkeypatch):
    monkeypatch.setattr("app.core.config.settings.books_dir", str(tmp_path / "livros"))
    pdf_bytes = b"%PDF-1.4 minimal pdf content for testing"

    mock_task = MagicMock()
    with patch("app.api.routes.upload.ingest_single_pdf_task") as mock_task_cls:
        mock_task_cls.delay = MagicMock()
        response = client.post(
            "/api/v1/upload/pdf",
            headers={"Authorization": f"Bearer {dev_token}"},
            files={"file": ("document.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "queued"
    assert data["filename"] == "document.pdf"
    assert "request_id" in data
    mock_task_cls.delay.assert_called_once()


def test_upload_non_pdf_rejected(client, dev_token):
    response = client.post(
        "/api/v1/upload/pdf",
        headers={"Authorization": f"Bearer {dev_token}"},
        files={"file": ("image.png", io.BytesIO(b"fake image"), "image/png")},
    )
    assert response.status_code in (422, 415)


def test_upload_oversized_pdf_rejected(client, dev_token, monkeypatch):
    monkeypatch.setattr("app.core.config.settings.max_upload_mb", 1)
    big_content = b"%PDF-1.4 " + b"x" * (2 * 1024 * 1024)

    with patch("app.api.routes.upload.ingest_single_pdf_task"):
        response = client.post(
            "/api/v1/upload/pdf",
            headers={"Authorization": f"Bearer {dev_token}"},
            files={"file": ("big.pdf", io.BytesIO(big_content), "application/pdf")},
        )

    assert response.status_code == 413


def test_upload_requires_auth(client):
    response = client.post(
        "/api/v1/upload/pdf",
        files={"file": ("doc.pdf", io.BytesIO(b"%PDF-1.4"), "application/pdf")},
    )
    assert response.status_code == 401
