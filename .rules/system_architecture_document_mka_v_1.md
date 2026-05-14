# System Architecture Document (SAD)
## Materials Knowledge Assistant (MKA)

Version: 1.0  
Status: Draft  
Author: Carlos Eduardo  
Date: May 2026

---

# 1. Introduction

## 1.1 Purpose

This System Architecture Document (SAD) defines the technical architecture of the Materials Knowledge Assistant (MKA), including its system components, infrastructure strategy, service responsibilities, integration patterns, deployment topology, security model, observability approach, and scalability considerations.

The purpose of this document is to:

- Establish the architectural foundation of the platform
- Align implementation decisions across frontend, backend, and AI infrastructure
- Support scalable and maintainable development
- Reduce technical ambiguity during implementation
- Serve as a reference for future system evolution
- Enable future extensibility toward advanced AI workflows

This document complements the Product Requirements Document (PRD) and translates product-level requirements into technical architectural decisions.

---

## 1.2 Scope

This document covers the architecture of Version 1 (V1) of the Materials Knowledge Assistant.

The architecture includes:

- Frontend application
- Backend APIs
- Authentication flow
- Retrieval-Augmented Generation (RAG) pipeline
- Document ingestion pipeline
- Vector database architecture
- AI orchestration layer
- Multimodal processing
- Observability and logging
- Infrastructure and deployment
- Security model
- Scalability strategy

The document does not cover:

- Detailed UI design specifications
- Detailed prompt templates
- Fine-tuning strategies
- Multi-agent orchestration
- Enterprise multi-tenancy
- ERP or external enterprise integrations

---

## 1.3 Related Documents

| Document | Description |
|---|---|
| PRD | Product Requirements Document |
| API Specification | REST endpoint specifications |
| Database Design Document | Metadata and storage schemas |
| Prompt Engineering Guide | LLM prompting strategy |
| Deployment Runbook | Infrastructure deployment procedures |
| Security Architecture Document | Security controls and compliance |

---

# 2. Architectural Goals

The architecture was designed according to the following engineering principles.

---

## 2.1 Modularity

The system should be divided into loosely coupled services with clear responsibilities.

Benefits:

- Easier maintenance
- Independent evolution
- Better testing
- Simplified debugging
- Future service extraction

---

## 2.2 Scalability

The architecture should support future horizontal scaling for:

- Retrieval workloads
- Embedding generation
- Concurrent users
- Large document collections
- AI inference throughput

---

## 2.3 Reliability

The system should prioritize:

- Stable retrieval behavior
- Predictable response generation
- Graceful degradation
- Traceability of failures
- Retry-safe operations

---

## 2.4 Observability

The platform must provide:

- Structured logs
- Request tracing
- Retrieval diagnostics
- AI execution monitoring
- Error visibility
- Performance metrics

---

## 2.5 AI Grounding

The architecture must minimize hallucinations by:

- Strict retrieval grounding
- Context-bound generation
- Citation enforcement
- Re-ranking validation
- Retrieval confidence monitoring

---

## 2.6 Simplicity First

Version 1 prioritizes:

- Low operational complexity
- Rapid iteration
- Maintainability
- Small infrastructure footprint
- Fast deployment cycles

---

# 3. High-Level System Architecture

## 3.1 Architectural Overview

The system follows a layered architecture composed of:

1. Client Layer
2. Application Layer
3. AI Orchestration Layer
4. Retrieval Layer
5. Storage Layer
6. External AI Providers

---

## 3.2 High-Level Flow

```text
+-------------------+
|   Web Frontend    |
| Next.js + Clerk   |
+---------+---------+
          |
          v
+-------------------+
|    FastAPI API    |
| Application Layer |
+---------+---------+
          |
          v
+-------------------+
| LangChain Runtime |
| AI Orchestration  |
+----+---------+----+
     |         |
     |         |
     v         v
+---------+  +----------------+
| Qdrant |  | OpenAI Services |
| Vector |  | GPT + Embedding |
|   DB   |  +----------------+
+----+---+
     |
     v
+-------------------+
| Document Storage  |
| Metadata + PDFs   |
+-------------------+
```

