# Backend Specification (BES)
## Materials Knowledge Assistant (MKA)

Version: 1.0  
Status: Draft  
Author: Carlos Eduardo  
Date: May 2026

---

# 1. Purpose

This document defines the backend implementation specification for the Materials Knowledge Assistant (MKA).

The specification translates the architectural decisions defined in the PRD, SAD, and RAG Architecture Specification into actionable backend engineering guidelines.

The backend is responsible for:

- API exposure
- AI orchestration
- Retrieval execution
- Document ingestion
- Embedding generation
- Citation formatting
- Authentication validation
- Multimodal processing
- Observability and logging

---

# 2. Backend Technology Stack

| Layer | Technology |
|---|---|
| API Framework | FastAPI |
| Language | Python 3.12+ |
| Validation | Pydantic |
| AI Orchestration | LangChain |
| Async Runtime | Uvicorn |
| Background Processing | Celery or Async Tasks |
| Vector Database | Qdrant |
| Embeddings | OpenAI Embeddings |
| LLM Provider | OpenAI |
| Containerization | Docker |
| Dependency Management | Poetry or UV |
| Observability | OpenTelemetry + Structured Logs |

---

# 3. Backend Architectural Principles

The backend implementation should prioritize:

- Stateless APIs
- Modular services
- Async-first processing
- Strong typing
- Structured observability
- Clear separation of concerns
- Retrieval-grounded AI responses
- Security-first implementation

---

# 4. Project Structure

```text
backend/
│
├── app/
│   ├── api/
│   │   ├── routes/
│   │   ├── dependencies/
│   │   ├── middleware/
│   │   └── schemas/
│   │
│   ├── core/
│   │   ├── config/
│   │   ├── logging/
│   │   ├── security/
│   │   └── exceptions/
│   │
│   ├── services/
│   │   ├── chat/
│   │   ├── retrieval/
│   │   ├── ingestion/
│   │   ├── embeddings/
│   │   ├── citations/
│   │   ├── multimodal/
│   │   └── auth/
│   │
│   ├── rag/
│   │   ├── chunking/
│   │   ├── reranking/
│   │   ├── prompts/
│   │   ├── metadata/
│   │   └── retrieval/
│   │
│   ├── integrations/
│   │   ├── openai/
│   │   ├── qdrant/
│   │   └── clerk/
│   │
│   ├── workers/
│   └── main.py
│
├── tests/
├── Dockerfile
├── pyproject.toml
└── README.md
```

---

# 5. API Specification

## 5.1 Base URL

```text
/api/v1
```

---

## 5.2 Endpoints

| Endpoint | Method | Description |
|---|---|---|
| /chat | POST | Main conversational endpoint |
| /upload/pdf | POST | Upload and ingest PDFs |
| /upload/image | POST | Upload image for analysis |
| /upload/audio | POST | Upload audio for transcription |
| /documents | GET | List indexed documents |
| /health | GET | Health check |
| /metrics | GET | Metrics endpoint |

---

# 6. Authentication Specification

## 6.1 Authentication Strategy

Authentication uses:

- Google OAuth
- Clerk session management
- JWT validation

---

## 6.2 Backend Responsibilities

The backend must:

- Validate Clerk JWT tokens
- Protect private endpoints
- Attach user context to requests
- Reject unauthenticated requests

---

## 6.3 Protected Routes

The following routes require authentication:

- /chat
- /upload/*
- /documents

---

# 7. Chat Service Specification

## 7.1 Responsibilities

The Chat Service is responsible for:

- Receiving user prompts
- Executing retrieval pipeline
- Building prompts
- Calling the LLM
- Streaming responses
- Formatting citations

---

## 7.2 Request Schema

```json
{
  "message": "What corrosion risks exist for carbon steel in marine environments?",
  "attachments": [],
  "metadata_filters": {
    "material_type": "Carbon Steel"
  }
}
```

---

## 7.3 Response Schema

```json
{
  "answer": "Carbon steel exposed to chloride-rich marine environments...",
  "citations": [
    {
      "source": "callister_materials_science.pdf",
      "page": 248,
      "section": "Galvanic Corrosion"
    }
  ]
}
```

---

## 7.4 Streaming Strategy

Responses should be streamed using:

- Server-Sent Events (SSE)
- Incremental token emission

Benefits:

- Better UX
- Lower perceived latency
- Faster interaction cycles

---

# 8. Retrieval Service Specification

## 8.1 Responsibilities

The Retrieval Service must:

- Generate query embeddings
- Execute vector search
- Apply metadata filters
- Aggregate candidates
- Execute re-ranking

---

## 8.2 Retrieval Pipeline

```text
User Query
    ↓
Embedding Generation
    ↓
Dense Retrieval
    ↓
Metadata Filtering
    ↓
Candidate Aggregation
    ↓
Cross-Encoder Re-ranking
    ↓
Top-K Selection
```

---

## 8.3 Retrieval Parameters

| Parameter | Value |
|---|---|
| Initial Candidates | Top 20 |
| Final Chunks | Top 5 |
| Similarity Metric | Cosine Similarity |
| Chunk Overlap | 15–20% |
| Chunk Size | 800–1500 tokens |

---

# 9. Ingestion Service Specification

## 9.1 Responsibilities

The Ingestion Service must:

- Validate uploaded files
- Parse PDFs
- Execute OCR fallback
- Generate semantic chunks
- Extract metadata
- Generate embeddings
- Index vectors in Qdrant

---

## 9.2 Ingestion Pipeline

```text
PDF Upload
    ↓
Validation
    ↓
Parsing
    ↓
OCR Fallback
    ↓
Chunking
    ↓
Metadata Enrichment
    ↓
Embedding Generation
    ↓
Qdrant Indexing
```

---

## 9.3 File Validation Rules

| Rule | Requirement |
|---|---|
| Accepted Format | PDF |
| Max File Size | 100MB |
| Virus Scan | Recommended |
| Duplicate Detection | Optional |

---

# 10. Embedding Service Specification

## 10.1 Responsibilities

The Embedding Service must:

- Batch embedding requests
- Retry failed operations
- Track token usage
- Optimize embedding throughput

---

## 10.2 Embedding Strategy

| Capability | Model |
|---|---|
| Main Embeddings | OpenAI Embeddings |
| Future Support | Domain-specific embeddings |

---

# 11. Citation Service Specification

## 11.1 Responsibilities

The Citation Service must:

- Build source references
- Format citations
- Preserve provenance metadata
- Attach page and section references

---

## 11.2 Citation Structure

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

# 12. Multimodal Service Specification

## 12.1 Image Processing

Supported image use cases:

- Corrosion analysis
- Surface degradation
- Microscopy
- Technical diagrams

---

## 12.2 Audio Processing

Audio uploads should:

- Be transcribed
- Converted into text queries
- Routed through the RAG pipeline

---

# 13. Error Handling Specification

## 13.1 Error Principles

The API should provide:

- Structured errors
- Traceable request IDs
- User-safe messages
- Internal debugging metadata

---

## 13.2 Example Error Response

```json
{
  "error": {
    "code": "RETRIEVAL_FAILURE",
    "message": "Unable to retrieve relevant documents.",
    "request_id": "req_12345"
  }
}
```

---

# 14. Observability Specification

## 14.1 Logging

Structured logs must include:

- Request ID
- User ID (hashed)
- Retrieval latency
- Embedding latency
- LLM latency
- Errors

---

## 14.2 Metrics

| Metric | Description |
|---|---|
| Retrieval Latency | Retrieval duration |
| LLM Latency | Generation duration |
| Error Rate | Failed requests |
| Citation Coverage | Citation completeness |
| Token Usage | LLM token consumption |

---

# 15. Security Specification

## 15.1 Security Goals

The backend must ensure:

- Secure authentication
- HTTPS-only communication
- Private document handling
- Secret isolation
- Secure file uploads

---

## 15.2 Secret Management

Secrets should be managed through:

- Railway Variables
- Docker Secrets
- CI/CD secret injection

Secrets must never be hardcoded.

---

# 16. Deployment Specification

## 16.1 Deployment Strategy

The backend should be deployed as a Dockerized FastAPI service.

---

## 16.2 Suggested Infrastructure

| Layer | Provider |
|---|---|
| Backend Hosting | Railway |
| Vector Database | Qdrant Cloud |
| LLM Provider | OpenAI |
| Object Storage | Cloud Storage |

---

# 17. Testing Strategy

## 17.1 Testing Types

| Test Type | Objective |
|---|---|
| Unit Tests | Validate isolated services |
| Integration Tests | Validate service interaction |
| Retrieval Tests | Validate retrieval quality |
| API Tests | Validate endpoints |
| Load Tests | Validate scalability |

---

# 18. Performance Targets

| Metric | Target |
|---|---|
| Retrieval Latency | < 2 seconds |
| Response Time | < 8 seconds |
| Citation Coverage | 100% |
| Hallucination Rate | < 5% |

---

# 19. Future Evolution

Future backend evolution may include:

- Multi-agent orchestration
- Hybrid retrieval
- Persistent memory
- Advanced observability
- Evaluation pipelines
- Workflow automation

---

# 20. Conclusion

The backend architecture of the Materials Knowledge Assistant prioritizes:

- Reliability
- Retrieval quality
- Grounded AI generation
- Maintainability
- Operational simplicity
- Future scalability
