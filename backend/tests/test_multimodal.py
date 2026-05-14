import io
from unittest.mock import AsyncMock, patch

import jwt
import pytest
from fastapi.testclient import TestClient

from app.core.config import settings


@pytest.fixture
def dev_token():
    return jwt.encode({"sub": "test-user"}, settings.clerk_jwt_secret, algorithm="HS256")


@pytest.fixture
def client():
    from app.main import app
    return TestClient(app)


def test_upload_image_returns_description(client, dev_token):
    with patch(
        "app.api.routes.multimodal.describe_image",
        new=AsyncMock(return_value="Corrosion visible on carbon steel surface."),
    ) as mock_desc:
        response = client.post(
            "/api/v1/upload/image",
            headers={"Authorization": f"Bearer {dev_token}"},
            files={"file": ("corrosion.jpg", io.BytesIO(b"fake image bytes"), "image/jpeg")},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "analyzed"
    assert data["description"] == "Corrosion visible on carbon steel surface."
    assert data["filename"] == "corrosion.jpg"
    mock_desc.assert_called_once()


def test_upload_image_passes_mime_type(client, dev_token):
    with patch(
        "app.api.routes.multimodal.describe_image",
        new=AsyncMock(return_value="Steel surface with oxide layer."),
    ) as mock_desc:
        client.post(
            "/api/v1/upload/image",
            headers={"Authorization": f"Bearer {dev_token}"},
            files={"file": ("diagram.png", io.BytesIO(b"png bytes"), "image/png")},
        )

    call_args = mock_desc.call_args
    assert call_args[0][1] == "image/png"


def test_upload_audio_returns_transcript(client, dev_token):
    with patch(
        "app.api.routes.multimodal.transcribe_audio",
        new=AsyncMock(return_value="What is the corrosion rate of carbon steel in marine environments?"),
    ) as mock_trans:
        response = client.post(
            "/api/v1/upload/audio",
            headers={"Authorization": f"Bearer {dev_token}"},
            files={"file": ("query.mp3", io.BytesIO(b"fake audio bytes"), "audio/mpeg")},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "transcribed"
    assert data["transcript"] == "What is the corrosion rate of carbon steel in marine environments?"
    assert data["filename"] == "query.mp3"
    mock_trans.assert_called_once()


def test_upload_audio_passes_filename_to_transcriber(client, dev_token):
    with patch(
        "app.api.routes.multimodal.transcribe_audio",
        new=AsyncMock(return_value="test transcript"),
    ) as mock_trans:
        client.post(
            "/api/v1/upload/audio",
            headers={"Authorization": f"Bearer {dev_token}"},
            files={"file": ("my_query.wav", io.BytesIO(b"wav bytes"), "audio/wav")},
        )

    call_args = mock_trans.call_args
    assert call_args[0][1] == "my_query.wav"


def test_upload_image_oversized_rejected(client, dev_token, monkeypatch):
    monkeypatch.setattr("app.core.config.settings.max_image_upload_mb", 1)
    big_content = b"JFIF" + b"x" * (2 * 1024 * 1024)

    with patch("app.api.routes.multimodal.describe_image", new=AsyncMock(return_value="")):
        response = client.post(
            "/api/v1/upload/image",
            headers={"Authorization": f"Bearer {dev_token}"},
            files={"file": ("big.jpg", io.BytesIO(big_content), "image/jpeg")},
        )

    assert response.status_code == 413


def test_upload_audio_oversized_rejected(client, dev_token, monkeypatch):
    monkeypatch.setattr("app.core.config.settings.max_audio_upload_mb", 1)
    big_content = b"ID3" + b"x" * (2 * 1024 * 1024)

    with patch("app.api.routes.multimodal.transcribe_audio", new=AsyncMock(return_value="")):
        response = client.post(
            "/api/v1/upload/audio",
            headers={"Authorization": f"Bearer {dev_token}"},
            files={"file": ("big.mp3", io.BytesIO(big_content), "audio/mpeg")},
        )

    assert response.status_code == 413


def test_upload_image_requires_auth(client):
    response = client.post(
        "/api/v1/upload/image",
        files={"file": ("test.jpg", io.BytesIO(b"data"), "image/jpeg")},
    )
    assert response.status_code == 401


def test_upload_audio_requires_auth(client):
    response = client.post(
        "/api/v1/upload/audio",
        files={"file": ("test.mp3", io.BytesIO(b"data"), "audio/mpeg")},
    )
    assert response.status_code == 401
