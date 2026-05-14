# RAG Architecture Specification (RAS)
## Materials Knowledge Assistant (MKA)

Version: 1.0  
Status: Draft  
Author: Carlos Eduardo  
Date: May 2026

---

# 1. Introduction

## 1.1 Purpose

This document defines the Retrieval-Augmented Generation (RAG) architecture specification for the Materials Knowledge Assistant (MKA).

The purpose of this specification is to provide a detailed technical definition of:

- Retrieval architecture
- Document ingestion workflows
- Semantic indexing strategy
- Chunking methodology
- Metadata enrichment
- Retrieval orchestration
- Re-ranking mechanisms
- Context assembly
- Citation generation
- Hallucination mitigation
- Evaluation strategy
- Performance optimization

This document operationalizes the RAG-related requirements defined in the PRD and expands the architectural decisions described in the SAD.

---

# 1.2 Scope

This specification covers:

- PDF ingestion architecture
- Semantic retrieval pipeline
- Embedding strategy
- Vector indexing
- Metadata modeling
- Hybrid retrieval
- Retrieval ranking
- Prompt context construction
- Citation architecture
- Retrieval observability
- Evaluation and benchmarking

This specification does not cover:

- Frontend implementation details
- Generic API specifications
- Infrastructure provisioning
- Fine-tuning pipelines
- Multi-agent orchestration
- Persistent conversational memory

---

# 1.3 Architectural Objectives

The RAG architecture is designed to achieve the following goals:

| Objective | Description |
|---|---|
| Grounded Responses | Ensure answers are based on indexed literature |
| High Retrieval Precision | Improve relevance of retrieved engineering content |
| Traceability | Preserve citations and provenance |
| Low Hallucination Rate | Reduce unsupported generation |
| Engineering Context Preservation | Maintain semantic integrity of technical content |
| Scalability | Support future corpus growth |
| Extensibility | Enable future retrieval enhancements |

---

# 2. RAG System Overview

## 2.1 High-Level Architecture

```text
                    ┌─────────────────────┐
                    │     User Query      │
                    └──────────┬──────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │ Query Preprocessing │
                    └──────────┬──────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │ Embedding Generator │
                    └──────────┬──────────┘
                               │
                               ▼
                 ┌────────────────────────────┐
                 │ Retrieval Orchestration    │
                 └───────┬─────────┬──────────┘
                         │         │
                         ▼         ▼
              ┌──────────────┐  ┌──────────────┐
              │ Dense Search │  │ Sparse Search│
              └──────┬───────┘  └──────┬───────┘
                     │                 │
                     └────────┬────────┘
                              ▼
                  ┌─────────────────────┐
                  │ Candidate Aggregator│
                  └──────────┬──────────┘
                             ▼
                  ┌─────────────────────┐
                  │ Cross-Encoder Ranker│
                  └──────────┬──────────┘
                             ▼
                  ┌─────────────────────┐
                  │ Context Constructor │
                  └──────────┬──────────┘
                             ▼
                  ┌─────────────────────┐
                  │ LLM Response Engine │
                  └──────────┬──────────┘
                             ▼
                  ┌─────────────────────┐
                  │ Citation Formatter  │
                  └─────────────────────┘
```

---

# 3. Document Ingestion Architecture

## 3.1 Ingestion Pipeline

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
Semantic Segmentation
    ↓
Chunk Generation
    ↓
Metadata Enrichment
    ↓
Embedding Generation
    ↓
