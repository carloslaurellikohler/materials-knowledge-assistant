# Product Requirements Document (PRD)
# Materials Knowledge Assistant (MKA)

Version: 1.0  
Status: Draft  
Author: Carlos Eduardo  
Date: May 2026

---

# 1. Product Overview

## 1.1 Product Name

Materials Knowledge Assistant (MKA)

---

## 1.2 Product Vision

The Materials Knowledge Assistant (MKA) is a specialized AI-powered assistant designed to support technical analysis workflows in the field of materials engineering for industrial applications, particularly in the context of electrical transformers.

The platform enables engineers to interact naturally with a curated technical knowledge base composed of books, scientific papers, technical reports, standards, and engineering documentation.

Using Retrieval-Augmented Generation (RAG), the assistant retrieves relevant information from indexed technical documents and generates grounded responses with explicit references to source materials.

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

- Provide grounded technical answers based on trusted literature
- Enable natural language interaction with engineering documentation
- Reduce time spent searching technical PDFs
- Improve consistency of technical opinions
- Create a centralized engineering knowledge interface
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

- Google OAuth login

## Chat Interface

- Natural language interaction
- Streaming responses
- Mobile-responsive UI

## Knowledge Base

- PDF ingestion
- Technical document indexing
- Semantic retrieval

## Multimodal Inputs

- Text input
- Image upload
- Audio upload

## Retrieval-Augmented Generation

- Contextual retrieval
- Citation-based responses
- Semantic search
- Metadata filtering
- Re-ranking pipeline

## Citations

- Source attribution
- Chunk references
- Page references when available

---

# 5.2 Out of Scope (V1)

- Persistent conversation memory
- Multi-user collaboration
- Fine-tuning custom models
- Autonomous agents
- Workflow automation
- ERP integrations
- Continuous document synchronization
- Offline mode
- Multi-tenant enterprise support

---

# 6. Functional Requirements

---

# 6.1 Authentication

## FR-001

The platform must support authentication via Google OAuth.

## FR-002

Only authenticated users may access the application.

---

# 6.2 Chat Experience

## FR-003

The platform must provide a conversational interface.

## FR-004

The platform must support streaming AI responses.

## FR-005

The platform must support markdown rendering.

## FR-006

The platform must support citation rendering.

---

# 6.3 File Upload

## FR-007

The platform must allow PDF upload for indexing.

## FR-008

The platform must allow image upload during conversations.

## FR-009

The platform must allow audio upload during conversations.

---

# 6.4 Knowledge Retrieval

## FR-010

The system must retrieve relevant chunks from indexed technical documents.

## FR-011

The retrieval system must use semantic similarity search.

## FR-012

The system must support metadata filtering.

## FR-013

The system must support retrieval re-ranking.

---

# 6.5 AI Response Generation

## FR-014

Responses must be grounded in retrieved documents.

## FR-015

Responses must include citations.

## FR-016

The assistant must avoid hallucinations when insufficient evidence exists.

## FR-017

The assistant must explicitly state uncertainty when confidence is low.

---

# 7. Non-Functional Requirements

---

# 7.1 Performance

## NFR-001

Average response latency should be below 8 seconds.

## NFR-002

Retrieval operations should complete in under 2 seconds.

---

# 7.2 Security

## NFR-003

Uploaded documents must remain private.

## NFR-004

Authentication tokens must be securely managed.

## NFR-005

No conversation persistence should occur in V1.

---

# 7.3 Scalability

## NFR-006

The architecture must support future horizontal scaling.

## NFR-007

The vector database must support incremental indexing.

---

# 7.4 Usability

## NFR-008

The platform must be fully responsive for mobile devices.

## NFR-009

The interface should prioritize simplicity and readability.

---

# 7.5 Observability

## NFR-010

The backend must expose structured logs.

## NFR-011

Errors and retrieval failures must be traceable.

---

# 8. System Architecture

---

# 8.1 Frontend Stack

| Layer | Technology |
|---|---|
| Framework | Next.js |
| Language | TypeScript |
| Styling | TailwindCSS |
| UI Components | shadcn/ui |
| Authentication | Clerk |
| Hosting | Railway or Vercel |

---

# 8.2 Backend Stack

| Layer | Technology |
|---|---|
| API | FastAPI |
| Language | Python |
| AI Orchestration | LangChain |
| Embeddings | OpenAI Embeddings |
| LLM | GPT-4.1 |
| Vision Support | GPT-4o / GPT-4.1-mini |
| OCR | Optional Gemini OCR |

---

# 8.3 Vector Infrastructure

| Component | Technology |
|---|---|
| Vector Database | Qdrant |
| Storage Strategy | Persistent collections |
| Search Type | Semantic + Hybrid |
| Re-ranking | Cross-encoder reranker |

---

# 9. RAG Strategy

