# RAG Architecture Specification (RAS)
## Materials Knowledge Assistant (MKA)

Version: 2.0
Status: Aligned with current implementation
Author: Carlos Eduardo
Date: May 2026

---

# 1. Introduction

## 1.1 Purpose

This document defines the Retrieval-Augmented Generation (RAG) architecture specification for the Materials Knowledge Assistant (MKA), reflecting the implementation as of May 2026.

The purpose of this specification is to provide a detailed technical definition of:

- Retrieval architecture (with mandatory per-user filtering)
- Document ingestion workflows (synchronous HTTP path + asynchronous Celery worker)
- Semantic indexing strategy
- Chunking methodology
- Metadata enrichment
- Retrieval orchestration
- Re-ranking mechanisms (optional)
- Context assembly
- Citation generation
- Hallucination mitigation (empty-context guard)
- Evaluation strategy
- Performance optimization

This document operationalizes the RAG-related requirements defined in the PRD and expands the architectural decisions described in the SAD.

---

# 1.2 Scope

This specification covers:

- PDF ingestion architecture (Supabase Storage + Celery + Qdrant)
- Semantic retrieval pipeline with per-user filtering
- Embedding strategy
- Vector indexing
- Metadata modeling
- Retrieval ranking
- Prompt context construction
- Citation architecture
- Retrieval observability
- Evaluation and benchmarking targets

This specification does not cover:

- Frontend implementation details (see Frontend Spec)
- Generic API specifications (see Backend Spec)
- Infrastructure provisioning (see SAD §16)
- Fine-tuning pipelines
- Multi-agent orchestration
- Persistent conversational memory

---

# 1.3 Architectural Objectives

The RAG architecture is designed to achieve the following goals:

| Objective | Description |
|---|---|
| Grounded Responses | Answers must be based on the user's indexed literature |
| Per-User Isolation | A user can only retrieve their own chunks |
| High Retrieval Precision | Maximize relevance of retrieved engineering content |
| Traceability | Preserve citations and provenance (source, chapter, section, page) |
| Low Hallucination Rate | Reduce unsupported generation; empty-context guard short-circuits the LLM |
| Engineering Context Preservation | Maintain semantic integrity of technical content |
| Scalability | Support corpus growth via incremental Qdrant indexing |
| Extensibility | Enable future hybrid retrieval and reranker swaps |

---

# 2. RAG System Overview

## 2.1 High-Level Architecture

```text
                  ┌─────────────────────┐
                  │     User Query      │
                  │ (Bearer Clerk JWT)  │
                  └──────────┬──────────┘
                             ▼
                  ┌─────────────────────┐
                  │  user_id Extraction │
                  └──────────┬──────────┘
                             ▼
                  ┌─────────────────────┐
                  │ Query Embedding     │
                  │ text-embedding-3-sm │
                  └──────────┬──────────┘
                             ▼
                  ┌──────────────────────────┐
                  │  Qdrant Dense Search     │
                  │  Filter:  must={user_id} │
                  │           + metadata     │
                  │  Limit:   top-K (20)     │
                  └──────────┬───────────────┘
                             ▼
                  ┌─────────────────────┐
                  │ [optional]          │
                  │ Cohere Re-ranking   │
                  │ top-K → top-N (5)   │
                  └──────────┬──────────┘
                             ▼
                  ┌─────────────────────┐
                  │ Empty-context Guard │
                  │ (deterministic      │
                  │  fallback if empty) │
                  └──────────┬──────────┘
                             ▼
                  ┌─────────────────────┐
                  │ Prompt Assembly     │
                  │ SYSTEM_PROMPT +     │
                  │ retrieved context   │
                  └──────────┬──────────┘
                             ▼
                  ┌─────────────────────┐
                  │ LLM Streaming       │
                  │ OpenAI chat (SSE)   │
                  └──────────┬──────────┘
                             ▼
                  ┌─────────────────────┐
                  │ Citation Formatter  │
                  │ (event: citations)  │
                  └─────────────────────┘
```

Sparse retrieval is not active in V1 (`SPARSE_RETRIEVAL_ENABLED=false`).

---

# 3. Document Ingestion Architecture

## 3.1 Ingestion Pipeline (Sync + Async)

