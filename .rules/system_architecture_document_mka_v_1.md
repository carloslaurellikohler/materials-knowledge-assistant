# System Architecture Document (SAD)
## Materials Knowledge Assistant (MKA)

Version: 2.0
Status: Aligned with current implementation
Author: Carlos Eduardo
Date: May 2026

---

# 1. Introduction

## 1.1 Purpose

This System Architecture Document (SAD) defines the technical architecture of the Materials Knowledge Assistant (MKA), including its system components, infrastructure strategy, service responsibilities, integration patterns, deployment topology, security model, observability approach, and scalability considerations.

The purpose of this document is to:

- Establish the architectural foundation of the platform
- Align implementation decisions across frontend, backend, persistence, and AI infrastructure
- Support scalable and maintainable development
- Reduce technical ambiguity during implementation
- Serve as a reference for future system evolution
- Enable future extensibility toward advanced AI workflows

This document complements the Product Requirements Document (PRD) and translates product-level requirements into technical architectural decisions.

---

## 1.2 Scope

This document covers the architecture of Version 1 (V1) of the Materials Knowledge Assistant.

The architecture includes:

- Frontend application (Next.js 14)
- Backend APIs (FastAPI)
- Asynchronous worker pipeline (Celery + Redis)
- Authentication flow (Clerk)
- Retrieval-Augmented Generation (RAG) pipeline
- Per-user document ingestion pipeline
- Vector database architecture (Qdrant)
- Relational database (PostgreSQL)
- Object storage (Supabase Storage)
- AI orchestration layer (direct OpenAI SDK)
- Multimodal processing
- Observability and logging
- Infrastructure and deployment (Docker Compose)
- Security model
- Scalability strategy

The document does not cover:

- Detailed UI design specifications
- Detailed prompt templates (see `backend/app/rag/prompts.py`)
- Fine-tuning strategies
- Multi-agent orchestration
- Cross-user collaboration / organization tenancy
- ERP or external enterprise integrations

---

## 1.3 Related Documents

| Document | Description |
|---|---|
| PRD | Product Requirements Document |
| Backend Spec | REST endpoint and service specifications |
| Frontend Spec | UI components and state management |
| RAG Architecture Specification | Detailed RAG pipeline design |
| README.md | Operational quick-start |

---

# 2. Architectural Goals

The architecture was designed according to the following engineering principles.

---

## 2.1 Modularity

The system is divided into loosely coupled services with clear responsibilities (chat, retrieval, ingestion, documents, storage, persistence).

Benefits:

- Easier maintenance
- Independent evolution
- Better testing
- Simplified debugging
- Future service extraction

---

## 2.2 Scalability

The architecture supports horizontal scaling for:

- Retrieval workloads (stateless FastAPI behind any load balancer)
- Embedding and ingestion throughput (Celery workers, scaled independently)
- Concurrent users (per-user data partitioning at the storage and vector layer)
- Large document collections (incremental Qdrant indexing)
- AI inference throughput (limited by upstream provider quota)

---

## 2.3 Reliability

The system prioritizes:

- Stable retrieval behavior with deterministic fallbacks for empty context
- Predictable response generation under streaming
- Graceful degradation (reranking is optional when Cohere key is absent)
- Traceability of failures (request IDs, document `indexing_error`)
- Retry-safe operations (Celery `bind=True, max_retries=3` with exponential backoff)

---

## 2.4 Observability

The platform provides:

- Structured logs with request IDs
- Document lifecycle status visible via API polling
- Retrieval and LLM latency metrics (ring buffer, exposed via `/metrics`)
- Error visibility surfaced through `indexing_error`

---

## 2.5 AI Grounding

The architecture minimizes hallucinations through:

- Strict retrieval grounding (system prompt forbids ungrounded claims)
- Per-user `user_id` filtering before retrieval
- Empty-context guard that short-circuits the LLM call
- Citation enforcement in every assistant message
- Optional Cohere re-ranking

---

## 2.6 Simplicity First

Version 1 prioritizes:

- Low operational complexity
- Rapid iteration
- Maintainability
- Small infrastructure footprint (6 containers)
- Fast deployment cycles
- No LangChain or LangGraph dependency — the OpenAI SDK is invoked directly

---

# 3. High-Level System Architecture

## 3.1 Architectural Overview

The system follows a layered architecture composed of:

1. Client Layer (browser + Next.js)
2. Edge / Proxy Layer (Next.js API route forwards `/api/v1/[...path]` to backend)
3. Application Layer (FastAPI HTTP API)
4. AI Orchestration Layer (direct OpenAI calls, optional Cohere)
5. Worker Layer (Celery for asynchronous ingestion)
6. Retrieval Layer (Qdrant vector DB)
7. Persistence Layer (PostgreSQL)
8. Object Storage Layer (Supabase Storage)
9. External AI Providers (OpenAI, Cohere)

