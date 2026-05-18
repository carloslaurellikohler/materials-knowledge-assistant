# Backend Specification (BES)
## Materials Knowledge Assistant (MKA)

Version: 2.0
Status: Aligned with current implementation
Author: Carlos Eduardo
Date: May 2026

---

# 1. Purpose

This document defines the backend implementation specification for the Materials Knowledge Assistant (MKA).

The specification reflects the implementation as of May 2026 and translates the architectural decisions defined in the PRD, SAD, and RAG Architecture Specification into actionable backend engineering guidelines.

The backend is responsible for:

- API exposure (HTTP + SSE)
- AI orchestration (direct OpenAI SDK calls)
- Retrieval execution with mandatory per-user filtering
- Document lifecycle management (CRUD over `/documents`)
- Asynchronous PDF ingestion via Celery
- Object storage (Supabase) and relational persistence (PostgreSQL)
- Embedding generation
- Citation formatting
- Authentication validation (Clerk JWTs)
- Multimodal processing (image, audio)
- Observability, logging, and metrics

---

# 2. Backend Technology Stack

| Layer | Technology |
|---|---|
| API Framework | FastAPI |
| Language | Python 3.12+ |
| Validation | Pydantic 2 + pydantic-settings |
| AI Orchestration | OpenAI SDK directly (no LangChain) |
| Async Runtime | Uvicorn |
| Background Processing | Celery + Redis 7 |
| Vector Database | Qdrant v1.11.3 (`qdrant-client`) |
| Relational Database | PostgreSQL 16 + SQLAlchemy 2.0 (`asyncpg` async, `psycopg2-binary` sync) |
| Migrations | Alembic (installed, not actively used) |
| Object Storage | Supabase Storage (`supabase-py`) |
| Embeddings | OpenAI `text-embedding-3-small` (1536-d) |
| LLM provider | OpenAI |
| Reranking | Cohere (`cohere>=5.0.0`) — optional |
| PDF parsing | `pypdf` + `pymupdf` |
| JWT | `PyJWT[crypto]` |
| Containerization | Docker |
| Dependency Management | `uv` (`pyproject.toml`) |
| Observability | Structured logs via `logging` + in-memory metrics ring buffer |

---

# 3. Backend Architectural Principles

The backend implementation prioritizes:

- Stateless APIs (no per-session state on the server)
- Modular services with single responsibilities
- Async-first processing (FastAPI + async SQLAlchemy + async OpenAI)
- Strong typing (Pydantic schemas, ORM models, typed services)
- Structured observability (request IDs propagated end-to-end)
- Clear separation between HTTP-sync work and Celery-async work
- Retrieval-grounded AI responses (empty-context guard, citation enforcement)
- Per-user isolation enforced at the data layer

---

# 4. Project Structure

```text
backend/
│
├── app/
│   ├── api/
│   │   ├── deps.py                      # auth (Clerk JWT), Qdrant/DB dependencies
│   │   ├── routes/
│   │   │   ├── chat.py                  # POST /chat (SSE)
│   │   │   ├── documents.py             # POST/GET/GET-{id}/DELETE /documents
│   │   │   ├── health.py                # GET /health
│   │   │   ├── metrics.py               # GET /metrics
│   │   │   └── multimodal.py            # POST /upload/image|audio
│   │   └── schemas/                     # Pydantic schemas (chat, documents, error)
│   │
│   ├── core/
│   │   ├── config.py                    # Settings (pydantic-settings)
│   │   ├── logging.py                   # structured logging configuration
│   │   └── metrics_store.py             # ring buffer for /metrics
│   │
│   ├── db/
│   │   ├── database.py                  # async + sync engines, sessions, create_tables
│   │   └── models.py                    # SQLAlchemy 2.0 ORM (Document)
│   │
│   ├── storage/
│   │   ├── provider.py                  # Protocol StorageProvider
│   │   └── supabase_provider.py         # Supabase implementation
│   │
│   ├── integrations/
│   │   └── openai_client.py             # embed_texts, stream_answer, describe_image, transcribe_audio
│   │
│   ├── rag/
│   │   └── prompts.py                   # SYSTEM_PROMPT, VISION_PROMPT
│   │
│   ├── services/
│   │   ├── chat.py                      # orchestration: embed → retrieve → rerank → stream
│   │   ├── ingestion.py                 # chunking, metadata, OCR, status callback
│   │   ├── reranking.py                 # CohereReranker (optional)
│   │   └── retrieval.py                 # Qdrant query with user_id filter
│   │
│   ├── workers/
│   │   ├── celery_app.py                # Celery configuration
│   │   └── tasks.py                     # mka.ingest_document, mka.reindex_books, mka.ingest_single_pdf
│   │
│   └── main.py                          # FastAPI app, lifespan, middleware, routers
│
├── tests/                                # pytest-asyncio suite (APP_ENV=test)
├── reindex_corpus.py                     # admin CLI (corpus base; no user_id)
├── livros/                               # admin corpus directory (gitignored)
├── Dockerfile
└── pyproject.toml
```