```text
HTTP path (synchronous)               Worker path (asynchronous)
────────────────────────────          ─────────────────────────────────────
POST /api/v1/documents                 mka.ingest_document(document_id)
   ↓                                       ↓
File Validation (PDF, size)            status → "processing"
   ↓                                       ↓
Filename sanitization                  Download blob from Supabase Storage
   ↓                                       ↓
Upload bytes to Supabase Storage       Extract pages (pypdf)
at {user_id}/{document_id}/file.pdf       ↓
   ↓                                   OCR fallback (opt-in, GPT-4o)
Insert documents row (pending)            ↓
   ↓                                   Structural chunking          → "chunking"
Enqueue Celery task                       ↓
   ↓                                   Embedding generation         → "embedding"
Return 202 + {document_id, status}        ↓
                                       Qdrant upsert (with user_id,
                                         document_id, metadata)
                                          ↓
                                       Update row → "indexed" / "error"
                                       (chunk_count populated on success;
                                        indexing_error populated on failure)
```

Implementation references:

- HTTP handler: `backend/app/api/routes/documents.py`
- Celery task: `backend/app/workers/tasks.py:ingest_document_task` (`mka.ingest_document`)
- Core ingestion logic: `backend/app/services/ingestion.py:ingest_pdf_bytes`

---

## 3.2 Status Callback Contract

The ingestion function accepts a `status_callback(status: str)` invoked at each stage transition. The Celery task wires this callback to a synchronous Postgres update, ensuring the document row reflects progress in near-real-time for frontend polling.

Stage transitions:

```text
pending  →  processing  →  chunking  →  embedding  →  indexed
                                          │
                                          └─ (on exception) → error
```

The Celery task uses `bind=True, max_retries=3` with exponential backoff (countdown=30s) for transient failures.

---

# 4. Chunking Specification

## 4.1 Chunking Objectives

The chunking strategy must:

- Preserve semantic coherence
- Preserve engineering reasoning
- Improve retrieval precision
- Reduce context fragmentation
- Maintain citation traceability

---

## 4.2 Chunk Parameters

| Parameter | Default | Source |
|---|---|---|
| Chunk size | ~1,200 words (≈ 800–1500 tokens) | constant in `services/ingestion.py` |
| Chunk overlap | ~200 words (≈ 15–20%) | constant in `services/ingestion.py` |
| Retrieval candidates | Top 20 | `RETRIEVAL_TOP_K_CANDIDATES` |
| Final context | Top 5 | `RETRIEVAL_TOP_K_FINAL` |

---

## 4.3 Chunking Algorithm

`_chunk_by_structure(page_text)` in `services/ingestion.py`:

1. Attempt structural splitting (numbered headings like `3.2 Corrosion`, uppercase headings).
2. If structural cues yield reasonable chunks, return them along with the section heading.
3. Otherwise, fall back to word-based chunking (`~1,200` words with `~200` overlap).

`_detect_structure(page_text)` produces auxiliary metadata:

- Chapter (regex over uppercase lines or "Capítulo N")
- Section (regex over numbered headings)
- Material type (keyword match: steel, copper, aluminum, etc.)

---

# 5. Metadata Architecture

## 5.1 Required Metadata Fields (Qdrant payload)

| Field | Source / Notes |
|---|---|
| `source` | PDF filename |
| `source_id` | SHA-256 of the PDF bytes (deduplication) |
| `user_id` | From Clerk JWT (mandatory for per-user retrieval) |
| `document_id` | UUID from the `documents` row (mandatory for delete-by-document) |
| `page` | Integer page number |
| `chunk_id` | Stable identifier derived from `(page_num, chunk_idx)` |
| `text` | Raw chunk text |
| `document_type` | Heuristic: Book / Paper / Standard |
| `ingestion_timestamp` | ISO-8601 UTC |
| `author` | Extracted from PDF metadata when available |
| `title` | Extracted from PDF metadata when available |
| `chapter` | Heuristic detection |
| `section` | Heuristic detection |
| `material_type` | Keyword-based (steel, copper, aluminum, …) |
| `environment` | Reserved (currently `None`) |

The point ID itself is generated by `_user_point_id(user_id, document_id, page_num, chunk_idx)`, ensuring idempotency on re-ingestion of the same document.

---

# 6. Embedding Architecture