---

## 3.2 High-Level Flow

```text
+--------------------+
|    Web Frontend    |
| Next.js 14 + Clerk |
+----------+---------+
           |  HTTP + SSE
           |  via /api/v1/[...path] proxy
           v
+--------------------+
|   FastAPI Backend  |
|   (Application)    |
+--+----+----+----+--+
   |    |    |    |
   |    |    |    +-----------+
   |    |    |                |
   |    |    +--------+       |
   |    |             |       v
   |    +-----+       |  +----------------+
   |          |       |  |  PostgreSQL    |
   |          |       |  | documents table|
   |          |       |  +----------------+
   |          v       |
   |     +----------+ |
   |     |  Qdrant  | |
   |     |  vectors | |
   |     | (filter  | |
   |     | by user) | |
   |     +----------+ |
   |                  |
   |     +------------+----+
   |     |  Supabase Storage|
   |     | {user_id}/{doc}/ |
   |     +-------+----------+
   |             ^
   |             | upload (HTTP) /
   |             | download (worker)
   v             |
+--------+       |
| OpenAI |       |
| Cohere |  +----+----+
+--------+  | Celery  |
            | Worker  |
            +----+----+
                 |
                 v
            +---------+
            |  Redis  |
            +---------+
```

Six Docker services in total: `frontend`, `backend`, `worker`, `postgres`, `redis`, `qdrant`.

---

## 3.3 Architectural Style

The platform adopts:

- Service-oriented backend design
- API-first communication
- Retrieval-Augmented Generation (RAG)
- Stateless request handling
- Asynchronous ingestion via Celery (the API returns 202 immediately, work happens in the worker)
- Storage abstraction (Protocol-based `StorageProvider` with Supabase implementation)

---

# 4. Frontend Architecture

## 4.1 Technology Stack

| Layer | Technology |
|---|---|
| Framework | Next.js 14 (App Router) |
| Language | TypeScript |
| Styling | TailwindCSS + `@tailwindcss/typography` |
| UI Components | shadcn/ui (Button, Card, Badge, Textarea) |
| Markdown | `react-markdown` |
| Icons | `lucide-react` |
| Authentication | Clerk (`@clerk/nextjs`) — optional via `NEXT_PUBLIC_ENABLE_CLERK` |
| State Management | React Context + Hooks (`useChatSession`) |
| API Communication | REST + Server-Sent Events |
| Hosting | Docker (any container host) |

---

## 4.2 Frontend Responsibilities

The frontend is responsible for:

- User authentication (when Clerk enabled)
- Chat interaction (streaming via SSE)
- Document management UI (upload, list, status polling, delete)
- Multimodal upload (image, audio)
- Rendering citations
- Markdown rendering of assistant messages
- Responsive layout
- Conversation session management (in-memory only — no persistence)
- Backend proxying via `/api/v1/[...path]/route.ts`

---

## 4.3 UI Modules

| Module | Responsibility |
|---|---|
| Auth Module | Clerk sign-in / sign-up pages, conditional middleware |
| Chat Module | `ChatWindow`, `ChatComposer`, `DocumentPanel` |
| Document Manager | `components/documents/document-manager.tsx` — drag-drop upload, status polling, delete |
| Status Badge | `components/documents/status-badge.tsx` — color-coded states |
| Upload Module | `components/upload/upload-panel.tsx` — image + audio |
| Citation Renderer | `components/citations/citation-list.tsx` |
| Markdown Renderer | `components/markdown/markdown-renderer.tsx` |
| Streaming Handler | `services/sse.ts` (async generator over SSE) |
| Session State | `hooks/use-chat-session.ts` (messages, documents, polling) |

---

## 4.4 Frontend Communication

The frontend communicates with the backend through:

- REST endpoints (`/api/v1/documents`, `/api/v1/upload/*`)
- Streaming HTTP responses (SSE for `/api/v1/chat`)
- Multipart upload (`POST /api/v1/documents`)

All browser calls hit the same origin and are proxied by `frontend/app/api/v1/[...path]/route.ts` to the backend (`BACKEND_URL` env var). Authentication tokens (Clerk JWTs) are forwarded transparently.

---

## 4.5 Frontend Design Principles

The UI prioritizes:

- Technical readability
- Minimal cognitive load
- Engineering-oriented workflows
- Clear citations
- High information density without clutter
- Portuguese (pt-BR) as primary locale

---

# 5. Backend Architecture

## 5.1 Technology Stack

| Layer | Technology |
|---|---|
| API Framework | FastAPI |
| Language | Python 3.12 |
| AI Orchestration | OpenAI SDK directly (no LangChain) |
| Validation | Pydantic 2 + pydantic-settings |
| Async Runtime | Uvicorn |
| Background Jobs | Celery + Redis 7 |
| Containerization | Docker + Docker Compose |
| HTTP client | httpx |
| JWT | PyJWT[crypto] |

