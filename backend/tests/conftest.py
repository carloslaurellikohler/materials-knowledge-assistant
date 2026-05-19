import pytest


@pytest.fixture(autouse=True)
def _isolate_test_env(monkeypatch):
    # Force HS256 fallback in app.api.deps even when developer .env defines CLERK_JWKS_URL.
    monkeypatch.setattr("app.core.config.settings.clerk_jwks_url", "")
    # Prevent CohereReranker from instantiating a real httpx client whose teardown
    # outlives the per-test event loop (causes "Event loop is closed" in __del__).
    monkeypatch.setattr("app.core.config.settings.cohere_api_key", "")

    # Reset module-level singletons that may have captured a previous setting value.
    import app.api.deps as deps
    import app.services.reranking as reranking

    deps._get_jwks_client.cache_clear()
    reranking._reranker = None
