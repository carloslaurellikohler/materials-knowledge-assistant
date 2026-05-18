# Product Requirements Document (PRD)
# Materials Knowledge Assistant (MKA)

Version: 2.0
Status: Aligned with current implementation
Author: Carlos Eduardo
Date: May 2026

---

# 1. Product Overview

## 1.1 Product Name

Materials Knowledge Assistant (MKA)

---

## 1.2 Product Vision

The Materials Knowledge Assistant (MKA) is a specialized AI-powered assistant designed to support technical analysis workflows in the field of materials engineering for industrial applications, particularly in the context of electrical transformers.

The platform enables engineers to interact with a personal, curated technical knowledge base composed of books, scientific papers, technical reports, standards, and engineering documentation. Each user manages their own corpus; documents and retrieval are isolated per user (multi-tenant).

Using Retrieval-Augmented Generation (RAG), the assistant retrieves relevant information from the user's indexed documents and generates grounded responses with explicit references to source materials.

The system aims to reduce the time required for technical investigations, improve decision confidence, and increase access to specialized engineering knowledge accumulated over years of academic and professional experience.

---

# 2. Problem Statement

Materials engineers frequently need to revisit highly technical literature to support engineering decisions and technical opinions related to:

- Corrosion
- Oxidation
- Thermal resistance
- Mechanical properties
- Environmental degradation
- Material compatibility
- Heat treatment suitability
- Surface failures
- Electrical insulation behavior
- Environmental exposure conditions

These analyses often require searching across multiple PDFs, books, standards, and scientific documents manually.

This process is:

- Time-consuming
- Cognitively expensive
- Fragmented
- Difficult to trace
- Dependent on prior memory of the literature

The lack of a unified semantic retrieval layer limits productivity and slows technical decision-making.

---

# 3. Product Goals

## 3.1 Primary Goals

- Provide grounded technical answers based on user-managed literature
- Enable natural language interaction with engineering documentation
- Reduce time spent searching technical PDFs
- Improve consistency of technical opinions
- Create a per-user knowledge interface with strict isolation
- Support multimodal interaction (text, image, audio)

---

## 3.2 Secondary Goals

- Prepare architecture for future multi-agent evolution
- Enable future support for standards and regulations
- Build reusable infrastructure for industrial AI assistants
- Create a scalable domain-specific RAG platform

---

# 4. Target User

## Primary User

Materials Engineer working with industrial materials analysis in the electrical transformer sector.

### User Characteristics

- High technical expertise
- Works with engineering literature frequently
- Needs high confidence and traceability
- Requires contextual and domain-specific responses
- Frequently analyzes environmental/material interactions

---

# 5. Product Scope

---

# 5.1 In Scope (V1)

## Authentication

- Clerk-based authentication (Google, email, etc. via Clerk)
- JWT validation in the backend (RS256 via Clerk JWKS in production; HS256 fallback for development)
- Optional Clerk in the frontend (toggle via `NEXT_PUBLIC_ENABLE_CLERK`)

## Chat Interface

- Natural language interaction
- Streaming responses via Server-Sent Events (SSE)
- Markdown rendering in answers
- Citation rendering (source, chapter/section, page, excerpt)
- Mobile-responsive UI

## Knowledge Base — Per-User

- PDF upload through `POST /api/v1/documents` (multipart)
- Per-user document listing and deletion
- Asynchronous indexing pipeline (Celery worker)
- Document lifecycle status tracking with terminal states: `indexed`, `error`
- Real-time status polling from the frontend (3-second interval)
- Strict per-user isolation: a user can only see and query their own documents

## Multimodal Inputs

- Text input
- Image upload (analysis via GPT-4o vision → textual description that can be fed back into a chat query)
- Audio upload (transcription via Whisper → textual transcript that can be fed back into a chat query)

## Retrieval-Augmented Generation

- Vector retrieval filtered by `user_id` (and optional `metadata_filters`)
- Top-K candidate retrieval (default 20)
- Optional re-ranking via Cohere Rerank (only when `COHERE_API_KEY` is provided)
- Top-N final context (default 5) fed to the LLM
- Empty-context guard: if no chunks are retrieved, the system returns a deterministic fallback message without invoking the LLM