Note: `app/api/routes/upload.py` exists in the codebase but is **not registered** in `main.py` and is therefore not exposed (dead code).

---

# 5. API Specification

## 5.1 Base URL

```text
/api/v1
```

CORS is restricted to `http://localhost:3000` and `http://127.0.0.1:3000` (Next.js dev origin). All cross-origin requests typically reach the backend via the Next.js proxy at `frontend/app/api/v1/[...path]/route.ts`.

---

## 5.2 Endpoints

| Method | Endpoint | Auth | Code location |
|---|---|---|---|
| `GET` | `/health` | No | `routes/health.py` |
| `GET` | `/metrics` | No | `routes/metrics.py` |
| `POST` | `/chat` | Yes | `routes/chat.py` |
| `POST` | `/documents` | Yes | `routes/documents.py` |
| `GET` | `/documents` | Yes | `routes/documents.py` |
| `GET` | `/documents/{id}` | Yes | `routes/documents.py` |
| `DELETE` | `/documents/{id}` | Yes | `routes/documents.py` |
| `POST` | `/upload/image` | Yes | `routes/multimodal.py` |
| `POST` | `/upload/audio` | Yes | `routes/multimodal.py` |

> `POST /upload/pdf` was the V1.0 ingestion endpoint and is no longer exposed. The current upload flow is `POST /documents` with asynchronous Celery ingestion.

---

## 5.3 Common HTTP Concerns

- **Authentication**: every protected route depends on `get_current_user` from `api/deps.py`, which validates the bearer JWT (Clerk RS256 via JWKS in prod, HS256 fallback in dev/test).
- **Request ID**: a middleware (`attach_request_id`) injects `request.state.request_id`, using the `x-request-id` header when supplied or generating a new UUID. The header is echoed back in the response.
- **Error envelope**: unhandled exceptions become HTTP 500 with the `ErrorResponse` schema:
  ```json
  {
    "error": {
      "code": "INTERNAL_ERROR",
      "message": "An unexpected error occurred.",
      "request_id": "..."
    }
  }
  ```
- **Lifespan**: `create_tables()` is awaited on startup, ensuring the `documents` table exists. The lifespan also enforces `OPENAI_API_KEY` is set when `APP_ENV != "test"`.

---

# 6. Authentication Specification

## 6.1 Authentication Strategy

Authentication uses:

- Clerk identity provider (Google, email, etc.)
- JWT bearer tokens validated by the backend

| Environment | Algorithm | Key source |
|---|---|---|
| Production | RS256 | `CLERK_JWKS_URL` (Clerk JWKS endpoint) |
| Dev / test | HS256 | `CLERK_JWT_SECRET` (default `dev-secret`) |

The frontend can additionally toggle Clerk on/off via `NEXT_PUBLIC_ENABLE_CLERK`.

---

