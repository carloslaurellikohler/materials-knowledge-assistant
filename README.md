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
  │  HTTP + SSE   (proxy interno /api/v1/[...path] → backend)
  ▼
Backend   (FastAPI · :8000)
  ├─── PostgreSQL   (:5432)        metadados de documentos · status de indexação
  ├─── Supabase Storage             bucket mka-documents/{user_id}/{document_id}/...
  ├─── OpenAI API                   embeddings · chat · vision (GPT-4o) · Whisper
  ├─── Cohere API                   re-ranking (opcional)
  └─── Qdrant       (:6333)         vetores · payload inclui user_id + document_id
         ▲
  Worker (Celery)  ◄── Redis (:6379)  ingestão assíncrona por documento
```

### Pipeline de inferência

```
query (autenticada via JWT Clerk → user_id)
  │
  ▼
embed_texts()          text-embedding-3-small · 1536-dim
  │
  ▼
Qdrant search          filtro must={user_id} + metadata_filters · top-K candidatos
  │
  ▼
Cohere rerank          top-K → top-N  (opcional · rerank-english-v3.0)
  │
  ▼
[context vazio?] ──Yes──► retorna mensagem de fallback (sem LLM)
  │ No
  ▼
stream_answer()        modelo de chat · streaming SSE
  │
  ▼
event: token × N  →  event: citations  →  event: done
```

### Pipeline de ingestão (upload por usuário)

```
HTTP (síncrono)                        Worker Celery (assíncrono)
─────────────────────────────────       ─────────────────────────────────
POST /api/v1/documents (multipart)     mka.ingest_document(document_id)
  │                                     │
  ├─ valida MIME + tamanho               ├─ status → "processing"
  ├─ sanitiza nome                       ├─ baixa PDF do Supabase Storage
  ├─ upload para Supabase Storage        ├─ extrai páginas (pypdf, OCR opt-in)
  ├─ insere row em documents (pending)   ├─ chunking estrutural          → "chunking"
  ├─ dispara mka.ingest_document         ├─ embed_texts() em lote        → "embedding"
  └─ retorna 202 Accepted +              ├─ upsert no Qdrant (user_id,
     {document_id, indexing_status}      │   document_id no payload)
                                         └─ status → "indexed" | "error"