Qdrant Indexing
```

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

| Parameter | Recommendation |
|---|---|
| Chunk Size | 800–1500 tokens |
| Chunk Overlap | 15–20% |
| Retrieval Candidates | Top 20 |
| Final Context Chunks | Top 5 |

---

# 5. Metadata Architecture

## 5.1 Required Metadata Fields

| Field | Description |
|---|---|
| source | Original document |
| title | Document title |
| author | Author |
| chapter | Chapter name |
| section | Section name |
| subsection | Subsection name |
| page | Page number |
| document_type | Book, paper, standard |
| ingestion_timestamp | Processing timestamp |
| chunk_id | Unique chunk identifier |

---

# 6. Embedding Architecture

## 6.1 Embedding Model Strategy

| Capability | Model |
|---|---|
| Primary Embeddings | OpenAI Embeddings |
| Future Specialized Models | Domain-specific embeddings |
| Lightweight Operations | Smaller embedding models |

---

# 7. Vector Database Architecture

## 7.1 Vector Database Selection

The system uses Qdrant as the primary vector database.

Selection rationale:

- High retrieval performance
- Native metadata filtering
- Incremental indexing support
- Operational simplicity
- Docker compatibility
- Cloud deployment flexibility

---

# 8. Retrieval Architecture

## 8.1 Retrieval Pipeline

```text
User Query
    ↓
Query Normalization
    ↓
Query Embedding
    ↓
Dense Semantic Search
    ↓
Metadata Filtering
    ↓
Optional Sparse Retrieval
    ↓
Candidate Aggregation
    ↓
Cross-Encoder Re-ranking
    ↓
Top-K Selection
    ↓
Context Compression
    ↓
Prompt Assembly
```

---

# 9. Re-ranking Architecture

## 9.1 Recommended Re-rankers

| Model | Type |
|---|---|
| BAAI/bge-reranker-large | Cross-encoder |
| Cohere Rerank | API-based |
| Jina Reranker | Cross-encoder |

---

# 10. Context Assembly Architecture

## 10.1 Context Assembly Goals

The context builder must:

- Maximize relevance
- Reduce redundancy
- Preserve citations
- Respect token budgets
- Preserve engineering reasoning chains

---

# 11. Prompt Grounding Specification

## 11.1 Grounding Rules

The assistant must:

- Only answer using retrieved evidence
- Explicitly state uncertainty
- Avoid unsupported assumptions
- Prefer omission over speculation

---

# 12. Citation Architecture

## 12.1 Citation Objectives

The citation layer provides:

- Traceability
- Engineering confidence
- Auditability
- Literature verification

---

# 13. Multimodal Retrieval Architecture

## 13.1 Image Retrieval Flow

```text
Image Upload
    ↓
Vision Interpretation
    ↓
Engineering Description
    ↓
Query Expansion
    ↓
RAG Retrieval Pipeline
```

---

# 14. Observability and Evaluation

## 14.1 Retrieval Metrics

| Metric | Description |
|---|---|
| Recall@K | Retrieval completeness |
| Precision@K | Retrieval precision |
| MRR | Mean Reciprocal Rank |
| Citation Coverage | Responses with citations |
| Hallucination Rate | Unsupported claims |
| Retrieval Latency | Retrieval duration |

---

# 15. Performance and Scalability

## 15.1 Performance Targets

| Metric | Target |
|---|---|
| Retrieval Latency | < 2 seconds |
| Average Response Time | < 8 seconds |
| Citation Coverage | 100% |
| Hallucination Rate | < 5% |

---

# 16. Risks and Mitigations

| Risk | Mitigation |
|---|---|
| Poor chunking quality | Structural-semantic chunking |
| Low retrieval precision | Re-ranking pipeline |
| Hallucinations | Strict grounding |
| OCR inaccuracies | OCR fallback validation |
| Large PDF processing | Incremental ingestion |
| Embedding cost growth | Batch processing |
| Token overflows | Context compression |

---

# 17. Conclusion

The RAG architecture of the Materials Knowledge Assistant was designed to prioritize:

- Retrieval quality
- Engineering traceability
- Semantic integrity
- Grounded AI reasoning
- Low operational complexity

The architecture intentionally emphasizes high-confidence technical retrieval and citation-backed generation to support engineering workflows where precision and trustworthiness are essential.