## 6.2 Backend Responsibilities

The backend must:

- Validate the JWT signature and expiration
- Extract `user_id` (from the `sub` claim)
- Inject `current_user` into route handlers via FastAPI dependency
- Reject unauthenticated requests with HTTP 401

---

## 6.3 Protected Routes

The following routes require authentication:

- `POST /chat`
- `POST/GET/GET-{id}/DELETE /documents` (every CRUD operation)
- `POST /upload/image`
- `POST /upload/audio`

The endpoints `/health` and `/metrics` are public.

---

# 7. Chat Service Specification

## 7.1 Responsibilities

The Chat Service (`backend/app/services/chat.py:stream_chat`) is responsible for:

- Receiving the user prompt and optional metadata filters
- Embedding the query
- Executing retrieval with the **mandatory `user_id` filter**
- Applying optional Cohere rerank
- Short-circuiting on empty context
- Streaming the LLM response over SSE
- Emitting citations after the final token
- Pushing latency metrics into the in-memory ring buffer

---

## 7.2 Request Schema (`schemas/chat.py:ChatRequest`)

```json
{
  "message": "What corrosion risks exist for carbon steel in marine environments?",
  "attachments": [],
  "metadata_filters": {
    "material_type": "steel"
  }
}
```

| Field | Type | Notes |
|---|---|---|
| `message` | `str` (min length 1) | Required |
| `attachments` | `list[dict[str, Any]]` | Reserved; currently unused |
| `metadata_filters` | `dict[str, Any]` | Combined with `user_id` via `must` clauses |

---

## 7.3 Response (SSE Events)

The `/chat` response is a Server-Sent Events stream:

| Event | Payload | Frequency |
|---|---|---|
| `token` | partial answer string | N times (streaming) |
| `citations` | JSON array of `Citation` objects | once, before `done` |
| `done` | sentinel string (`ok`) | once, at the end |
| `error` | error message | on failure |

`Citation` schema (`schemas/chat.py:Citation`):

```json
{
  "source": "callister_materials_science.pdf",
  "chapter": "Corrosion",
  "section": "Galvanic Corrosion",
  "page": 248,
  "excerpt": "Carbon steel exposed to chloride-rich marine environments..."
}
```

---

## 7.4 Streaming Strategy

Responses are streamed using Server-Sent Events (`sse-starlette`). The OpenAI streaming API is consumed asynchronously; tokens are forwarded immediately to the client.

Benefits:

- Better UX
- Lower perceived latency
- Faster interaction cycles

---

# 8. Retrieval Service Specification

## 8.1 Responsibilities

The Retrieval Service (`backend/app/services/retrieval.py:retrieve_context`) must:

- Accept a query vector and optional metadata filters
- Build a Qdrant `Filter(must=[...])` that ALWAYS includes a `user_id` clause
- Execute an async vector search (`client.query_points`)
- Return typed `RetrievedChunk` objects

---

## 8.2 Retrieval Pipeline

```text
User Query (authenticated)
    ↓
Query Embedding (text-embedding-3-small, 1536-d)
    ↓
Qdrant Dense Search (must={user_id, ...metadata_filters}, top-K)
    ↓
[optional] Cohere Re-ranking (when COHERE_API_KEY is set)
    ↓
Top-N Selection
```

---

## 8.3 Retrieval Parameters

| Parameter | Default | Env var |
|---|---|---|
| Initial Candidates | 20 | `RETRIEVAL_TOP_K_CANDIDATES` |
| Final Chunks | 5 | `RETRIEVAL_TOP_K_FINAL` |
| Similarity Metric | Cosine | (Qdrant) |
| Chunk Size | ~1,200 words | code constant |
| Chunk Overlap | ~200 words | code constant |
| Vector Size | 1536 | `QDRANT_VECTOR_SIZE` |

---

# 9. Document Service Specification

The Document Service is implemented in `backend/app/api/routes/documents.py`.

## 9.1 POST /api/v1/documents