This section defines the core intelligence architecture of the platform.

---

# 9.1 Document Ingestion Pipeline

```text
PDF Upload
    ↓
Document Parsing
    ↓
OCR Fallback (if needed)
    ↓
Structural Segmentation
    ↓
Semantic Chunking
    ↓
Metadata Enrichment
    ↓
Embedding Generation
    ↓
Qdrant Indexing
```

---

# 9.2 Parsing Strategy

The ingestion pipeline should identify and preserve:

- Chapters
- Sections
- Subsections
- Tables
- Equations
- Technical diagrams
- Standards references
- Material classifications

The parser should avoid flattening the entire document into plain text whenever possible.

---

# 9.3 Chunking Strategy

## Objective

Preserve semantic integrity of technical engineering knowledge.

---

## Recommended Strategy

Hybrid Chunking:

- Structural chunking
- Semantic chunking
- Controlled overlap

---

## Chunk Characteristics

| Property | Recommendation |
|---|---|
| Chunk Size | 800–1500 tokens |
| Overlap | 15–20% |
| Segmentation | Section-aware |
| Table Handling | Isolated chunks |
| Equations | Preserved inline |

---

## Important Rules

### Avoid:

- Fixed-size naive chunking only
- Breaking tables across chunks
- Splitting definitions from explanations

### Prefer:

- Section-preserving chunks
- Concept-complete chunks
- Material-property contextualization

---

# 9.4 Metadata Strategy

Each indexed chunk should contain metadata.

## Example

```json
{
  "source": "callister_materials_science.pdf",
  "author": "William D. Callister",
  "chapter": "Corrosion",
  "section": "Galvanic Corrosion",
  "material_type": "Carbon Steel",
  "environment": "Marine",
  "temperature_range": "0-50C",
  "document_type": "Book",
  "page": 248
}
```

---

# 9.5 Retrieval Pipeline

```text
User Query
    ↓
Query Embedding
    ↓
Semantic Retrieval
    ↓
Metadata Filtering
    ↓
Hybrid Search
    ↓
Re-ranking
    ↓
Context Assembly
    ↓
LLM Response Generation
```

---

# 9.6 Retrieval Strategy

## Retrieval Method

Hybrid Retrieval:

- Dense semantic retrieval
- Optional sparse keyword search

---

## Retrieval Parameters

| Parameter | Recommendation |
|---|---|
| Initial Retrieval | Top 20 |
| Re-ranked Results | Top 5 |
| Similarity Metric | Cosine Similarity |

---

# 9.7 Re-ranking Strategy

## Objective

Improve contextual precision before prompt assembly.

---

## Recommended Approach

Cross-encoder re-ranking.

Examples:

- BAAI/bge-reranker-large
- Cohere Rerank
- Jina AI rerankers

---

# 9.8 Citation Strategy

Every response must include:

- Source document
- Section reference
- Page number (when available)
- Retrieved excerpt

---

## Example Response Format

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

---

# 10.2 Anti-Hallucination Policy

If insufficient evidence exists:

The assistant should respond:

```text
The indexed technical literature does not provide sufficient evidence to confidently answer this question.
```

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

The assistant should support:

- Corrosion images
- Microscopy
- Material failures
- Surface degradation
- Technical diagrams

---

# 11.2 Audio Support

Audio uploads should be:

- Transcribed
- Converted into textual queries
- Processed through the same retrieval pipeline

---

# 12. API Architecture

---

# 12.1 Suggested Services

| Service | Responsibility |
|---|---|
| Auth Service | Authentication |
| Chat Service | Conversation orchestration |
| Retrieval Service | Qdrant interaction |
| Ingestion Service | PDF processing |
| Embedding Service | Embedding generation |
| Citation Service | Source formatting |

---

# 13. Deployment Strategy

---

# 13.1 Infrastructure

| Layer | Provider |
|---|---|
| Frontend | Vercel or Railway |
| Backend | Railway |
| Vector DB | Qdrant Cloud or Docker |
| Secrets | Railway Variables |

---

# 13.2 Deployment Goals

- Fast iteration
- Low operational complexity
- Simple CI/CD
- Container-ready architecture

---

# 14. Future Roadmap

---

# Phase 1 — Core RAG Assistant

- PDF ingestion
- Chat interface
- Semantic retrieval
- Citations
- Google login

---

# Phase 2 — Advanced Retrieval

- Hybrid search
- Better reranking
- Metadata filtering UI
- Retrieval observability

---

# Phase 3 — Multimodal Intelligence

- Advanced image analysis
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
| Poor chunking quality | Structural-semantic chunking |
| Hallucinations | Strict grounding prompts |
| Low retrieval precision | Re-ranking pipeline |
| OCR failures | OCR fallback strategy |
| Large PDFs | Incremental ingestion |

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