---

## 5.2 Backend Responsibilities

The backend is responsible for:

- Authentication validation (Clerk JWT, RS256/JWKS or HS256 fallback)
- Chat orchestration (embed → retrieve → rerank → stream)
- Retrieval execution with per-user filtering
- Prompt assembly with grounding instructions
- LLM interaction (OpenAI streaming)
- Citation formatting
- Document CRUD (`/documents` endpoints)
- File ingestion (synchronous upload to Supabase + asynchronous Celery indexing)
- Embedding generation
- Metadata enrichment
- Observability logging and metrics

---

## 5.3 Backend Service Decomposition

### Auth Service

Location: `backend/app/api/deps.py`

Responsibilities:

- Validate Clerk JWT (RS256 via JWKS in production; HS256 fallback in dev/test)
- Inject `current_user` (with `user_id`) into request handlers via FastAPI dependency

---

### Chat Service

Location: `backend/app/services/chat.py`

Responsibilities:

- Receive user query and `metadata_filters`
- Embed the query
- Call retrieval (with `user_id` filter)
- Apply optional Cohere rerank
- Short-circuit on empty context
- Stream LLM response via SSE
- Emit `citations` event after generation
- Push metrics to the in-memory ring buffer

---

### Retrieval Service

Location: `backend/app/services/retrieval.py`

Responsibilities:

- Query Qdrant with cosine similarity
- Build `Filter(must=[...])` including mandatory `user_id` plus any `metadata_filters`
- Return a typed `list[RetrievedChunk]` with source, text, page, chapter, section

---

### Reranking Service

Location: `backend/app/services/reranking.py`

Responsibilities:

- Wrap Cohere Async client (`AsyncClientV2`)
- Only instantiated when `COHERE_API_KEY` is set
- Method `rerank(query, chunks, top_k)` returns top-N chunks

---

### Ingestion Service

Location: `backend/app/services/ingestion.py`

Responsibilities:

- `ingest_pdf_bytes(pdf_bytes, filename, user_id, document_id, status_callback)`:
  - Extract pages (pypdf + optional OCR via GPT-4o)
  - Structural chunking (numbered/uppercase headings → fallback word-based)
  - Generate embeddings in batches
  - Upsert into Qdrant with payload containing `user_id`, `document_id`, page, chunk_id, etc.
  - Call `status_callback(status)` at each major stage (`processing → chunking → embedding`)
- `reindex_books()` and `ingest_single_pdf()` (administrative, filesystem-based; no `user_id`)
- Heuristic metadata extraction: chapter/section/material_type/author/title

---

### Document Service

Location: `backend/app/api/routes/documents.py`

Responsibilities:

- `POST /api/v1/documents`: validate, sanitize filename, upload to Supabase, insert DB row, enqueue Celery task, return 202
- `GET /api/v1/documents`: list documents scoped by `user_id`
- `GET /api/v1/documents/{id}`: return a document (with ownership check)
- `DELETE /api/v1/documents/{id}`: delete Qdrant points (filter by `document_id`), Supabase blob, and DB row

---

### Storage Provider

Location: `backend/app/storage/provider.py`, `backend/app/storage/supabase_provider.py`

Responsibilities:

- Define an abstract `StorageProvider` protocol (`upload`, `delete`, `download`)
- Implement Supabase Storage variant using the `supabase-py` client with both async (via `asyncio.to_thread`) and sync (for Celery) entry points
- Authenticate to Supabase with the `service_role` key (backend is trusted; bypasses RLS)

---

### Persistence Layer

Location: `backend/app/db/database.py`, `backend/app/db/models.py`

Responsibilities:

- Provide an async engine (`asyncpg`) with `AsyncSessionLocal` for FastAPI
- Provide a sync engine (`psycopg2`) with `SyncSessionLocal` for Celery workers
- ORM model `Document` (see Section 10 for full schema)
- Auto-create tables at startup via `create_tables()` in the FastAPI lifespan
- Alembic is installed but not actively used for migrations yet

---

### Embedding Service

Location: `backend/app/integrations/openai_client.py`

Responsibilities:

- Generate embeddings in batches via `embed_texts`
- Stream chat completions via `stream_answer`
- Analyze images via `describe_image` (GPT-4o)
- Transcribe audio via `transcribe_audio` (Whisper)

---

### Citation Service

Citations are formatted inline by `services/chat.py` from the retrieved chunks; there is no dedicated citation microservice. The output schema is defined in `backend/app/api/schemas/chat.py`.

---

# 6. AI Orchestration Architecture

## 6.1 Orchestration Strategy

The orchestration is **directly coded** in Python using the OpenAI SDK. LangChain and LangGraph are intentionally NOT used in V1.

Rationale:

- Linear execution flows
- Predictable retrieval pipelines
- Faster implementation
- Lower debugging complexity
- Simpler observability
- Tighter control over streaming semantics