| Aspect | Detail |
|---|---|
| Auth | Required (Clerk JWT) |
| Body | `multipart/form-data` with field `file` (PDF) |
| Size limit | `MAX_UPLOAD_MB` (default 100 MB) |
| Side effects | Uploads to Supabase, inserts row in `documents` (`pending`), enqueues `mka.ingest_document(document_id)` |
| Response | HTTP 202 with `{ document_id, indexing_status }` |

Sequence:

1. Validate MIME and size.
2. Sanitize filename.
3. Generate `document_id` (UUID).
4. Upload bytes to Supabase at `{user_id}/{document_id}/{sanitized_filename}`.
5. Insert a `Document` row with status `pending`.
6. Dispatch `ingest_document_task` to Celery.
7. Return 202.

## 9.2 GET /api/v1/documents

| Aspect | Detail |
|---|---|
| Auth | Required |
| Response | `list[DocumentResponse]` ordered by `created_at DESC` |
| Filter | `WHERE user_id = current_user.user_id` |

## 9.3 GET /api/v1/documents/{document_id}

| Aspect | Detail |
|---|---|
| Auth | Required |
| Ownership | Enforced — 404 if the document is not owned by `current_user` |
| Response | `DocumentResponse` |
| Usage | Frontend polls this endpoint every 3 seconds until a terminal status |

## 9.4 DELETE /api/v1/documents/{document_id}

| Aspect | Detail |
|---|---|
| Auth | Required |
| Ownership | Enforced |
| Response | HTTP 204 |
| Cascade | (1) Qdrant vectors filtered by `document_id`; (2) Supabase blob; (3) Postgres row |

---

# 10. Ingestion Service Specification

The Ingestion Service is implemented in `backend/app/services/ingestion.py`.

## 10.1 Responsibilities

The Ingestion Service must:

- Accept PDF bytes plus identifiers (`user_id`, `document_id`)
- Extract pages (pypdf, OCR fallback via GPT-4o when `OCR_BACKEND=vision`)
- Apply structural chunking
- Generate embeddings in batches
- Upsert vectors into Qdrant with rich payload (including `user_id` and `document_id`)
- Notify status updates via a callback

---

## 10.2 Ingestion Pipeline (Sync + Async)

```text
HTTP path (sync, returns 202)             Worker path (mka.ingest_document)
─────────────────────────────             ───────────────────────────────────
POST /api/v1/documents                     status → "processing"
   ↓                                          ↓
Validate MIME + size                       Download blob from Supabase
   ↓                                          ↓
Sanitize filename                          Extract pages (pypdf, OCR opt-in)
   ↓                                          ↓
Upload bytes to Supabase                   Structural chunking         → "chunking"
   ↓                                          ↓
Insert documents row (pending)             Embed chunks in batches     → "embedding"
   ↓                                          ↓
Enqueue mka.ingest_document                Upsert into Qdrant (payload includes
   ↓                                          user_id, document_id, page, etc.)
Return 202                                    ↓
                                           Update row → "indexed" | "error"
```

## 10.3 Status Callback Contract

`ingest_pdf_bytes(pdf_bytes, filename, user_id, document_id, status_callback)` invokes `status_callback(status: str)` at each transition. The Celery task wires this callback to a synchronous DB update so the document row reflects progress in near-real-time.

Transitions:

```
pending → processing → chunking → embedding → indexed
                                    │
                                    └─ (on exception) → error
```

## 10.4 File Validation Rules

| Rule | Requirement |
|---|---|
| Accepted Format | `application/pdf` |
| Max File Size | `MAX_UPLOAD_MB` (default 100 MB) |
| Filename Sanitization | Yes (path traversal protection) |
| Duplicate Detection | Yes — SHA-256 of bytes recorded as `source_id` in Qdrant payload; admin reindex skips already-seen hashes |

## 10.5 Administrative Ingestion (Legacy)