## 6.1 Embedding Model Strategy

| Capability | Default | Configurable via |
|---|---|---|
| Primary embeddings | `text-embedding-3-small` (1536-d) | `OPENAI_EMBEDDING_MODEL` |
| Vector dimension | 1536 | `QDRANT_VECTOR_SIZE` |

Future direction: domain-specific embeddings for materials/engineering corpora. Not in V1.

## 6.2 Batching

Embeddings are generated in batches by `openai_client.embed_texts`. The batch size is bounded by the OpenAI API limits.

---

# 7. Vector Database Architecture

## 7.1 Vector Database Selection

The system uses Qdrant v1.11.3 as the primary vector database.

Selection rationale:

- High retrieval performance
- Native payload filtering (load-bearing for per-user isolation)
- Incremental indexing support
- Operational simplicity (single container)
- Cloud deployment flexibility

## 7.2 Collection Design

Single collection: `engineering_documents` (configurable via `QDRANT_COLLECTION`).

Per-user partitioning is handled by payload filtering, not by separate collections. This keeps operational complexity low while still ensuring isolation through mandatory `must={user_id}` clauses in every search.

---

# 8. Retrieval Architecture

## 8.1 Retrieval Pipeline

```text
User Query (authenticated)
    ↓
Query Embedding (1536-d)
    ↓
Qdrant Dense Search
   filter = Filter(must=[
     FieldCondition(key="user_id",   value=<from JWT>),
     FieldCondition(key=<filter_k>,  value=<filter_v>)  for each metadata_filters entry
   ])
   limit  = RETRIEVAL_TOP_K_CANDIDATES (default 20)
    ↓
[optional] Cohere Rerank (when COHERE_API_KEY set)
    ↓
Top-N (RETRIEVAL_TOP_K_FINAL, default 5)
    ↓
Empty-context Guard
    ↓
Prompt Assembly
```

The handler is `services/retrieval.py:retrieve_context(client, query_vector, metadata_filters, limit, user_id)`.

---

## 8.2 Empty-context Guard

After retrieval (and optional rerank), if the chunk list is empty:

- The chat service short-circuits and does NOT invoke the LLM.
- It returns a deterministic fallback message (Portuguese): "A literatura técnica indexada não fornece evidência suficiente para responder a esta questão."
- The SSE stream still emits a `token` event with the fallback message, an empty `citations` event, and a `done` event.

This is the primary anti-hallucination mechanism.

---

# 9. Re-ranking Architecture

## 9.1 Implementation

The reranker is `services/reranking.py:CohereReranker`, which wraps `cohere.AsyncClientV2`.

| Aspect | Detail |
|---|---|
| Model | `rerank-english-v3.0` (configurable via `RERANKER_MODEL`) |
| Activation | Only initialized when `COHERE_API_KEY` is set |
| Fallback | When disabled, top-N is taken directly from Qdrant's top-K |

## 9.2 Future Reranker Options

| Model | Type | Status |
|---|---|---|
| Cohere `rerank-english-v3.0` | API-based | ✅ implemented |
| BAAI/bge-reranker-large | Cross-encoder | future option |
| Jina Reranker | Cross-encoder | future option |

---

# 10. Context Assembly Architecture

## 10.1 Context Assembly Goals

The context builder must:

- Maximize relevance
- Reduce redundancy (handled implicitly by reranker)
- Preserve citation metadata alongside each chunk
- Respect the LLM token budget
- Preserve engineering reasoning chains across consecutive chunks

## 10.2 Implementation Notes

The chat service (`services/chat.py:stream_chat`) builds the system + user prompts using:

- The retrieved chunks (text + metadata)
- The user query
- The `SYSTEM_PROMPT` defined in `backend/app/rag/prompts.py`

The order of chunks follows the reranker output (or the Qdrant order when reranking is disabled).

---

# 11. Prompt Grounding Specification

## 11.1 Grounding Rules

The assistant must:

- Only answer using retrieved evidence
- Explicitly state uncertainty
- Avoid unsupported assumptions
- Prefer omission over speculation

These rules are enforced by the system prompt at `backend/app/rag/prompts.py:SYSTEM_PROMPT`.

## 11.2 Anti-Hallucination Mechanisms