---

## 6.2 Orchestration Pipeline

```text
User Query (authenticated)
    ↓
Input Validation (Pydantic)
    ↓
Embedding Generation (text-embedding-3-small, 1536-d)
    ↓
Qdrant Retrieval with user_id filter
    ↓
Optional Cohere Rerank (when enabled)
    ↓
Empty-context Guard (deterministic fallback if no chunks)
    ↓
Prompt Assembly (SYSTEM_PROMPT + retrieved context + user query)
    ↓
LLM Streaming (OpenAI chat completion, SSE)
    ↓
Citation Formatting (emitted after generation)
    ↓
Streamed Response: event:token × N → event:citations → event:done
```

---

## 6.3 Prompt Assembly Strategy

Prompt construction includes:

- Retrieved chunks with inline metadata (source, page, chapter, section)
- Citation identifiers usable by the model
- User query
- System grounding instructions (`backend/app/rag/prompts.py:SYSTEM_PROMPT`)

The prompt explicitly:

- Restricts unsupported assumptions
- Enforces grounded answers
- Requires citation references
- Encourages uncertainty disclosure

---

## 6.4 LLM Strategy

| Capability | Default model | Configuration |
|---|---|---|
| Main reasoning | (see configuration note) | `OPENAI_CHAT_MODEL` |
| Vision processing | `gpt-4o` | `OPENAI_VISION_MODEL` |
| Audio transcription | `whisper-1` | `OPENAI_WHISPER_MODEL` |
| Embeddings | `text-embedding-3-small` (1536-d) | `OPENAI_EMBEDDING_MODEL` |

> ⚠️ The default value for `openai_chat_model` in `backend/app/core/config.py:14` is currently `gpt-5.4`, which is not a published OpenAI model. Operators must override `OPENAI_CHAT_MODEL` (e.g., to `gpt-4.1`) until the default is corrected.

---

## 6.5 Hallucination Mitigation

The orchestration layer:

- Rejects empty retrieval contexts (deterministic fallback message; no LLM call)
- Limits generation to retrieved evidence via the system prompt
- Enforces citation-backed claims
- Prefers omission over speculation

---

# 7. Retrieval-Augmented Generation (RAG) Architecture

## 7.1 RAG Overview

The platform uses Retrieval-Augmented Generation to ground AI responses in the user's own indexed technical literature.

The retrieval pipeline combines:

- Per-user filtering (mandatory)
- Semantic retrieval (cosine in Qdrant)
- Optional metadata filtering
- Optional Cohere re-ranking
- Empty-context guard

---

## 7.2 Retrieval Pipeline

```text
User Query
    ↓
Query Embedding
    ↓
Qdrant Dense Vector Search (filter must={user_id} + metadata_filters)
    ↓
Top-K Candidates (default 20)
    ↓
[optional] Cohere Cross-Encoder Re-ranking
    ↓
Top-N Context (default 5)
    ↓
Empty-context Guard
    ↓
Prompt Injection
```

---

## 7.3 Retrieval Parameters

| Parameter | Default | Env var |
|---|---|---|
| Initial Retrieval | Top 20 | `RETRIEVAL_TOP_K_CANDIDATES` |
| Final Context | Top 5 | `RETRIEVAL_TOP_K_FINAL` |
| Similarity Metric | Cosine | (Qdrant) |
| Vector Size | 1536 | `QDRANT_VECTOR_SIZE` |
| Chunk Size | ~1,200 words | code constant in `services/ingestion.py` |
| Chunk Overlap | ~200 words | code constant in `services/ingestion.py` |

---

## 7.4 Hybrid Retrieval Strategy

Version 1 uses dense semantic retrieval only. Sparse retrieval is gated by `SPARSE_RETRIEVAL_ENABLED` and is currently disabled. The architecture is prepared for future hybrid search combining dense vector search and BM25-style lexical retrieval.

---

## 7.5 Re-ranking Layer

The re-ranking layer improves contextual precision. Only Cohere `rerank-english-v3.0` is implemented; alternative providers (BGE, Jina) are possible future directions.

The reranker evaluates:

- Semantic relevance
- Engineering terminology alignment
- Contextual coherence
- Query-document compatibility

---

## 7.6 Citation Architecture

Every generated answer references:

- Source document
- Chapter / section (when extracted)
- Page number (when available)
- Retrieved excerpt (first ~220 characters)

Citation formatting happens after generation, using the metadata stored in the Qdrant payload alongside each chunk.

---

# 8. Document Ingestion Architecture

## 8.1 Ingestion Overview

The ingestion pipeline transforms uploaded engineering literature into indexed semantic knowledge **scoped to a specific user**.

It is split across two execution contexts:

- **Synchronous** (HTTP request handler): validates, persists the file to Supabase, creates the DB row, enqueues the worker job, and returns 202 quickly.
- **Asynchronous** (Celery worker): performs parsing, chunking, embedding, and Qdrant indexing, updating the document status in PostgreSQL as it progresses.

---

## 8.2 Ingestion Pipeline (Sync + Async)

```text
HTTP path                                Worker path (mka.ingest_document)
─────────────────────────────────        ──────────────────────────────────
POST /api/v1/documents                    Load Document row
   ↓                                         ↓
Validate MIME (PDF) + size                Update status → "processing"
   ↓                                         ↓
Sanitize filename                         Download blob from Supabase
   ↓                                         ↓
Upload bytes to Supabase                  Extract pages (pypdf, OCR opt-in)
Storage at {user_id}/{doc_id}/file.pdf       ↓
   ↓                                      Structural chunking      → "chunking"
Insert row in documents (pending)            ↓
   ↓                                      Embed chunks in batches  → "embedding"
Enqueue mka.ingest_document(doc_id)          ↓
   ↓                                      Upsert points into Qdrant
Return 202 + {document_id, status}        (payload: user_id, document_id,
                                           page, chunk_id, source, etc.)
                                             ↓
                                          Update row → "indexed" (with chunk_count)
                                          or "error" (with indexing_error)
```

---

## 8.3 Parsing Strategy

The parser preserves:

- Chapters (heuristic: uppercase / "Capítulo N" / numbered)
- Sections (numbered headings like `3.2 Corrosion`)
- Subsections
- Equations (inline)
- Standards references (when present)
- Material terminology

Flattening into plain text is avoided when structural cues are detected. Tables are kept inline today; isolating them is a future improvement.

---

## 8.4 OCR Strategy

OCR is **opt-in** via `OCR_BACKEND=vision` (defaults to `none`). When enabled:

- Pages with native text shorter than `OCR_MIN_CHARS` (default 50) are sent to GPT-4o for OCR
- This adds API cost per page; intended for scanned documents
- No third-party OCR providers (Tesseract, Gemini, Azure DI) are currently integrated

---

## 8.5 Chunking Strategy

### Strategy

Hybrid chunking:

- **Structural** when numbered or uppercase headings are detected
- **Word-based** fallback (default 1,200 words, 200-word overlap)

### Important Rules

Avoid:

- Arbitrary token slicing
- Breaking definitions from their explanations

Prefer:

- Concept-complete chunks
- Section-aware segmentation
- Material-property contextual grouping

---

## 8.6 Metadata Enrichment

Each chunk's Qdrant payload includes:

```json
{
  "source": "callister_materials_science.pdf",
  "source_id": "sha256:9c...",
  "user_id": "user_2abc...",
  "document_id": "9a1b8c7d-...-...",
  "page": 248,
  "chunk_id": "p248_c0",
  "text": "...",
  "document_type": "Book",
  "ingestion_timestamp": "2026-05-18T12:30:00Z",
  "author": "William D. Callister",
  "title": "Materials Science and Engineering",
  "chapter": "Corrosion",
  "section": "Galvanic Corrosion",
  "material_type": "steel"
}
```

The `user_id` and `document_id` fields are the load-bearing identifiers for per-user retrieval and for cascading deletes.

---

# 9. Vector Database Architecture

## 9.1 Vector Database Selection

Qdrant v1.11.3 was selected due to:

- Strong vector search performance
- First-class payload filtering (essential for per-user isolation)
- Incremental indexing
- Simple operational model (single Docker container)
- Cloud deployment options

---

## 9.2 Vector Storage Strategy

Each chunk stored in Qdrant contains:

- Embedding vector (1536-d cosine)
- Raw chunk text
- Metadata payload (see Section 8.6)
- Deterministic point ID derived from `(user_id, document_id, page_num, chunk_idx)`

Point IDs are generated by `_user_point_id` in `backend/app/services/ingestion.py`, ensuring idempotency for re-ingestion.

---

## 9.3 Collection Design

Currently there is a single collection: `engineering_documents` (configurable via `QDRANT_COLLECTION`). Multi-collection layouts (one per tenant or evaluation dataset) are a future option; for V1 a single collection with strong payload filtering is sufficient.

---

## 9.4 Persistence Strategy

Persistent collections are enabled via the `qdrant_data` Docker volume. Operational backups should include:

- Vector indexes
- Metadata payloads
- Collection schemas

The reference admin CLI `reindex_corpus.py` supports checkpoint resume after interruption.

---

# 10. Relational Database Architecture

## 10.1 Selection

PostgreSQL 16 was selected for:

- Strong transactional semantics for document lifecycle updates
- Rich indexing (B-tree on `user_id`)
- Wide library support (`asyncpg`, `psycopg2`)
- Standard SQL operability

## 10.2 Schema (`documents` table)