`reindex_books()` and `ingest_single_pdf()` operate on `backend/livros/` from the filesystem and DO NOT attach a `user_id` to the resulting chunks. Use them only for shared admin corpora. Vectors ingested this way will NOT be retrievable by user-scoped queries.

---

# 11. Persistence Layer Specification

## 11.1 Database

PostgreSQL 16, accessed via SQLAlchemy 2.0.

| Context | Driver | Session |
|---|---|---|
| FastAPI handlers | `asyncpg` (async) | `AsyncSessionLocal` |
| Celery worker | `psycopg2` (sync) | `SyncSessionLocal` |

Both engines and session factories are defined in `backend/app/db/database.py`. The function `create_tables()` is awaited on app startup to ensure schema presence (`Base.metadata.create_all`).

## 11.2 `documents` Table (`backend/app/db/models.py`)

| Column | Type | Notes |
|---|---|---|
| `id` | String(36) PK | UUID generated by the backend |
| `user_id` | String(255) | Indexed |
| `filename` | String(512) | Sanitized name (storage) |
| `original_filename` | String(512) | User-provided name |
| `storage_path` | String(1024) | `{user_id}/{document_id}/{filename}` |
| `mime_type` | String(128) | Always `application/pdf` |
| `size` | Integer | Bytes |
| `indexing_status` | Enum | `pending`, `processing`, `chunking`, `embedding`, `indexed`, `error` |
| `indexing_error` | Text · nullable | Populated when `status = error` |
| `chunk_count` | Integer · nullable | Populated after `indexed` |
| `embedding_model` | String(128) · nullable | e.g., `text-embedding-3-small` |
| `qdrant_collection` | String(256) | Target collection |
| `created_at` / `updated_at` | DateTime(tz) | Auto-maintained |

## 11.3 Migrations

Schema creation uses `Base.metadata.create_all()` at startup. Alembic is installed (`alembic>=1.13`) and ready to adopt; migration revisions are not yet versioned. Adopting Alembic-managed migrations is on the Phase 2 roadmap.

---

# 12. Object Storage Specification

## 12.1 Storage Provider Protocol

`backend/app/storage/provider.py` defines a `StorageProvider` Protocol:

```python
async def upload(path: str, content: bytes, mime_type: str) -> str
async def delete(path: str) -> None
async def download(path: str) -> bytes
```

## 12.2 Supabase Implementation

`backend/app/storage/supabase_provider.py`:

- Lazy singleton via `get_storage()`
- Bucket: `SUPABASE_BUCKET` (default `mka-documents`)
- Authenticates with **`SUPABASE_KEY` set to the `service_role` secret**, NOT the anon key
- Async methods wrap the sync `supabase-py` client via `asyncio.to_thread`
- Sync variants (`sync_upload`, `sync_delete`, `sync_download`) are provided for use inside Celery workers

## 12.3 Path Convention

```
{user_id}/{document_id}/{sanitized_filename}.pdf
```

The path itself encodes ownership, which simplifies cascading deletes and audit.

---

# 13. Embedding Service Specification

## 13.1 Responsibilities

The Embedding Service (`backend/app/integrations/openai_client.py`) must:

- Batch embedding requests
- Retry failed operations (handled implicitly by the OpenAI client)
- Generate streaming chat completions
- Generate vision descriptions (GPT-4o)
- Transcribe audio (Whisper)

## 13.2 Model Strategy

| Capability | Default | Env var |
|---|---|---|
| Primary embeddings | `text-embedding-3-small` (1536-d) | `OPENAI_EMBEDDING_MODEL` |
| Chat | (see configuration note) | `OPENAI_CHAT_MODEL` |
| Vision | `gpt-4o` | `OPENAI_VISION_MODEL` |
| Audio transcription | `whisper-1` | `OPENAI_WHISPER_MODEL` |

> ⚠️ The default value of `openai_chat_model` in `backend/app/core/config.py:14` is `gpt-5.4`, which is not a published OpenAI model. Operators must override `OPENAI_CHAT_MODEL` (e.g., to `gpt-4.1`) until the default is corrected.