## Citations

- Source document attribution
- Chapter / section references (when extracted)
- Page references
- Inline excerpt from the cited chunk

## Administrative Corpus (Optional)

- A separate CLI (`backend/reindex_corpus.py`) can index a shared admin corpus from `backend/livros/`
- This corpus has no `user_id` and is therefore NOT visible in user-scoped retrieval. It is used only for bootstrap / shared bases when applicable

---

# 5.2 Out of Scope (V1)

- Persistent conversation memory
- **Active collaboration between users** (sharing documents, conversations, or knowledge bases between different Clerk identities)
- Fine-tuning custom models
- Autonomous agents / multi-agent orchestration
- Workflow automation
- ERP integrations
- Continuous document synchronization
- Offline mode
- Organization-level (enterprise) tenancy and roles beyond the per-user isolation already implemented
- Behavioral analytics / usage metering at user level

> The platform is **multi-tenant at the user level** (each Clerk user is a tenant); what is out of scope is *collaboration* between users and richer organization/team modeling.

---

# 6. Functional Requirements

---

# 6.1 Authentication

## FR-001

The platform must authenticate users via Clerk. The backend must verify the bearer JWT on every protected endpoint using Clerk's JWKS (RS256) in production, falling back to a shared secret (HS256) only in development/test environments.

## FR-002

Only authenticated users may access protected endpoints (`/chat`, `/documents/*`, `/upload/image`, `/upload/audio`). The endpoints `/health` and `/metrics` remain public.

## FR-003

The frontend must support running without Clerk for local development (flag `NEXT_PUBLIC_ENABLE_CLERK=false`); when disabled, the auth middleware acts as a no-op.

---

# 6.2 Chat Experience

## FR-004

The platform must provide a conversational interface.

## FR-005

The platform must stream AI responses using Server-Sent Events (`event: token`, `event: citations`, `event: done`, `event: error`).

## FR-006

The platform must render assistant messages as markdown.

## FR-007

The platform must render citations alongside each assistant message (source, optional chapter/section, optional page, excerpt).

## FR-008

Each chat request must be authenticated; the `user_id` extracted from the JWT must be applied as a `must` filter on the Qdrant search.

---

# 6.3 Document Management

## FR-009

The platform must accept PDF uploads up to `MAX_UPLOAD_MB` (default 100 MB) via `POST /api/v1/documents` (multipart `file` field).

## FR-010

The upload endpoint must:
- Validate MIME and size
- Sanitize the filename
- Persist the binary in Supabase Storage at `{user_id}/{document_id}/{filename}`
- Insert a row in the `documents` table with status `pending`
- Enqueue the Celery task `mka.ingest_document(document_id)`
- Return HTTP **202 Accepted** with `{ document_id, indexing_status }`

## FR-011

The platform must expose:
- `GET /api/v1/documents` — list documents for the authenticated user
- `GET /api/v1/documents/{id}` — retrieve a single document (status polling)
- `DELETE /api/v1/documents/{id}` — remove the document (Qdrant vectors filtered by `document_id`, Supabase blob, and Postgres row)

Each endpoint must enforce ownership by `user_id`.

## FR-012

The Celery worker must update the document status as it progresses:
`pending → processing → chunking → embedding → indexed` (or `→ error` on failure).
Failures must populate `indexing_error` with a human-readable message.

## FR-013

The frontend must poll `GET /api/v1/documents/{id}` until the document reaches a terminal status (`indexed` or `error`). Default polling interval: 3 seconds.

## FR-014

The platform must allow image upload (`POST /api/v1/upload/image`) for analysis via GPT-4o.

## FR-015

The platform must allow audio upload (`POST /api/v1/upload/audio`) for transcription via Whisper.

---

# 6.4 Knowledge Retrieval

## FR-016

The system must retrieve relevant chunks from the user's indexed documents using semantic similarity search in Qdrant.

## FR-017

All vector searches must include a mandatory `user_id` filter so that a user never retrieves another user's chunks.

## FR-018

The system must support additional metadata filters supplied by the client (`metadata_filters` in the chat payload), combined with the `user_id` filter via `must` clauses.

## FR-019