---

## 3.3 Architectural Style

The platform adopts:

- Service-oriented backend design
- API-first communication
- Retrieval-Augmented Generation (RAG)
- Stateless request handling
- Asynchronous ingestion operations

---

# 4. Frontend Architecture

## 4.1 Technology Stack

| Layer | Technology |
|---|---|
| Framework | Next.js |
| Language | TypeScript |
| Styling | TailwindCSS |
| UI Components | shadcn/ui |
| Authentication | Clerk |
| State Management | React Context + Hooks |
| API Communication | REST + Streaming |
| Hosting | Vercel or Railway |

---

## 4.2 Frontend Responsibilities

The frontend is responsible for:

- User authentication
- Chat interaction
- File uploads
- Rendering citations
- Streaming responses
- Responsive layout
- Conversation session management
- Upload progress tracking

---

## 4.3 UI Modules

| Module | Responsibility |
|---|---|
| Auth Module | Google OAuth authentication |
| Chat Module | Conversational interface |
| Upload Module | File upload management |
| Citation Renderer | Citation visualization |
| Markdown Renderer | Structured response rendering |
| Streaming Handler | Incremental token rendering |
| Session Manager | Active session state |

---

## 4.4 Frontend Communication

The frontend communicates with the backend through:

- REST endpoints
- Streaming HTTP responses
- Multipart upload endpoints

Authentication tokens are attached to all protected requests.

---

## 4.5 Frontend Design Principles

The UI should prioritize:

- Technical readability
- Minimal cognitive load
- Engineering-oriented workflows
- Clear citations
- High information density without clutter

---

# 5. Backend Architecture

## 5.1 Technology Stack

| Layer | Technology |
|---|---|
| API Framework | FastAPI |
| Language | Python |
| AI Orchestration | LangChain |
| Validation | Pydantic |
| Async Runtime | Uvicorn |
| Background Jobs | Celery or Async Tasks |
| Containerization | Docker |

---

## 5.2 Backend Responsibilities

The backend is responsible for:

- Authentication validation
- Chat orchestration
- Retrieval execution
- Prompt assembly
- LLM interaction
- Citation formatting
- File ingestion
- Embedding generation
- Metadata enrichment
- Observability logging

---

## 5.3 Backend Service Decomposition

### Auth Service

Responsibilities:

- Validate Clerk tokens
- Protect API routes
- Attach user context

---

### Chat Service

Responsibilities:

- Receive user queries
- Manage orchestration flow
- Trigger retrieval pipeline
- Stream LLM responses

---

### Retrieval Service

Responsibilities:

- Query Qdrant
- Execute metadata filtering
- Run hybrid search
- Perform re-ranking

---

### Ingestion Service

Responsibilities:

- Parse uploaded PDFs
- Execute chunking pipeline
- Generate embeddings
- Store vectors and metadata

---

### Embedding Service

Responsibilities:

- Generate embeddings
- Batch embedding requests
- Retry failed operations
- Track embedding costs

---

### Citation Service

Responsibilities:

- Build source references
- Format citations
- Attach metadata provenance

---

# 6. AI Orchestration Architecture

## 6.1 Orchestration Strategy

The orchestration layer is implemented using LangChain.

The initial architecture intentionally avoids LangGraph in V1 to reduce complexity.

This decision is based on:

- Linear execution flows
- Predictable retrieval pipelines
- Faster implementation
- Lower debugging complexity
- Simpler observability

---

## 6.2 Orchestration Pipeline

```text
User Query
    ↓
Input Validation
    ↓
Embedding Generation
    ↓
Retrieval Execution
    ↓
Metadata Filtering
    ↓
Re-ranking
    ↓
Prompt Assembly
    ↓
LLM Generation
    ↓
Citation Formatting
    ↓
Streaming Response
```

---

## 6.3 Prompt Assembly Strategy

Prompt construction should include:

- Retrieved chunks
- Metadata references
- Citation identifiers
- User query
- System grounding instructions

