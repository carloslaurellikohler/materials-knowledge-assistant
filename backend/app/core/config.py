from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "MKA Backend"
    app_env: str = "dev"
    api_prefix: str = "/api/v1"
    clerk_jwks_url: str = ""
    clerk_jwt_secret: str = "dev-secret"
    openai_api_key: str = ""
    openai_embedding_model: str = "text-embedding-3-small"
    openai_chat_model: str = "gpt-5.4"
    openai_vision_model: str = "gpt-4o"
    openai_whisper_model: str = "whisper-1"
    qdrant_url: str = "http://localhost:6333"
    qdrant_collection: str = "engineering_documents"
    qdrant_vector_size: int = 1536
    redis_url: str = "redis://localhost:6379/0"
    books_dir: str = "livros"
    max_upload_mb: int = 100
    max_image_upload_mb: int = 20
    max_audio_upload_mb: int = 25
    retrieval_top_k_candidates: int = 20
    retrieval_top_k_final: int = 5
    cohere_api_key: str = ""
    reranker_model: str = "rerank-english-v3.0"
    sparse_retrieval_enabled: bool = False
    ocr_backend: str = "none"  # "none" | "vision"
    ocr_min_chars: int = 50


settings = Settings()