```

---

## Stack

| Camada | Tecnologia |
|---|---|
| Frontend | Next.js 14 (App Router), TypeScript, TailwindCSS, shadcn/ui |
| Autenticação | Clerk (RS256/JWKS em produção, HS256 em dev; opcional via `NEXT_PUBLIC_ENABLE_CLERK`) |
| Backend | FastAPI, Python 3.12+, Uvicorn |
| Embeddings | OpenAI `text-embedding-3-small` (1536-dim) |
| LLM (chat) | OpenAI — ver nota em [Configuração completa](#configuração-completa) |
| LLM (visão) | OpenAI `gpt-4o` |
| Transcrição | OpenAI `whisper-1` |
| Re-ranking | Cohere `rerank-english-v3.0` (opcional) |
| Vector DB | Qdrant v1.11.3 (payload com `user_id` + `document_id`) |
| Banco relacional | PostgreSQL 16 + SQLAlchemy 2.0 (async via `asyncpg`, sync via `psycopg2` para Celery) |
| Object Storage | Supabase Storage (`supabase-py`) — bucket `mka-documents` |
| Migrations | Alembic (instalado; schema atualmente criado em runtime via `Base.metadata.create_all` no lifespan — `backend/app/main.py:23`) |
| Task queue | Celery + Redis 7 |
| PDF parsing | pypdf + PyMuPDF (OCR opt-in via GPT-4o) |
| Containerização | Docker + Docker Compose (6 serviços: qdrant, redis, postgres, backend, worker, frontend) |

> O frontend pode rodar sem Clerk em dev: defina `NEXT_PUBLIC_ENABLE_CLERK=false` e o `middleware.ts` opera como no-op (rotas ficam abertas). Em produção, ative Clerk e configure JWKS no backend.

---

## Pré-requisitos

- Docker e Docker Compose
- **Chave de API OpenAI** — obrigatória (`OPENAI_API_KEY`)
- **Projeto Supabase** com o bucket `mka-documents` criado, e a chave **`service_role`** (não a anon) em mãos — necessária para upload por usuário. Sem ela, o backend retorna 403 (RLS bloqueia)
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
# --- OpenAI (obrigatório) ---
OPENAI_API_KEY=sk-...

# --- Cohere (opcional) ---
COHERE_API_KEY=

# --- Clerk (opcional; HS256 fallback em dev) ---
# Clerk Dashboard → Configure → API Keys → "JWKS URL"
CLERK_JWKS_URL=
CLERK_JWT_SECRET=dev-secret

# --- PostgreSQL ---
# Usado por backend e worker; DATABASE_URL é montado no docker-compose
POSTGRES_PASSWORD=mka-dev-password

# --- Supabase Storage (obrigatório para upload de usuário) ---
SUPABASE_URL=https://xxxxxxxxxxxxxxxxxxxx.supabase.co
SUPABASE_KEY=eyJhbGci...service_role...
SUPABASE_BUCKET=mka-documents

# --- Frontend (Clerk) ---
NEXT_PUBLIC_ENABLE_CLERK=false
NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=
CLERK_SECRET_KEY=
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
| PostgreSQL | localhost:5432 |
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
| `GET` | `/metrics` | Não | Métricas p50/p95 de latência e cobertura de citações |
| `POST` | `/chat` | Sim | Chat com streaming SSE (filtrado por `user_id`) |
| `POST` | `/documents` | Sim | Upload de PDF; retorna 202 e dispara ingestão Celery |
| `GET` | `/documents` | Sim | Lista documentos do usuário autenticado |
| `GET` | `/documents/{id}` | Sim | Status detalhado de um documento (polling de indexação) |
| `DELETE` | `/documents/{id}` | Sim | Remove documento (Qdrant + Supabase + Postgres) |
| `POST` | `/upload/image` | Sim | Análise de imagem via GPT-4o |
| `POST` | `/upload/audio` | Sim | Transcrição via Whisper |

O frontend (Next.js) expõe `/api/v1/[...path]/route.ts` como **proxy transparente** para o backend, permitindo que o navegador chame o mesmo origin do frontend.

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

### POST /documents

Upload assíncrono de PDF para a knowledge base do usuário autenticado.

- Campo `multipart/form-data`: `file` (PDF, até `MAX_UPLOAD_MB`, default 100 MB).
- O backend valida MIME, sanitiza o nome, sobe o arquivo para `mka-documents/{user_id}/{document_id}/{filename}`, cria uma row em `documents` com `indexing_status="pending"` e dispara o task Celery `mka.ingest_document(document_id)`.
- Retorna HTTP **202 Accepted** imediatamente:

```json
{
  "document_id": "9a1b8c7d-...-...",
  "indexing_status": "pending"
}
```

A indexação ocorre em background — o frontend deve fazer **polling** em `GET /documents/{id}` para acompanhar a progressão de status.

### GET /documents/{id}

Retorna o estado atual de um documento (somente do próprio usuário). Estados possíveis para `indexing_status`:

| Estado | Significado |
|---|---|
| `pending` | Enfileirado para o worker |
| `processing` | Worker baixou o arquivo do Supabase |
| `chunking` | Texto extraído e dividido em chunks |
| `embedding` | Chunks sendo embedados em lote |
| `indexed` | Vetores inseridos no Qdrant — pronto para retrieval |
| `error` | Falha; ver `indexing_error` |

O frontend faz polling a cada 3s até `indexed` ou `error` (`frontend/hooks/use-chat-session.ts`).

### DELETE /documents/{id}

Remove os vetores correspondentes do Qdrant (filtrando por `document_id`), deleta o arquivo do Supabase e apaga a row em `documents`. Retorna **204 No Content**.

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

## Modelo de dados

A tabela `documents` (Postgres) é a fonte de verdade para o ciclo de vida de cada PDF de usuário. Definida em `backend/app/db/models.py`.

| Coluna | Tipo | Notas |
|---|---|---|
| `id` | UUID (string) | PK (gerada pelo backend) |
| `user_id` | string | Indexado; extraído do JWT Clerk |
| `filename` | string | Nome sanitizado armazenado no Supabase |
| `original_filename` | string | Nome original enviado pelo usuário |
| `storage_path` | string | `{user_id}/{document_id}/{filename}` |
| `mime_type` | string | Sempre `application/pdf` |
| `size` | integer | Bytes |
| `indexing_status` | enum | `pending`, `processing`, `chunking`, `embedding`, `indexed`, `error` |
| `indexing_error` | text · nullable | Mensagem em caso de falha |
| `chunk_count` | integer · nullable | Preenchido após indexação bem-sucedida |
| `embedding_model` | string · nullable | Ex.: `text-embedding-3-small` |
| `qdrant_collection` | string | Coleção alvo (default `engineering_documents`) |
| `created_at` / `updated_at` | timestamp (tz) | Mantidos automaticamente |

O schema é criado em runtime via `Base.metadata.create_all` no lifespan do FastAPI (`backend/app/main.py:23`). Alembic está instalado e disponível, mas não há migrations versionadas no momento.

**Payload dos chunks no Qdrant** (gerado por `backend/app/services/ingestion.py`):

```
source, source_id (SHA-256 do PDF), user_id, document_id,
page, chunk_id, text, document_type, ingestion_timestamp,
author, title, chapter, section, material_type
```

O retrieval (`backend/app/services/retrieval.py`) sempre adiciona um filtro `must={user_id=...}` antes da busca vetorial.

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

## Gestão do corpus (modo administrativo)

> **Importante:** o fluxo principal hoje é **upload por usuário** via `POST /api/v1/documents`, com isolamento por `user_id`. O modo administrativo abaixo é usado para pré-carregar um corpus base no Qdrant.
>
> Vetores ingeridos por este caminho **não recebem `user_id`** e portanto **não aparecem** na busca filtrada por usuário. Use-os apenas quando o objetivo for um corpus compartilhado ou bootstrap de ambiente.

PDFs administrativos devem ser colocados em `backend/livros/`. Os documentos são indexados com:
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
| `OPENAI_CHAT_MODEL` | `gpt-5.4` ⚠️ | Modelo de chat — ver nota abaixo |
| `OPENAI_VISION_MODEL` | `gpt-4o` | Modelo de análise de imagem |
| `OPENAI_WHISPER_MODEL` | `whisper-1` | Modelo de transcrição de áudio |
| `COHERE_API_KEY` | — | Opcional; re-ranking desativado sem ela |
| `RERANKER_MODEL` | `rerank-english-v3.0` | Modelo de re-ranking Cohere |
| `CLERK_JWKS_URL` | — | Opcional; ativa validação RS256 |
| `CLERK_JWT_SECRET` | `dev-secret` | Fallback HS256 (somente dev/test) |
| `QDRANT_URL` | `http://localhost:6333` | URL do Qdrant |
| `QDRANT_COLLECTION` | `engineering_documents` | Nome da coleção vetorial |
| `QDRANT_VECTOR_SIZE` | `1536` | Dimensão dos vetores (alinhada ao embedding) |
| `REDIS_URL` | `redis://localhost:6379/0` | URL do Redis (broker Celery) |
| `DATABASE_URL` | `postgresql+asyncpg://mka:mka@localhost:5432/mka` | URL do Postgres (driver async) |
| `SUPABASE_URL` | — | **Obrigatória** — URL do projeto Supabase |
| `SUPABASE_KEY` | — | **Obrigatória** — chave `service_role` (não a anon) |
| `SUPABASE_BUCKET` | `mka-documents` | Bucket alvo do storage |
| `RETRIEVAL_TOP_K_CANDIDATES` | `20` | Candidatos retornados pelo Qdrant |
| `RETRIEVAL_TOP_K_FINAL` | `5` | Chunks enviados ao LLM após re-ranking |
| `MAX_UPLOAD_MB` | `100` | Tamanho máximo de PDF por upload |
| `MAX_IMAGE_UPLOAD_MB` | `20` | Tamanho máximo de imagem |
| `MAX_AUDIO_UPLOAD_MB` | `25` | Tamanho máximo de áudio |
| `OCR_BACKEND` | `none` | `none` ou `vision` |
| `OCR_MIN_CHARS` | `50` | Chars mínimos para acionar OCR |
| `APP_ENV` | `dev` | `dev`, `test` ou `prod` |
| `NEXT_PUBLIC_ENABLE_CLERK` | `false` | (frontend) `true` ativa o middleware Clerk |
| `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` | — | (frontend) chave pública Clerk |
| `CLERK_SECRET_KEY` | — | (frontend, server-side) chave secreta Clerk |
| `BACKEND_URL` | `http://backend:8000` | (frontend) destino do proxy `/api/v1/[...path]` |