1. **Empty-context guard** — deterministic fallback without invoking the LLM (Section 8.2).
2. **Grounding instructions** — the system prompt forbids ungrounded claims.
3. **Citation enforcement** — every assistant response is paired with a `citations` event derived from the chunks actually fed to the LLM.

---

# 12. Citation Architecture

## 12.1 Citation Objectives

The citation layer provides:

- Traceability
- Engineering confidence
- Auditability
- Literature verification

## 12.2 Citation Schema

Defined in `backend/app/api/schemas/chat.py:Citation`:

```python
class Citation(BaseModel):
    source: str
    chapter: str | None = None
    section: str | None = None
    page: int | None = None
    excerpt: str
```

The excerpt is the first ~220 characters of the chunk text. Citations are emitted via an SSE event (`event: citations`) after the final token is streamed.

---

# 13. Multimodal Retrieval Architecture

## 13.1 Image Flow

```text
POST /api/v1/upload/image
    ↓
GPT-4o (VISION_PROMPT)
    ↓
Textual description
    ↓
(user may send this description into /chat as the query)
    ↓
Standard RAG pipeline (Section 2.1)
```

## 13.2 Audio Flow

```text
POST /api/v1/upload/audio
    ↓
Whisper-1
    ↓
Transcript
    ↓
(user may send this transcript into /chat as the query)
    ↓
Standard RAG pipeline (Section 2.1)
```

Both flows return a textual artifact; they do not auto-invoke retrieval.

---

# 14. Observability and Evaluation

## 14.1 Retrieval Metrics

Implemented (in-memory ring buffer, exposed via `GET /api/v1/metrics`):

| Metric | Description |
|---|---|
| p50 / p95 retrieval latency | Time from query to top-K chunks |
| p50 / p95 LLM latency | Time from first to last streamed token |
| Citation Coverage | % of responses with at least one citation |
| Error rate | Failed requests over the sample window |

Aspirational (not currently computed):

| Metric | Description |
|---|---|
| Recall@K | Retrieval completeness |
| Precision@K | Retrieval precision |
| MRR | Mean Reciprocal Rank |
| Hallucination Rate | Unsupported claims (requires labeled eval set) |

---

# 15. Performance and Scalability

## 15.1 Performance Targets

| Metric | Target |
|---|---|
| Retrieval Latency (p95) | < 2 seconds |
| End-to-end Response Time (p95) | < 8 seconds |
| Citation Coverage | 100% |
| Hallucination Rate | < 5% |
| Upload HTTP path | < 3 seconds (returns 202) |

## 15.2 Scalability Notes

- Qdrant is the primary scaling concern as the corpus grows — payload indexing on `user_id` should be added if collection size becomes large.
- The Celery worker pool scales horizontally; ingestion throughput is bounded by OpenAI rate limits (embedding).
- Frontend polling at 3-second intervals is acceptable while user counts are low; long-polling or WebSockets are options for future scale.

---

# 16. Risks and Mitigations

| Risk | Mitigation |
|---|---|
| Poor chunking quality | Hybrid structural + word-based chunking with overlap |
| Low retrieval precision | Optional Cohere re-ranking |
| Hallucinations | Strict grounding prompt + empty-context guard |
| OCR inaccuracies | GPT-4o vision fallback (opt-in) |
| Large PDF processing | Async Celery pipeline with retry |
| Embedding cost growth | Batched embedding API calls |
| Token overflows | Bounded top-N context (default 5 chunks) |
| Per-user data leakage | Mandatory `user_id` filter on every retrieval call |
| Re-ingestion of the same document | Deterministic point IDs ensure idempotency |
| Default invalid LLM model (`gpt-5.4`) | Operators override `OPENAI_CHAT_MODEL` until default is corrected |

---

# 17. Conclusion

The RAG architecture of the Materials Knowledge Assistant prioritizes:

- Retrieval quality (semantic + optional rerank)
- Engineering traceability (rich metadata, citation enforcement)
- Semantic integrity (structural chunking)
- Grounded AI reasoning (empty-context guard, strict prompt)
- Per-user privacy (mandatory `user_id` filtering)
- Low operational complexity (single Qdrant collection, single OpenAI dependency)

The architecture intentionally emphasizes high-confidence technical retrieval and citation-backed generation to support engineering workflows where precision and trustworthiness are essential.