| Column | Type | Notes |
|---|---|---|
| `id` | String(36) PK | UUID generated by the backend |
| `user_id` | String(255) | Indexed; from Clerk JWT |
| `filename` | String(512) | Sanitized name (storage) |
| `original_filename` | String(512) | User-provided name |
| `storage_path` | String(1024) | `{user_id}/{document_id}/{filename}` |
| `mime_type` | String(128) | Always `application/pdf` |
| `size` | Integer | Bytes |
| `indexing_status` | Enum | `pending`, `processing`, `chunking`, `embedding`, `indexed`, `error` |
| `indexing_error` | Text · nullable | Filled when status = `error` |
| `chunk_count` | Integer · nullable | Set after `indexed` |
| `embedding_model` | String(128) · nullable | e.g., `text-embedding-3-small` |
| `qdrant_collection` | String(256) | Target collection |
| `created_at` / `updated_at` | DateTime(tz) | Auto-maintained |

## 10.3 Sessions

| Context | Driver | Session class | Use |
|---|---|---|---|
| FastAPI | `asyncpg` (async) | `AsyncSessionLocal` | HTTP request handlers |
| Celery worker | `psycopg2` (sync) | `SyncSessionLocal` | Background tasks |

## 10.4 Migrations

Schema creation is performed via `Base.metadata.create_all()` inside the FastAPI lifespan (`backend/app/main.py:23`). Alembic is installed (`alembic>=1.13` in `pyproject.toml`) and ready to adopt, but no migration revisions are versioned yet. Migrating to Alembic-managed revisions is on the Phase 2 roadmap.

---

# 11. Object Storage Architecture

## 11.1 Selection

Supabase Storage was selected for:

- Managed S3-compatible object storage with simple ACL
- Hosted SaaS (no operational overhead in V1)
- First-class Python client (`supabase-py`)
- Compatibility with future RLS-based public-share flows

## 11.2 Bucket Layout

Single bucket: `mka-documents` (configurable via `SUPABASE_BUCKET`).

Path structure:

```
mka-documents/
  └─ {user_id}/
       └─ {document_id}/
            └─ {sanitized_filename}.pdf
```

The path itself encodes ownership, which simplifies cascading deletes and audit.

## 11.3 Authentication

The backend authenticates to Supabase using the **`service_role` secret key**, NOT the anon key. The backend is trusted and bypasses RLS; per-user authorization is enforced by Clerk + the application layer.

Using the anon key causes 403 errors with `row violates row-level security policy` — this is the documented failure mode.

## 11.4 Provider Abstraction

The `StorageProvider` Protocol in `backend/app/storage/provider.py` defines `upload`, `delete`, and `download`. The Supabase implementation in `supabase_provider.py` is a lazy singleton acquired via `get_storage()`. Sync variants (`sync_upload`, `sync_delete`, `sync_download`) are exposed for use inside Celery workers, where awaiting an async client is awkward.

This abstraction makes future provider swaps (S3, GCS, Azure Blob) straightforward.

---

# 12. Multimodal Architecture

## 12.1 Multimodal Goals

The platform supports:

- Text input
- Image upload (GPT-4o description)
- Audio upload (Whisper transcription)

PDF attachments inline within a chat conversation are NOT supported in V1 (PDFs go through the `/documents` flow).

---

## 12.2 Image Processing Pipeline

Supported use cases:

- Corrosion inspection
- Material degradation analysis
- Microscopy analysis
- Technical diagrams
- Surface failures

```text
Image Upload (POST /api/v1/upload/image)
    ↓
GPT-4o Vision (VISION_PROMPT)
    ↓
Textual Description
    ↓
(User decides to send the description as a /chat query)
    ↓
Normal RAG Pipeline
```

Max image size: `MAX_IMAGE_UPLOAD_MB` (default 20 MB).

---

## 12.3 Audio Processing Pipeline

```text
Audio Upload (POST /api/v1/upload/audio)
    ↓
Whisper-1 Transcription
    ↓
Textual Transcript
    ↓
(User decides to send the transcript as a /chat query)
    ↓
Normal RAG Pipeline
```

Max audio size: `MAX_AUDIO_UPLOAD_MB` (default 25 MB).

---

## 12.4 Multimodal Model Strategy

| Capability | Default model | Env var |
|---|---|---|
| Vision | `gpt-4o` | `OPENAI_VISION_MODEL` |
| Audio Transcription | `whisper-1` | `OPENAI_WHISPER_MODEL` |
| Main reasoning | (see Section 6.4 note) | `OPENAI_CHAT_MODEL` |

---

# 13. API Architecture

## 13.1 API Style

The backend exposes RESTful APIs under `/api/v1`. Streaming responses use Server-Sent Events. Unhandled exceptions are converted to a typed `ErrorResponse` envelope with the request ID by the global exception handler in `backend/app/main.py`.

CORS is restricted to `http://localhost:3000` and `http://127.0.0.1:3000` (suitable for the bundled Next.js dev origin or when the Next.js proxy is the only client).