When `COHERE_API_KEY` is configured, the system must apply Cohere Rerank to the top-K candidates to produce the top-N final context. When not configured, the top-N from Qdrant is used directly.

---

# 6.5 AI Response Generation

## FR-020

Responses must be grounded exclusively in the chunks retrieved for the user. The system prompt forbids the LLM from inventing facts not present in the context.

## FR-021

Every assistant message must be accompanied by a `citations` event listing the sources used (source, chapter, section, page, excerpt).

## FR-022

If retrieval returns no chunks for a query, the system must short-circuit and return a fixed fallback message in Portuguese (no LLM call): "A literatura técnica indexada não fornece evidência suficiente para responder a esta questão."

## FR-023

The assistant must explicitly state uncertainty when the retrieved context is thin or contradictory.

---

# 7. Non-Functional Requirements

---

# 7.1 Performance

## NFR-001

End-to-end response latency (retrieval + LLM streaming start) should target under 8 seconds at p95.

## NFR-002

Retrieval (Qdrant query + optional rerank) should complete in under 2 seconds at p95.

## NFR-003

Document upload (HTTP synchronous portion) must return 202 in under 3 seconds for files at the maximum size limit; ingestion proceeds asynchronously after that.

---

# 7.2 Security

## NFR-004

Uploaded documents must be stored privately in Supabase Storage. The backend authenticates to Supabase using a `service_role` secret; the anon key is not used.

## NFR-005

Authentication tokens (Clerk JWTs) must be transmitted only via `Authorization: Bearer` and never persisted server-side.

## NFR-006

No conversation persistence in V1: chat messages are not stored on the backend.

## NFR-007

Per-user isolation must be enforced at the data layer (Postgres queries scoped by `user_id`, Qdrant searches filtered by `user_id`, Supabase paths namespaced by `user_id`). The application MUST NOT rely on UI gating alone.

---

# 7.3 Scalability

## NFR-008

The architecture must support horizontal scaling of stateless services (backend and Celery workers).

## NFR-009

The vector database must support incremental indexing of new documents without recreating the collection.

## NFR-010

The relational database schema must allow efficient lookups by `user_id` (indexed) and by `document_id` (primary key).

---

# 7.4 Usability

## NFR-011

The platform must be fully responsive for mobile devices.

## NFR-012

The interface should prioritize simplicity and readability.

## NFR-013

Long-running operations (PDF indexing) must surface progress to the user via status polling, with clear visual states (`pending`, `processing`, `chunking`, `embedding`, `indexed`, `error`).

---

# 7.5 Observability

## NFR-014

The backend must expose structured logs with request IDs propagated from the `x-request-id` header (auto-generated when absent).

## NFR-015

Errors and retrieval failures must be traceable end-to-end.

## NFR-016

The endpoint `GET /api/v1/metrics` must expose p50/p95 retrieval latency, p50/p95 LLM latency, citation coverage, and error rate (computed from a ring buffer in memory).

---

# 7.6 Durability and Data Lifecycle

## NFR-017

Document metadata is stored in PostgreSQL with timestamps (`created_at`, `updated_at`). The schema is created automatically on backend startup via SQLAlchemy `Base.metadata.create_all` (Alembic is available but no migrations are versioned yet).

## NFR-018

Document binaries are stored in Supabase Storage. Deletion of a document is cascading: vectors (Qdrant) → blob (Supabase) → row (Postgres). Failures at any step must surface to the user.

---

# 8. System Architecture

---

# 8.1 Frontend Stack

| Layer | Technology |
|---|---|
| Framework | Next.js 14 (App Router) |
| Language | TypeScript |
| Styling | TailwindCSS + `@tailwindcss/typography` |
| UI Components | shadcn/ui (Button, Card, Badge, Textarea) |
| Markdown | `react-markdown` |
| Icons | `lucide-react` |
| Authentication | Clerk (`@clerk/nextjs`) — optional via flag |
| Hosting | Docker (any container host) |

---

# 8.2 Backend Stack