> ⚠️ **`OPENAI_CHAT_MODEL` padrão**: o valor default em `backend/app/core/config.py:14` é `gpt-5.4`, que não corresponde a um modelo OpenAI publicado. Em qualquer ambiente real, sobrescreva a variável (ex.: `OPENAI_CHAT_MODEL=gpt-4.1`) ou corrija o default no código antes de subir o stack.

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
│   │   │   ├── deps.py              # autenticação JWT, dependências Qdrant/DB
│   │   │   ├── routes/
│   │   │   │   ├── chat.py          # POST /chat (streaming SSE, filtra user_id)
│   │   │   │   ├── documents.py     # POST/GET/GET-{id}/DELETE /documents
│   │   │   │   ├── health.py        # GET /health
│   │   │   │   ├── metrics.py       # GET /metrics
│   │   │   │   └── multimodal.py    # POST /upload/image|audio
│   │   │   └── schemas/             # modelos Pydantic (chat, documents, error)
│   │   ├── core/
│   │   │   ├── config.py            # Settings (pydantic-settings)
│   │   │   ├── logging.py           # configuração de logs estruturados
│   │   │   └── metrics_store.py     # ring buffer p50/p95 latência + citações
│   │   ├── db/
│   │   │   ├── database.py          # engines async/sync, sessions, create_tables
│   │   │   └── models.py            # ORM SQLAlchemy 2.0 (Document)
│   │   ├── storage/
│   │   │   ├── provider.py          # Protocol StorageProvider
│   │   │   └── supabase_provider.py # implementação Supabase Storage
│   │   ├── integrations/
│   │   │   └── openai_client.py     # embed_texts, stream_answer, describe_image, transcribe_audio
│   │   ├── rag/
│   │   │   └── prompts.py           # SYSTEM_PROMPT (grounding), VISION_PROMPT
│   │   ├── services/
│   │   │   ├── chat.py              # orquestração: embed → retrieve → rerank → stream
│   │   │   ├── ingestion.py         # chunking estrutural, metadata, OCR, SHA256, status callback
│   │   │   ├── reranking.py         # CohereReranker (opcional)
│   │   │   └── retrieval.py         # query Qdrant com filtro user_id + metadata
│   │   ├── workers/
│   │   │   ├── celery_app.py        # configuração Celery
│   │   │   └── tasks.py             # mka.ingest_document, mka.reindex_books (legacy)
│   │   └── main.py                  # FastAPI app, lifespan (cria tabelas), middleware, routers
│   ├── tests/                       # pytest-asyncio, modo APP_ENV=test
│   ├── reindex_corpus.py            # CLI de indexação administrativa (corpus base)
│   ├── livros/                      # PDFs do corpus admin (gitignored)
│   ├── Dockerfile
│   └── pyproject.toml
│
├── frontend/
│   ├── app/                         # Next.js App Router
│   │   ├── chat/page.tsx            # workspace principal
│   │   ├── sign-in/[[...sign-in]]/  # Clerk sign-in page
│   │   ├── sign-up/[[...sign-up]]/  # Clerk sign-up page
│   │   ├── api/v1/[...path]/route.ts# proxy transparente para o backend
│   │   ├── providers.tsx            # ClerkProvider condicional
│   │   ├── lib/clerk.ts             # flag isClerkEnabled
│   │   ├── layout.tsx
│   │   └── page.tsx                 # redirect → /chat
│   ├── components/
│   │   ├── chat/                    # ChatWindow, ChatComposer, DocumentPanel
│   │   ├── citations/               # CitationList
│   │   ├── documents/               # DocumentManager (drag-drop, polling), StatusBadge
│   │   ├── upload/                  # UploadPanel (imagem/áudio)
│   │   ├── markdown/                # MarkdownRenderer (typography)
│   │   ├── layout/                  # HeaderBar
│   │   └── ui/                      # Button, Card, Badge, Textarea
│   ├── hooks/
│   │   └── use-chat-session.ts      # estado central + polling 3s de documentos
│   ├── services/
│   │   ├── api.ts                   # fetchDocuments, uploadDocument, deleteDocument, streamChat, uploadAttachment
│   │   └── sse.ts                   # parser genérico de Server-Sent Events
│   ├── types/chat.ts                # Citation, ChatMessage, UploadItem, UserDocument, DocumentStatus
│   ├── middleware.ts                # Clerk auth (no-op se NEXT_PUBLIC_ENABLE_CLERK=false)
│   └── Dockerfile
│
├── .rules/                          # especificações do produto (fonte da verdade)
│   ├── Product-Requirements-Document-(PRD).md
│   ├── system_architecture_document_mka_v_1.md
│   ├── RAG_Architecture_Specification_MKA.md
│   ├── Backend_Spec_MKA.md
│   └── Frontend_Spec_MKA.md
│
├── docker-compose.yml               # base (6 serviços: qdrant, redis, postgres, backend, worker, frontend)
├── docker-compose.dev.yml           # override dev (hot reload, bind mounts)
├── docker-compose.prod.yml          # override prod
└── .env.example                     # template de variáveis de ambiente
```

---

## Fora do escopo (V1)

A plataforma é **multi-tenant por usuário** (cada usuário Clerk vê apenas seus próprios documentos e chunks). As funcionalidades abaixo foram deliberadamente excluídas do V1:

- Memória persistente de conversação
- **Colaboração ativa entre usuários** (compartilhamento de documentos, conversas ou knowledge bases — o isolamento por `user_id` é estrito)
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