The prompt should explicitly:

- Restrict unsupported assumptions
- Enforce grounded answers
- Require citation references
- Encourage uncertainty disclosure

---

## 6.4 LLM Strategy

| Capability | Model |
|---|---|
| Main Reasoning | GPT-4.1 |
| Vision Processing | GPT-4o |
| Lightweight Operations | GPT-4.1-mini |
| Embeddings | OpenAI Embeddings |

---

## 6.5 Hallucination Mitigation

The orchestration layer must:

- Reject empty retrieval contexts
- Detect low-confidence retrieval
- Limit generation to retrieved evidence
- Enforce citation-backed claims
- Prefer omission over speculation

---

# 7. Retrieval-Augmented Generation (RAG) Architecture

## 7.1 RAG Overview

The platform uses Retrieval-Augmented Generation to ground AI responses in indexed technical literature.

The retrieval pipeline combines:

- Semantic retrieval
- Metadata filtering
- Optional keyword retrieval
- Re-ranking
- Context compression

---

## 7.2 Retrieval Pipeline

```text
User Query
    ↓
Query Embedding
    ↓
Dense Vector Search
    ↓
Metadata Filtering
    ↓
Optional Sparse Search
    ↓
Candidate Aggregation
    ↓
Cross-Encoder Re-ranking
    ↓
Top-K Context Selection
    ↓
Prompt Injection
```

---

## 7.3 Retrieval Parameters

| Parameter | Value |
|---|---|
| Initial Retrieval | Top 20 |
| Final Context | Top 5 |
| Similarity Metric | Cosine Similarity |
| Chunk Overlap | 15–20% |
| Chunk Size | 800–1500 tokens |

---

## 7.4 Hybrid Retrieval Strategy

Version 1 primarily prioritizes dense semantic retrieval.

The architecture is prepared for future hybrid search combining:

- Dense vector search
- Sparse lexical retrieval
- BM25 keyword ranking
- Metadata scoring

---

## 7.5 Re-ranking Layer

The re-ranking layer improves contextual precision.

Candidate models:

- BAAI/bge-reranker-large
- Cohere Rerank
- Jina AI rerankers

The reranker evaluates:

- Semantic relevance
- Engineering terminology alignment
- Contextual coherence
- Query-document compatibility

---

## 7.6 Citation Architecture

Every generated answer should reference:

- Source document
- Section title
- Page number
- Retrieved excerpt

Citation formatting occurs after generation to ensure traceability.

---

# 8. Document Ingestion Architecture

## 8.1 Ingestion Overview

The ingestion pipeline transforms uploaded engineering literature into indexed semantic knowledge.

---

## 8.2 Ingestion Pipeline

```text
PDF Upload
    ↓
File Validation
    ↓
Document Parsing
    ↓
OCR Fallback
    ↓
Structural Analysis
    ↓
Semantic Chunking
    ↓
Metadata Extraction
    ↓
Embedding Generation
    ↓
Qdrant Indexing
```

---

## 8.3 Parsing Strategy

The parser should preserve:

- Chapters
- Sections
- Subsections
- Tables
- Equations
- Captions
- Standards references
- Technical terminology

Flattening the entire document into plain text should be avoided.

---

## 8.4 OCR Strategy

OCR should be triggered when:

- PDF text extraction fails
- Scanned documents are detected
- Image-only pages exist

Possible OCR providers:

- Gemini OCR
- Tesseract
- Azure Document Intelligence

---

## 8.5 Chunking Strategy

The chunking system should prioritize semantic integrity.

### Preferred Strategy

Hybrid chunking:

- Structural chunking
- Semantic chunking
- Context-aware overlap

---

### Important Chunking Rules

Avoid:

- Arbitrary token slicing
- Breaking tables across chunks
- Splitting formulas from explanations

Prefer:

- Concept-complete chunks
- Section-aware segmentation
- Material-property contextual grouping

---

## 8.6 Metadata Enrichment

Each chunk should contain metadata fields.

Example:

```json
{
  "source": "callister_materials_science.pdf",
  "chapter": "Corrosion",
  "section": "Galvanic Corrosion",
  "page": 248,
  "material_type": "Carbon Steel",
  "environment": "Marine"
}
```

---

# 9. Vector Database Architecture

## 9.1 Vector Database Selection

Qdrant was selected due to:

- Strong vector search performance
- Metadata filtering support
- Incremental indexing
- Simple operational model
- Docker compatibility
- Cloud deployment options

---

## 9.2 Vector Storage Strategy

Each chunk stored in Qdrant contains:

- Embedding vector
- Raw chunk text
- Metadata payload
- Source identifiers
- Section references

---

## 9.3 Collection Design

Suggested collection strategy:

| Collection | Purpose |
|---|---|
| engineering_documents | Main production corpus |
| temporary_uploads | Processing validation |
| evaluation_dataset | Retrieval benchmarking |

---

## 9.4 Persistence Strategy

Persistent collections should be enabled.

Backups should include:

- Vector indexes
- Metadata payloads
- Collection schemas

---

# 10. Multimodal Architecture

## 10.1 Multimodal Goals

The platform supports:

- Text input
- Image upload
- Audio upload

---

## 10.2 Image Processing Pipeline

Supported use cases:

- Corrosion inspection
- Material degradation analysis
- Microscopy analysis
- Technical diagrams
- Surface failures

---

### Image Flow

```text
Image Upload
    ↓
Vision Model Processing
    ↓
Textual Interpretation
    ↓
Retrieval Query Expansion
    ↓
RAG Pipeline
```

---

## 10.3 Audio Processing Pipeline

Audio handling flow:

```text
Audio Upload
    ↓
Speech-to-Text
    ↓
Query Normalization
    ↓
RAG Pipeline
```

---

## 10.4 Multimodal Model Strategy

| Capability | Model |
|---|---|
| Vision | GPT-4o |
| Audio Transcription | Whisper or OpenAI Audio |
| Main Reasoning | GPT-4.1 |

---

# 11. API Architecture

## 11.1 API Style

The backend exposes RESTful APIs.

Streaming responses are implemented using:

- Server-Sent Events (SSE)
- Streaming HTTP responses

---

## 11.2 Suggested Endpoint Structure

| Endpoint | Responsibility |
|---|---|
| POST /chat | Main conversation endpoint |
| POST /upload/pdf | PDF ingestion |
| POST /upload/image | Image analysis |
| POST /upload/audio | Audio transcription |
| GET /health | Health check |
| GET /metrics | Observability metrics |

---

## 11.3 API Design Principles

The API should prioritize:

- Statelessness
- Predictable schemas
- Structured errors
- Async support
- Streaming compatibility

---

# 12. Security Architecture

## 12.1 Authentication Strategy

Authentication uses:

- Google OAuth
- Clerk session management
- JWT validation

---

## 12.2 Security Goals

The system should ensure:

- Private document handling
- Secure token storage
- Authenticated access only
- Transport encryption
- Minimal data retention

---

## 12.3 Data Privacy Strategy

Version 1 intentionally avoids:

- Persistent conversation history
- Long-term user profiling
- Behavioral analytics

Uploaded documents should remain isolated and protected.

---

## 12.4 Secret Management

Secrets should be managed through:

- Railway Variables
- Vercel Environment Variables
- Secure CI/CD injection

Secrets must never be hardcoded.

---

# 13. Observability Architecture

## 13.1 Observability Goals

The system must provide visibility into:

- Retrieval behavior
- LLM performance
- Failures
- Latency
- Infrastructure health

---

## 13.2 Logging Strategy

Structured logs should include:

- Request IDs
- User IDs (hashed)
- Retrieval timings
- Embedding timings
- LLM latency
- Error traces

---

## 13.3 Metrics

Suggested metrics:

| Metric | Description |
|---|---|
| Retrieval Latency | Time spent retrieving chunks |
| Embedding Latency | Embedding generation duration |
| LLM Latency | Response generation time |
| Citation Coverage | Percentage of cited responses |
| Retrieval Precision | Evaluation benchmark metric |
| Error Rate | Failed requests percentage |