---

## 13.2 Endpoint Map

| Method | Path | Auth | Code location |
|---|---|---|---|
| `GET` | `/api/v1/health` | No | `routes/health.py` |
| `GET` | `/api/v1/metrics` | No | `routes/metrics.py` |
| `POST` | `/api/v1/chat` | Yes | `routes/chat.py` |
| `POST` | `/api/v1/documents` | Yes | `routes/documents.py` |
| `GET` | `/api/v1/documents` | Yes | `routes/documents.py` |
| `GET` | `/api/v1/documents/{id}` | Yes | `routes/documents.py` |
| `DELETE` | `/api/v1/documents/{id}` | Yes | `routes/documents.py` |
| `POST` | `/api/v1/upload/image` | Yes | `routes/multimodal.py` |
| `POST` | `/api/v1/upload/audio` | Yes | `routes/multimodal.py` |

> `routes/upload.py` exists in the codebase but is **NOT registered** in `main.py` and therefore not exposed. The legacy `POST /upload/pdf` is dead code; the actively used upload path is `POST /documents`.

---

## 13.3 API Design Principles

The API prioritizes:

- Statelessness
- Predictable schemas (Pydantic v2)
- Structured errors (`ErrorResponse` envelope with request ID)
- Async support
- Streaming compatibility (SSE)
- Per-user ownership enforced at the handler level

---

# 14. Security Architecture

## 14.1 Authentication Strategy

Authentication uses:

- Clerk (any identity provider Clerk supports — Google, email, etc.)
- JWT bearer tokens validated by the backend:
  - **Production**: RS256 via Clerk JWKS (`CLERK_JWKS_URL`)
  - **Dev/test**: HS256 fallback (`CLERK_JWT_SECRET`)

The frontend can also operate **without** Clerk for local development (`NEXT_PUBLIC_ENABLE_CLERK=false`).

---

## 14.2 Security Goals

The system ensures:

- Private document handling (per-user paths in Supabase, per-user filters in Qdrant, per-user rows in Postgres)
- Secure token handling (bearer only, never persisted on the server)
- Authenticated access for all protected endpoints
- Transport encryption (TLS at the edge in production)
- Minimal data retention (no chat history persistence in V1)

---

## 14.3 Data Privacy Strategy

Version 1 intentionally avoids:

- Persistent conversation history
- Long-term user profiling
- Behavioral analytics

Uploaded documents are isolated by `user_id` at every layer (Postgres queries, Qdrant filters, Supabase paths) and cascade-deleted on `DELETE /documents/{id}`.

---

## 14.4 Secret Management

Secrets are managed via:

- `.env` files at the repository root for local development (gitignored)
- Container orchestrator secrets in production (Docker Swarm, Kubernetes, Railway Variables, etc.)
- The Supabase `service_role` key MUST NOT be exposed to the frontend; only the backend uses it

Secrets must never be hardcoded.

---

# 15. Observability Architecture

## 15.1 Observability Goals

The system provides visibility into:

- Retrieval behavior
- LLM performance
- Failures (per request and per document)
- Latency
- Infrastructure health

---

## 15.2 Logging Strategy

Structured logs (via the `logging` module configured in `backend/app/core/logging.py`) include:

- Request IDs (`request.state.request_id`, propagated via the `x-request-id` middleware)
- Stage timings (retrieval, embedding, LLM)
- Document IDs for worker logs
- Error traces

---

## 15.3 Metrics

Implemented in `backend/app/core/metrics_store.py` (in-memory ring buffer), exposed via `GET /api/v1/metrics`:

| Metric | Description |
|---|---|
| p50 / p95 retrieval latency | Time spent in Qdrant + rerank |
| p50 / p95 LLM latency | Time from first to last streamed token |
| Citation coverage | Percentage of responses with at least one citation |
| Error rate | Failed requests over sample window |
| Sample size | Current ring buffer fill |

---

## 15.4 Tracing

Future observability may integrate:

- OpenTelemetry
- Grafana / Prometheus
- LangSmith (only if LangChain is ever adopted)

---

# 16. Deployment Architecture

## 16.1 Infrastructure Overview

| Layer | Default in `docker-compose.yml` |
|---|---|
| Frontend | Container `frontend` (port 3000) |
| Backend | Container `backend` (port 8000) |
| Worker | Container `worker` (Celery) |
| Vector Database | Container `qdrant` (port 6333) |
| Relational Database | Container `postgres` (port 5432) |
| Cache / Broker | Container `redis` (port 6379) |
| AI providers | OpenAI, Cohere (external SaaS) |
| Object Storage | Supabase (external managed SaaS) |

Total: 6 local containers + 3 external SaaS dependencies.

---

## 16.2 Container Strategy

Backend services are containerized using Docker. Benefits:

- Environment consistency
- Easier deployment
- Infrastructure portability
- Simplified CI/CD

