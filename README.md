# Materials Knowledge Assistant (MKA)

> Assistente RAG especializado em literatura técnica de engenharia de materiais — respostas fundamentadas, rastreáveis e citadas, sem alucinações.

O MKA é uma plataforma de raciocínio técnico baseada em Retrieval-Augmented Generation (RAG) construída para engenheiros de materiais do setor de transformadores elétricos. Elimina a necessidade de buscas manuais em PDFs técnicos extensos, fornecendo respostas precisas com citação de fonte, seção e página extraídas de literatura indexada de engenharia.

**Princípio fundamental:** omissão é preferível a especulação. Se a literatura indexada não contém evidência suficiente para responder, o sistema informa isso em vez de fabricar uma resposta.

---

## Arquitetura

```
Usuário
  │
  ▼
Frontend  (Next.js 14 · :3000)
  │  HTTP + SSE
  ▼
Backend   (FastAPI · :8000)
  ├─── OpenAI API  (embed · GPT-4.1 · GPT-4o · Whisper)
  ├─── Cohere API  (re-ranking)
  └─── Qdrant      (:6333)  ◄── vector store (65 k+ chunks)
         │
  Worker (Celery)  ◄── Redis (:6379)  ◄── ingestão em background
```

### Pipeline de inferência

```
query
  │
  ▼
embed_texts()          text-embedding-3-small · 1536-dim
  │
  ▼
Qdrant search          top-20 por similaridade cosseno
  │
  ▼
Cohere rerank          top-20 → top-5  (rerank-english-v3.0)
  │
  ▼
[context vazio?] ──Yes──► retorna mensagem de fallback (sem LLM)
  │ No
  ▼
stream_answer()        GPT-4.1 · streaming SSE
  │
  ▼
event: token × N  →  event: citations  →  event: done
```

---

## Stack

| Camada | Tecnologia |
|---|---|
| Frontend | Next.js 14, TypeScript, TailwindCSS, shadcn/ui |
| Autenticação | Clerk (RS256/JWKS em produção, HS256 em dev) |
| Backend | FastAPI, Python 3.12+, Uvicorn |
| Embeddings | OpenAI `text-embedding-3-small` (1536-dim) |
| LLM (chat) | OpenAI `gpt-4.1` |
| LLM (visão) | OpenAI `gpt-4o` |
| Transcrição | OpenAI `whisper-1` |
| Re-ranking | Cohere `rerank-english-v3.0` |
| Vector DB | Qdrant v1.11.3 |
| Task queue | Celery + Redis 7 |
| PDF parsing | pypdf + PyMuPDF (OCR fallback) |
| Containerização | Docker + Docker Compose |

---

## Pré-requisitos

- Docker e Docker Compose
- **Chave de API OpenAI** — obrigatória (`OPENAI_API_KEY`)
- Chave de API Cohere — opcional (re-ranking desativado sem ela)
- Clerk — opcional (HS256 dev fallback disponível sem configuração Clerk)

---

## Início rápido

### 1. Configurar variáveis de ambiente

```bash
cp .env.example .env
```

Editar `.env` na raiz do projeto:

```env
OPENAI_API_KEY=sk-...

# Opcional — re-ranking Cohere
COHERE_API_KEY=

# Opcional — autenticação Clerk (produção)
# Clerk Dashboard → Configure → API Keys → "JWKS URL"
CLERK_JWKS_URL=

# Usado em dev/test sem CLERK_JWKS_URL
CLERK_JWT_SECRET=dev-secret
```

### 2. Subir o stack

**Desenvolvimento** (hot reload em backend e frontend):

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build
```

**Produção**:

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up --build -d
```

| Serviço | URL |
|---|---|
| Frontend | http://localhost:3000 |
| Backend API | http://localhost:8000 |
| Qdrant | http://localhost:6333 |
| Redis | localhost:6379 |

### 3. Indexar o corpus

O Qdrant começa vazio. Coloque os PDFs em `backend/livros/` e execute:

```bash
cd backend
uv sync
uv run python reindex_corpus.py --recreate
```