---

## 13.4 Tracing

Future observability may integrate:

- OpenTelemetry
- LangSmith
- Grafana
- Prometheus

---

# 14. Deployment Architecture

## 14.1 Infrastructure Overview

| Layer | Provider |
|---|---|
| Frontend | Vercel or Railway |
| Backend | Railway |
| Vector Database | Qdrant Cloud or Docker |
| AI Providers | OpenAI APIs |
| Object Storage | Cloud Storage |

---

## 14.2 Container Strategy

Backend services should be containerized using Docker.

Benefits:

- Environment consistency
- Easier deployment
- Infrastructure portability
- Simplified CI/CD

---

## 14.3 CI/CD Strategy

Suggested CI/CD stages:

```text
Code Push
    ↓
Linting
    ↓
Unit Tests
    ↓
Container Build
    ↓
Deployment
    ↓
Smoke Tests
```

---

## 14.4 Environment Strategy

Suggested environments:

| Environment | Purpose |
|---|---|
| Local | Development |
| Staging | Validation |
| Production | Live environment |

---

# 15. Scalability Strategy

## 15.1 Horizontal Scaling

The architecture supports future scaling through:

- Stateless APIs
- Independent retrieval services
- External vector database
- Async ingestion workers
- Containerized deployment

---

## 15.2 Future Architectural Evolution

The platform is intentionally prepared for:

- Multi-agent orchestration
- Specialized engineering agents
- Multi-tenant architecture
- Advanced observability
- Retrieval evaluation pipelines
- Autonomous workflows

---

## 15.3 Potential Future Services

| Future Service | Purpose |
|---|---|
| Evaluation Service | Retrieval benchmarking |
| Memory Service | Persistent conversations |
| Agent Runtime | Multi-agent orchestration |
| Standards Validator | Engineering standards analysis |
| Reporting Engine | Technical report generation |

---

# 16. Risks and Architectural Tradeoffs

## 16.1 Key Risks

| Risk | Mitigation |
|---|---|
| Hallucinations | Strict grounding |
| Poor retrieval quality | Re-ranking pipeline |
| Large PDF complexity | Incremental ingestion |
| OCR inaccuracies | OCR fallback validation |
| Embedding costs | Batch processing |
| Long response latency | Streaming responses |

---

## 16.2 Architectural Tradeoffs

| Decision | Benefit | Tradeoff |
|---|---|---|
| LangChain instead of LangGraph | Simplicity | Less orchestration flexibility |
| Qdrant | Operational simplicity | Less ecosystem maturity than Pinecone |
| No persistent memory | Privacy + simplicity | Reduced continuity |
| Monolithic backend in V1 | Faster delivery | Future service extraction required |

---

# 17. Future Architecture Evolution

## Phase 1 — Core Assistant

- Basic RAG
- PDF ingestion
- Citations
- Semantic retrieval
- Google login

---

## Phase 2 — Retrieval Optimization

- Hybrid search
- Better reranking
- Retrieval analytics
- Evaluation datasets

---

## Phase 3 — Advanced Multimodality

- Diagram interpretation
- Failure analysis
- Comparative engineering analysis

---

## Phase 4 — Engineering Copilot

- Multi-agent orchestration
- Standards validation
- Automated technical reports
- Failure prediction assistance

---

# 18. Conclusion

The Materials Knowledge Assistant architecture was designed to balance:

- Technical rigor
- Operational simplicity
- AI reliability
- Scalability
- Engineering usability

The core architectural differentiator of the platform is not only the use of generative AI, but the combination of:

- Domain-specialized retrieval
- Structured engineering knowledge
- Grounded AI reasoning
- Traceable citations
- Multimodal technical workflows

The architecture intentionally prioritizes strong retrieval quality and grounded responses over unnecessary orchestration complexity.

This foundation enables future evolution toward a fully specialized engineering AI copilot platform.

---

## Source Reference

This document was derived from the Product Requirements Document (PRD) for the Materials Knowledge Assistant. fileciteturn0file0L1-L587