`docker-compose.dev.yml` overrides for hot reload (bind mounts on backend and frontend), `docker-compose.prod.yml` overrides for production hardening.

---

## 16.3 CI/CD Strategy

Suggested CI/CD stages:

```text
Code Push
    ↓
Linting (ruff)
    ↓
Unit Tests (pytest, APP_ENV=test bypasses required OPENAI_API_KEY)
    ↓
Container Build
    ↓
Deployment
    ↓
Smoke Tests (GET /health)
```

---

## 16.4 Environment Strategy

| Environment | Purpose |
|---|---|
| Local (`dev`) | Development with hot reload |
| Test (`test`) | Pytest suite (skips OPENAI key check) |
| Production (`prod`) | Live environment with hardened compose overrides |

`APP_ENV` selects the mode and gates the OpenAI key requirement at startup.

---

# 17. Scalability Strategy

## 17.1 Horizontal Scaling

The architecture supports horizontal scaling through:

- Stateless FastAPI containers (any number behind a load balancer)
- Independent Celery worker pool (scale `worker` replicas to match ingestion load)
- External vector database (Qdrant can be moved to a dedicated cluster)
- External managed Postgres (production deployments should use a managed instance)
- External Supabase Storage (handled by the SaaS provider)

## 17.2 Future Architectural Evolution

The platform is prepared for:

- Hybrid retrieval (sparse + dense)
- Multi-agent orchestration
- Specialized engineering agents
- Organization-level tenancy (extend `user_id` to `org_id` filtering)
- Advanced observability
- Retrieval evaluation pipelines
- Autonomous workflows

## 17.3 Potential Future Services

| Future service | Purpose |
|---|---|
| Evaluation Service | Retrieval benchmarking |
| Memory Service | Persistent conversations |
| Agent Runtime | Multi-agent orchestration |
| Standards Validator | Engineering standards analysis |
| Reporting Engine | Technical report generation |
| Organization Service | Multi-tenant org modeling |

---

# 18. Risks and Architectural Tradeoffs

## 18.1 Key Risks

| Risk | Mitigation |
|---|---|
| Hallucinations | Strict grounding + empty-context guard |
| Poor retrieval quality | Optional Cohere re-ranking |
| Large PDF complexity | Async Celery ingestion with retry + checkpointing |
| OCR inaccuracies | GPT-4o vision fallback (opt-in) |
| Embedding costs | Batch processing |
| Long response latency | Streaming responses |
| Per-user data leakage | Mandatory `user_id` filter; ownership enforced at DB |
| Supabase outage | `StorageProvider` abstraction allows swapping backends |
| Default `OPENAI_CHAT_MODEL` is invalid (`gpt-5.4`) | Always override via env until the default is corrected |

## 18.2 Architectural Tradeoffs

| Decision | Benefit | Tradeoff |
|---|---|---|
| Direct OpenAI SDK instead of LangChain | Simplicity, control | Less ecosystem tooling |
| Qdrant | Operational simplicity | Smaller ecosystem than Pinecone |
| Postgres with `create_all` (no Alembic yet) | Faster bootstrap | Migrations must be manual when schema changes |
| Supabase Storage | Managed, easy | Vendor coupling (mitigated by Protocol abstraction) |
| No persistent chat memory | Privacy + simplicity | Reduced continuity |
| Monolithic backend in V1 | Faster delivery | Future service extraction required |

---

# 19. Future Architecture Evolution

## Phase 1 — Core Assistant (✅ implemented)

- RAG with per-user isolation
- PDF ingestion via Supabase + Celery
- Citations
- Semantic retrieval
- Clerk authentication
- Document lifecycle in Postgres

## Phase 2 — Retrieval Optimization

- Hybrid search (sparse + dense)
- Improved re-ranking
- Retrieval analytics
- Evaluation datasets
- Alembic migrations adoption

## Phase 3 — Advanced Multimodality

- Inline image attachments in chat
- Diagram interpretation
- Comparative engineering analysis

## Phase 4 — Engineering Copilot

- Multi-agent orchestration
- Standards validation
- Automated technical reports
- Failure prediction assistance
- Organization-level tenancy

---

# 20. Conclusion

The Materials Knowledge Assistant architecture balances:

- Technical rigor
- Operational simplicity
- AI reliability
- Per-user privacy
- Scalability
- Engineering usability

The core differentiator is not only the use of generative AI, but the combination of:

- Domain-specialized retrieval
- Structured engineering knowledge
- Grounded AI reasoning
- Traceable citations
- Multimodal technical workflows
- Strict per-user isolation

The architecture intentionally prioritizes strong retrieval quality and grounded responses over orchestration complexity. This foundation enables future evolution toward a fully specialized engineering AI copilot platform.

---

## Source Reference

This document supersedes Version 1.0 of the SAD and is aligned with the implementation as of May 2026.