---

# 14. Reranking Service Specification

## 14.1 Implementation

`backend/app/services/reranking.py:CohereReranker`:

- Wraps `cohere.AsyncClientV2`
- Only instantiated when `COHERE_API_KEY` is set
- Default model: `rerank-english-v3.0` (`RERANKER_MODEL`)
- API: `rerank(query, chunks, top_k) -> list[RerankedChunk]`

## 14.2 Behavior When Disabled

If `COHERE_API_KEY` is not set, the reranker is `None` and the top-K from Qdrant is passed directly to the prompt assembly stage (limited to `RETRIEVAL_TOP_K_FINAL`).

---

# 15. Citation Service Specification

## 15.1 Responsibilities

Citations are formatted inline by `services/chat.py` using metadata from each retrieved chunk. There is no dedicated citation microservice.

The pipeline:

1. Pull `source`, `chapter`, `section`, `page`, `excerpt` from each chunk used in the final context.
2. Build the `Citation` objects (truncating the excerpt to ~220 characters).
3. Emit them via an SSE `citations` event after the final token.

## 15.2 Citation Structure (`schemas/chat.py:Citation`)

```json
{
  "source": "document.pdf",
  "chapter": "Corrosion",
  "section": "Galvanic Corrosion",
  "page": 248,
  "excerpt": "Carbon steels exposed to chloride..."
}
```

---

# 16. Multimodal Service Specification

## 16.1 Image Processing

`POST /api/v1/upload/image` accepts PNG / JPG / WebP up to `MAX_IMAGE_UPLOAD_MB` (default 20 MB). The image is sent to GPT-4o via `describe_image`, which returns a textual description.

```json
{ "status": "analyzed", "description": "Corrosão generalizada na superfície..." , "filename": "..." }
```

The user may take that description and send it as a follow-up `/chat` query.

## 16.2 Audio Processing

`POST /api/v1/upload/audio` accepts MP3 / WAV / M4A up to `MAX_AUDIO_UPLOAD_MB` (default 25 MB). Whisper transcribes the audio:

```json
{ "status": "transcribed", "transcript": "Quais são as propriedades do cobre...", "filename": "..." }
```

---

# 17. Workers Specification

## 17.1 Celery Configuration

`backend/app/workers/celery_app.py`:

- Broker & backend: Redis (`REDIS_URL`, default `redis://localhost:6379/0`)
- Default queue: `mka-default`
- Task module: `app.workers.tasks`

## 17.2 Tasks (`backend/app/workers/tasks.py`)

| Task name | Signature | Purpose |
|---|---|---|
| `mka.ingest_document` | `ingest_document_task(self, document_id: str)` | Primary user-document ingestion; updates DB status; retries on exception |
| `mka.reindex_books` | `reindex_books_task()` | Admin reindexing of `backend/livros/` (no `user_id`) |
| `mka.ingest_single_pdf` | `ingest_single_pdf_task(pdf_path: str)` | Admin: index a single PDF from the filesystem |

`mka.ingest_document` uses `bind=True, max_retries=3` with exponential backoff (`countdown=30s`).

---

# 18. Error Handling Specification

## 18.1 Error Principles

The API provides:

- Structured errors (`ErrorResponse` envelope)
- Traceable request IDs (echoed in the response header)
- User-safe messages
- Internal debugging metadata in logs (never in the response body)

## 18.2 Example Error Response

```json
{
  "error": {
    "code": "INTERNAL_ERROR",
    "message": "An unexpected error occurred.",
    "request_id": "req_12345"
  }
}
```

Custom error codes may be added in the future (`RETRIEVAL_FAILURE`, `INGESTION_FAILURE`, etc.). Today only `INTERNAL_ERROR` is emitted by the global handler.

---

# 19. Observability Specification

## 19.1 Logging

Structured logs (configured in `backend/app/core/logging.py`) include:

- Request ID (from `x-request-id` middleware)
- Document IDs in worker logs
- Stage timings (retrieval, embedding, LLM)
- Error traces

## 19.2 Metrics (`GET /api/v1/metrics`)

Implemented in `backend/app/core/metrics_store.py` (in-memory ring buffer):

| Metric | Description |
|---|---|
| p50 / p95 retrieval latency | Time spent in Qdrant + optional rerank |
| p50 / p95 LLM latency | Time from first to last streamed token |
| Citation Coverage | % of responses with at least one citation |
| Error rate | Failed requests over the sample window |
| Sample size | Current ring buffer fill |

---

# 20. Security Specification

## 20.1 Security Goals

The backend ensures:

- JWT-based authentication (Clerk)
- HTTPS-only communication (TLS at the edge in production)
- Private document handling (per-user paths in Supabase, per-user filters in Qdrant, per-user rows in Postgres)
- Secret isolation (Supabase `service_role` never leaves the backend)
- Secure file uploads (size + MIME validation, filename sanitization)

## 20.2 Secret Management

Secrets are managed through:

- `.env` files at the repo root (gitignored, dev only)
- Container orchestrator secrets in production
- The Supabase `service_role` key MUST NOT be exposed to the frontend

Secrets must never be hardcoded.

---

# 21. Deployment Specification

## 21.1 Deployment Strategy

The backend is deployed as a Dockerized FastAPI service. The Celery worker is a sibling container that shares the same image but uses a different command (`celery -A app.workers.celery_app.celery_app worker`).

## 21.2 Suggested Infrastructure

| Layer | Component |
|---|---|
| Backend hosting | Docker container behind a load balancer |
| Worker | Docker container (scaled independently) |
| Vector Database | Qdrant (Docker, future: managed cluster) |
| Relational Database | PostgreSQL (Docker in dev, managed in prod) |
| Broker | Redis 7 (Docker in dev, managed in prod) |
| Object Storage | Supabase Storage (managed SaaS) |
| LLM provider | OpenAI |
| Reranker | Cohere (optional) |

---

# 22. Testing Strategy

## 22.1 Testing Types

| Test Type | Objective |
|---|---|
| Unit Tests | Validate isolated services |
| Integration Tests | Validate service interaction |
| Retrieval Tests | Validate retrieval quality (eval datasets — future) |
| API Tests | Validate endpoints (FastAPI TestClient) |
| Load Tests | Validate scalability (future) |

`APP_ENV=test` skips the OpenAI key requirement at startup so the suite can run without real API keys.

---

# 23. Performance Targets

| Metric | Target |
|---|---|
| Retrieval Latency (p95) | < 2 seconds |
| End-to-end Response Time (p95) | < 8 seconds |
| Upload HTTP path (returns 202) | < 3 seconds |
| Citation Coverage | 100% |
| Hallucination Rate | < 5% |

---

# 24. Future Evolution

Future backend evolution may include:

- Hybrid retrieval (sparse + dense)
- Alembic-managed schema migrations
- Multi-agent orchestration
- Persistent conversation memory
- Advanced observability (OpenTelemetry, Grafana)
- Evaluation pipelines (Recall@K, Precision@K, MRR)
- Workflow automation
- Organization-level tenancy (extend `user_id` to `org_id` filtering)
- Custom error codes (`RETRIEVAL_FAILURE`, `INGESTION_FAILURE`, etc.)

---

# 25. Conclusion

The backend architecture of the Materials Knowledge Assistant prioritizes:

- Reliability (retry-safe Celery, structured error envelope)
- Retrieval quality (per-user filtering, optional reranking)
- Grounded AI generation (empty-context guard, citation enforcement)
- Per-user privacy (data layer enforcement)
- Maintainability (modular services, typed interfaces)
- Operational simplicity (single OpenAI dependency, single Qdrant collection)
- Future scalability (stateless API, independent worker pool, abstracted storage)