| Layer | Technology |
|---|---|
| API | FastAPI (Python 3.12) |
| ASGI | Uvicorn |
| AI orchestration | OpenAI SDK directly (no LangChain) |
| Embeddings | OpenAI `text-embedding-3-small` (1536-d) |
| LLM (chat) | OpenAI chat models (see configuration note in README) |
| Vision | OpenAI `gpt-4o` |
| Audio transcription | OpenAI `whisper-1` |
| OCR (opt-in) | GPT-4o via `OCR_BACKEND=vision` |
| Re-ranking | Cohere `rerank-english-v3.0` (optional) |
| Task queue | Celery + Redis 7 |
| PDF parsing | `pypdf`, `pymupdf` |
| Relational DB | PostgreSQL 16 + SQLAlchemy 2.0 (async via `asyncpg`, sync via `psycopg2-binary` for Celery) |
| Object Storage | Supabase Storage (`supabase-py`) |
| Migrations | Alembic (installed, not actively used; schema created in lifespan) |

---

# 8.3 Vector Infrastructure

| Component | Technology |
|---|---|
| Vector Database | Qdrant v1.11.3 |
| Storage Strategy | Single collection (`engineering_documents`) with payload-based filtering |
| Search Type | Semantic (cosine) with mandatory `user_id` filter |
| Re-ranking | Optional Cohere Rerank API |
| Payload Schema | `source`, `source_id`, `user_id`, `document_id`, `page`, `chunk_id`, `text`, `document_type`, `ingestion_timestamp`, `author`, `title`, `chapter`, `section`, `material_type` |

---

# 9. RAG Strategy

This section defines the core intelligence architecture of the platform.

---

# 9.1 Document Ingestion Pipeline (Sync + Async)

```text
HTTP path (sync, returns 202)         Worker path (async, mka.ingest_document)
─────────────────────────────         ─────────────────────────────────────────
POST /api/v1/documents                 status → "processing"
   ↓                                       ↓
Validate MIME + size                   Download blob from Supabase
   ↓                                       ↓
Sanitize filename                      Extract pages (pypdf, OCR opt-in)
   ↓                                       ↓
Upload to Supabase Storage             Structural chunking            status → "chunking"
   ↓                                       ↓
Insert documents row (pending)         Embed chunks in batches        status → "embedding"
   ↓                                       ↓
Enqueue mka.ingest_document            Upsert into Qdrant (payload has user_id, document_id)
   ↓                                       ↓
Return 202 + {document_id, status}     Update documents row           status → "indexed" | "error"
```

---

# 9.2 Parsing Strategy

The ingestion pipeline should identify and preserve:

- Chapters (detected via uppercase / "Capítulo N" / numbered)
- Sections (numbered headings like `3.2 Corrosion`)
- Subsections
- Tables (kept inline today; future work to isolate)
- Equations (kept inline)
- Standards references (when extractable)
- Material classifications (heuristic keyword detection: steel, copper, aluminum, etc.)

The parser should avoid flattening the entire document into plain text whenever possible.

---

# 9.3 Chunking Strategy

## Objective

Preserve semantic integrity of technical engineering knowledge.

---

## Strategy

Hybrid Chunking:

- Structural chunking when numbered or uppercase headings are detected
- Word-based chunking as a fallback (default 1,200 words per chunk, 200-word overlap)

---

## Chunk Characteristics

| Property | Recommendation |
|---|---|
| Chunk Size | ~1,200 words (≈ 800–1,500 tokens) |
| Overlap | ~200 words (≈ 15–20%) |
| Segmentation | Section-aware where possible |
| Table Handling | Inline today (future improvement) |
| Equations | Preserved inline |

---

## Important Rules

### Avoid

- Fixed-size naive chunking only
- Breaking tables across chunks (best-effort)
- Splitting definitions from explanations

### Prefer

- Section-preserving chunks
- Concept-complete chunks
- Material-property contextualization

---

# 9.4 Metadata Strategy

Each chunk stored in Qdrant carries the metadata listed in section 8.3.

## Example payload

```json
{
  "source": "callister_materials_science.pdf",
  "source_id": "sha256:9c...",
  "user_id": "user_2abc...",
  "document_id": "9a1b8c7d-...-...",
  "author": "William D. Callister",
  "title": "Materials Science and Engineering",
  "chapter": "Corrosion",
  "section": "Galvanic Corrosion",
  "material_type": "steel",
  "document_type": "Book",
  "page": 248,
  "chunk_id": "p248_c0",
  "text": "Carbon steels exposed to chloride-rich marine environments...",
  "ingestion_timestamp": "2026-05-18T12:30:00Z"
}
```