Veja a seção [Gestão do corpus](#gestão-do-corpus) para opções avançadas.

---

## API Reference

Base URL: `http://localhost:8000/api/v1`

| Método | Endpoint | Auth | Descrição |
|---|---|---|---|
| `GET` | `/health` | Não | Health check |
| `POST` | `/chat` | Sim | Chat com streaming SSE |
| `GET` | `/documents` | Sim | Lista documentos indexados |
| `POST` | `/upload/pdf` | Sim | Upload PDF → ingestão via worker |
| `POST` | `/upload/image` | Sim | Análise de imagem via GPT-4o |
| `POST` | `/upload/audio` | Sim | Transcrição via Whisper |
| `GET` | `/metrics` | Não | Métricas de latência e citações |

### POST /chat

**Corpo:**

```json
{
  "message": "Quais são os mecanismos de corrosão do aço carbono?",
  "metadata_filters": {
    "material_type": "steel"
  }
}
```

**Eventos SSE retornados:**

```
event: token
data: A corrosão uniforme ocorre...

event: token
data:  em toda a superfície exposta...

event: citations
data: [
  {
    "source": "Callister 9ª Ed.pdf",
    "chapter": "CORROSION AND DEGRADATION",
    "section": "17.8 Corrosion of Metals",
    "page": 735,
    "excerpt": "É conveniente classificar a corrosão de acordo com..."
  }
]

event: done
data: ok
```

**Guarda de contexto vazio:** se o retrieval não encontrar nenhum chunk relevante, o SSE retorna a mensagem de fallback padrão sem acionar o LLM.

### POST /upload/image

Aceita PNG, JPG, WEBP (máx. 20 MB). GPT-4o analisa a imagem e retorna uma descrição técnica para uso como query no `/chat`.

```json
{ "status": "analyzed", "description": "Corrosão generalizada na superfície..." }
```

### POST /upload/audio

Aceita MP3, WAV, M4A (máx. 25 MB). Whisper transcreve e retorna texto para uso como query no `/chat`.

```json
{ "status": "transcribed", "transcript": "Quais são as propriedades do cobre..." }
```

---

## Autenticação

| Ambiente | Mecanismo | Configuração |
|---|---|---|
| Produção | Clerk RS256/JWKS | `CLERK_JWKS_URL=https://.../.well-known/jwks.json` |
| Dev/test | HS256 | `CLERK_JWT_SECRET=dev-secret` |

**Gerar token de dev para testes curl:**

```bash
python3 -c "import jwt; print(jwt.encode({'sub': 'dev'}, 'dev-secret', algorithm='HS256'))"
```

```bash
TOKEN="eyJ..."
curl -N -X POST http://localhost:8000/api/v1/chat \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"message": "Quais as propriedades mecânicas do aço AISI 1020?"}'
```

---

## Gestão do corpus

O corpus é **fechado** — novos embeddings são gerados por operação administrativa, não por upload de usuários. PDFs devem ser colocados em `backend/livros/`.

Os documentos são indexados com:
- **Chunking estrutural** — detecta headings numerados (`3.2 Corrosion`) e ALL CAPS antes de dividir por palavras (tamanho padrão: 1.200 palavras, overlap: 200)
- **Metadados enriquecidos** — `chapter`, `section`, `material_type`, `author`, `title`, `document_type` extraídos heuristicamente de cada página
- **Detecção de duplicatas por SHA-256** — PDFs já indexados são pulados automaticamente

### Comandos

```bash
cd backend && uv sync

# Primeira indexação (ou após mudanças de chunking — recria a coleção)
uv run python reindex_corpus.py --recreate

# Adicionar novos PDFs sem apagar os já indexados
uv run python reindex_corpus.py

# Processar apenas 1 PDF (validação rápida)
uv run python reindex_corpus.py --recreate --limit 1

# Retomar de checkpoint após interrupção
uv run python reindex_corpus.py --resume --checkpoint-file .reindex/checkpoint.json

# Silencioso (sem logs de progresso)
uv run python reindex_corpus.py --quiet
```

### OCR para PDFs escaneados (opt-in)

Por padrão, páginas com menos de 50 caracteres de texto nativo são descartadas. Para ativar OCR via GPT-4o, defina no `.env` do backend:

```env
OCR_BACKEND=vision   # usa GPT-4o para páginas esparsas
OCR_MIN_CHARS=50     # limiar de caracteres para acionar OCR
```

> **Atenção:** OCR via GPT-4o tem custo por página processada. Ative apenas para documentos escaneados.

---

## Configuração completa

Todas as variáveis são lidas de `.env` (raiz) ou variáveis de ambiente. Valores padrão são aplicados quando a variável está ausente.

| Variável | Padrão | Descrição |
|---|---|---|
| `OPENAI_API_KEY` | — | **Obrigatória** em produção |
| `OPENAI_EMBEDDING_MODEL` | `text-embedding-3-small` | Modelo de embedding |
| `OPENAI_CHAT_MODEL` | `gpt-4.1` | Modelo de chat |
| `OPENAI_VISION_MODEL` | `gpt-4o` | Modelo de análise de imagem |
| `OPENAI_WHISPER_MODEL` | `whisper-1` | Modelo de transcrição de áudio |
| `COHERE_API_KEY` | — | Opcional; re-ranking desativado sem ela |
| `RERANKER_MODEL` | `rerank-english-v3.0` | Modelo de re-ranking Cohere |
| `CLERK_JWKS_URL` | — | Opcional; ativa validação RS256 |
| `CLERK_JWT_SECRET` | `dev-secret` | Fallback HS256 (somente dev/test) |
| `QDRANT_URL` | `http://localhost:6333` | URL do Qdrant |
| `QDRANT_COLLECTION` | `engineering_documents` | Nome da coleção vetorial |
| `REDIS_URL` | `redis://localhost:6379/0` | URL do Redis |
| `RETRIEVAL_TOP_K_CANDIDATES` | `20` | Candidatos retornados pelo Qdrant |
| `RETRIEVAL_TOP_K_FINAL` | `5` | Chunks enviados ao LLM após re-ranking |
| `MAX_UPLOAD_MB` | `100` | Tamanho máximo de PDF por upload |
| `MAX_IMAGE_UPLOAD_MB` | `20` | Tamanho máximo de imagem |
| `MAX_AUDIO_UPLOAD_MB` | `25` | Tamanho máximo de áudio |
| `OCR_BACKEND` | `none` | `none` ou `vision` |
| `OCR_MIN_CHARS` | `50` | Chars mínimos para acionar OCR |
| `APP_ENV` | `dev` | `dev`, `test` ou `prod` |

---

## Desenvolvimento local (sem Docker)

Qdrant e Redis devem estar rodando (podem ser iniciados isoladamente via Docker):

```bash
docker compose up qdrant redis -d
```

```bash
cd backend
uv sync

# Rodar testes (não requer API keys)
APP_ENV=test uv run pytest tests/ -v

# Rodar servidor localmente
uv run uvicorn app.main:app --reload --port 8000
```

O backend lê `.env` automaticamente via `pydantic-settings`.

---

## Estrutura do projeto

```
materials-knowledge-assistant/
│
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   ├── deps.py              # autenticação JWT, dependências Qdrant
│   │   │   ├── routes/
│   │   │   │   ├── chat.py          # POST /chat (streaming SSE)
│   │   │   │   ├── documents.py     # GET /documents
│   │   │   │   ├── health.py        # GET /health
│   │   │   │   ├── metrics.py       # GET /metrics
│   │   │   │   ├── multimodal.py    # POST /upload/image|audio
│   │   │   │   └── upload.py        # POST /upload/pdf
│   │   │   └── schemas/             # modelos Pydantic de request/response
│   │   ├── core/
│   │   │   ├── config.py            # Settings (pydantic-settings)
│   │   │   ├── logging.py           # configuração de logs estruturados
│   │   │   └── metrics_store.py     # ring buffer p50/p95 latência + citações
│   │   ├── integrations/
│   │   │   └── openai_client.py     # embed_texts, stream_answer, describe_image, transcribe_audio
│   │   ├── rag/
│   │   │   └── prompts.py           # SYSTEM_PROMPT (grounding), VISION_PROMPT
│   │   ├── services/
│   │   │   ├── chat.py              # orquestração: embed → retrieve → rerank → stream
│   │   │   ├── ingestion.py         # chunking estrutural, metadata, OCR, SHA256
│   │   │   ├── reranking.py         # CohereReranker
│   │   │   └── retrieval.py         # query Qdrant com filtros de metadados
│   │   ├── workers/
│   │   │   ├── celery_app.py        # configuração Celery
│   │   │   └── tasks.py             # reindex_books_task, ingest_single_pdf_task
│   │   └── main.py                  # FastAPI app, lifespan, middleware, routers
│   ├── tests/                       # 54 testes (pytest-asyncio, sem API keys)
│   ├── reindex_corpus.py            # CLI de indexação do corpus
│   ├── livros/                      # PDFs do corpus (gitignored)
│   ├── Dockerfile
│   └── pyproject.toml
│
├── frontend/
│   ├── app/                         # Next.js App Router
│   │   ├── chat/page.tsx            # interface principal
│   │   └── layout.tsx
│   ├── components/
│   │   ├── chat/                    # ChatWindow, ChatComposer
│   │   ├── citations/               # CitationList
│   │   ├── upload/                  # UploadPanel
│   │   └── ui/                      # Button, Card, Badge, Textarea
│   ├── hooks/
│   │   └── use-chat-session.ts      # estado de sessão (React Context + Hooks)
│   ├── services/
│   │   ├── api.ts                   # chamadas REST
│   │   └── sse.ts                   # consumo de Server-Sent Events
│   ├── types/chat.ts
│   ├── middleware.ts                 # Clerk auth middleware
│   └── Dockerfile
│
├── .rules/                          # especificações do produto (fonte da verdade)
│   ├── Product-Requirements-Document-(PRD).md
│   ├── system_architecture_document_mka_v_1.md
│   ├── RAG_Architecture_Specification_MKA.md
│   ├── Backend_Spec_MKA.md
│   └── Frontend_Spec_MKA.md
│
├── docker-compose.yml               # base (serviços e volumes)
├── docker-compose.dev.yml           # override dev (hot reload, bind mounts)
├── docker-compose.prod.yml          # override prod
└── .env.example                     # template de variáveis de ambiente
```

---

## Fora do escopo (V1)

As funcionalidades abaixo foram deliberadamente excluídas do V1 por razões de simplicidade, privacidade ou priorização:

- Memória persistente de conversação
- Colaboração multi-usuário
- Fine-tuning de modelos
- Agentes autônomos / orquestração multi-agente
- Integração com ERP ou sistemas externos
- Sincronização contínua de documentos
- Modo offline
- Análise comportamental e analytics de uso

---

## SLAs de desempenho (alvos de design)

| Métrica | Alvo |
|---|---|
| Latência total (retrieval + LLM) | < 8 segundos |
| Latência de retrieval | < 2 segundos |
| Cobertura de citações | 100% |
| Taxa de alucinação | < 5% |
| Precisão de retrieval | > 85% |