---

# 9.5 Retrieval Pipeline

```text
User Query (authenticated, user_id from JWT)
    ↓
Query Embedding (text-embedding-3-small)
    ↓
Qdrant search with must={user_id} + metadata_filters (Top-K candidates, default 20)
    ↓
Cohere Rerank (optional; Top-K → Top-N, default 5)
    ↓
Empty-context guard (if no chunks → deterministic fallback, no LLM call)
    ↓
Prompt assembly with SYSTEM_PROMPT (grounding) + retrieved context
    ↓
LLM streaming response (SSE: token × N → citations → done)
```

---

# 9.6 Retrieval Strategy

## Retrieval Method

Dense semantic retrieval with payload-based filtering. Sparse keyword retrieval is currently disabled (`SPARSE_RETRIEVAL_ENABLED=false`).

---

## Retrieval Parameters

| Parameter | Default | Env var |
|---|---|---|
| Initial Retrieval | Top 20 | `RETRIEVAL_TOP_K_CANDIDATES` |
| Final Context | Top 5 | `RETRIEVAL_TOP_K_FINAL` |
| Similarity Metric | Cosine Similarity | (Qdrant) |
| Vector Size | 1536 | `QDRANT_VECTOR_SIZE` |

---

# 9.7 Re-ranking Strategy

## Objective

Improve contextual precision before prompt assembly.

## Implementation

Cohere Rerank API (`rerank-english-v3.0` by default), enabled only when `COHERE_API_KEY` is set. When disabled, the top-K from Qdrant is forwarded directly to the prompt assembly stage (limited to top-N).

---

# 9.8 Citation Strategy

Every response must include:

- Source document
- Chapter / section reference (when available)
- Page number (when available)
- Retrieved excerpt (first ~220 characters of the chunk)

---

## Example response format

```text
According to "Materials Science and Engineering" (Chapter: Corrosion, p. 248):

"Carbon steels exposed to chloride-rich marine environments..."

This suggests that the selected material may present elevated corrosion susceptibility under maritime exposure conditions.
```

---

# 10. Prompt Engineering Strategy

---

# 10.1 Grounding Rules

The assistant must:

- Only answer using retrieved context
- Explicitly mention uncertainty
- Avoid unsupported assumptions
- Prefer precision over speculation

The system prompt (defined in `backend/app/rag/prompts.py`) enforces these rules.

---

# 10.2 Anti-Hallucination Policy

If retrieval returns zero relevant chunks, the assistant SHORT-CIRCUITS and responds (in Portuguese):

```text
A literatura técnica indexada não fornece evidência suficiente para responder a esta questão.
```

No LLM call is issued in this case; the fallback is deterministic.

---

# 10.3 Tone and Style

The assistant should communicate:

- Professionally
- Technically
- Clearly
- Objectively
- Without exaggerated confidence

---

# 11. Multimodal Strategy

---

# 11.1 Image Support

The assistant supports analysis of:

- Corrosion images
- Microscopy
- Material failures
- Surface degradation
- Technical diagrams

`POST /api/v1/upload/image` returns a textual description produced by GPT-4o; the user can then send the description (or a derived question) through `/chat`.

---

# 11.2 Audio Support

`POST /api/v1/upload/audio` returns a Whisper transcript. The transcript can then be used as input for `/chat`.

---

# 12. API Architecture

---

# 12.1 Logical Services

| Service | Responsibility | Code location |
|---|---|---|
| Auth Service | Clerk JWT validation (RS256 / HS256 fallback) | `backend/app/api/deps.py` |
| Chat Service | Conversation orchestration + SSE streaming | `backend/app/services/chat.py` |
| Retrieval Service | Qdrant query with `user_id` filtering | `backend/app/services/retrieval.py` |
| Reranking Service | Optional Cohere rerank | `backend/app/services/reranking.py` |
| Ingestion Service | PDF parsing, chunking, embedding, status callbacks | `backend/app/services/ingestion.py` |
| Document Service | CRUD for `documents` (`POST/GET/GET-{id}/DELETE`) | `backend/app/api/routes/documents.py` |
| Storage Provider | Abstract object storage + Supabase implementation | `backend/app/storage/` |
| Persistence Layer | SQLAlchemy 2.0 async + sync sessions | `backend/app/db/` |

---

# 12.2 Endpoint Map

| Method | Path | Auth | Purpose |
|---|---|---|---|
| `GET` | `/api/v1/health` | No | Health probe |
| `GET` | `/api/v1/metrics` | No | Latency + citation metrics |
| `POST` | `/api/v1/chat` | Yes | Streaming SSE chat |
| `POST` | `/api/v1/documents` | Yes | Upload PDF (returns 202, async ingestion) |
| `GET` | `/api/v1/documents` | Yes | List user's documents |
| `GET` | `/api/v1/documents/{id}` | Yes | Document status |
| `DELETE` | `/api/v1/documents/{id}` | Yes | Delete document (Qdrant + Supabase + Postgres) |
| `POST` | `/api/v1/upload/image` | Yes | Image description (GPT-4o) |
| `POST` | `/api/v1/upload/audio` | Yes | Audio transcription (Whisper) |

---

# 13. Deployment Strategy

---

# 13.1 Infrastructure

| Layer | Provider / Component |
|---|---|
| Frontend | Docker container (Next.js standalone) |
| Backend | Docker container (FastAPI / Uvicorn) |
| Worker | Docker container (Celery) |
| Vector DB | Qdrant (Docker) |
| Cache / Broker | Redis 7 (Docker) |
| Relational DB | PostgreSQL 16 (Docker) |
| Object Storage | Supabase Storage (managed SaaS) |
| Secrets | `.env` files (dev) / orchestrator secrets (prod) |

---

# 13.2 Deployment Goals

- Fast iteration
- Low operational complexity
- Simple CI/CD
- Container-ready architecture
- Clear separation between sync API and async workers

---

# 14. Future Roadmap

---

# Phase 1 — Core RAG Assistant (✅ implemented)

- PDF ingestion (per-user)
- Chat interface with streaming
- Semantic retrieval (filtered by `user_id`)
- Citations
- Clerk authentication
- Postgres-backed document lifecycle
- Supabase Storage for binaries

---

# Phase 2 — Advanced Retrieval

- Hybrid search (sparse + dense)
- Improved re-ranking strategies
- Metadata filtering UI in the frontend
- Retrieval observability dashboards
- Alembic migrations adopted in place of `create_all`

---

# Phase 3 — Multimodal Intelligence

- Inline image attachments within `/chat`
- Technical diagram interpretation
- Comparative material analysis

---

# Phase 4 — Specialized Engineering Copilot

- Multi-agent workflows
- Standards validation
- Failure prediction assistance
- Technical report generation

---

# 15. Success Metrics

| Metric | Target |
|---|---|
| Retrieval Precision | > 85% |
| Response Satisfaction | > 90% |
| Average Response Time | < 8s |
| Citation Coverage | 100% |
| Hallucination Rate | < 5% |

---

# 16. Risks and Challenges

| Risk | Mitigation |
|---|---|
| Poor chunking quality | Structural-semantic chunking with overlap |
| Hallucinations | Strict grounding prompts + empty-context guard |
| Low retrieval precision | Optional Cohere re-ranking |
| OCR failures | OCR fallback strategy via GPT-4o (opt-in) |
| Large PDFs | Async Celery ingestion with retry + checkpointing |
| Per-user data leakage | Mandatory `user_id` filter on all Qdrant queries; ownership enforced at DB layer |
| Supabase outage | Object storage abstraction (`StorageProvider`) allows future provider swap |

---

# 17. Final Considerations

The Materials Knowledge Assistant is not intended to replace engineering expertise.

Its purpose is to augment technical reasoning by enabling fast, traceable, and contextual access to specialized literature.

The core competitive advantage of the platform lies in:

- Domain specialization
- High-quality retrieval
- Grounded technical reasoning
- Citation-based trust
- Multimodal interaction
- Engineering-oriented UX
- Per-user privacy and isolation
