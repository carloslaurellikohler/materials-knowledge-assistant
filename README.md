# Materials Knowledge Assistant
### Projeto de Estudo — AWS Certified Generative AI Developer (AIP-C01)

> Sistema RAG multimodal 100% serverless na AWS, desenvolvido como projeto prático de estudo para a certificação AIP-C01. Permite que especialistas em Engenharia de Materiais consultem sua base de conhecimento em PDFs via chat com voz, texto e imagens — obtendo respostas referenciadas com citações precisas.

---

## Índice

- [Visão Geral](#visão-geral)
- [Arquitetura](#arquitetura)
- [Funcionalidades](#funcionalidades)
- [Serviços AWS Utilizados](#serviços-aws-utilizados)
- [Cobertura do Exame AIP-C01](#cobertura-do-exame-aip-c01)
- [Estrutura do Projeto](#estrutura-do-projeto)
- [Fases de Desenvolvimento](#fases-de-desenvolvimento)
- [Pré-requisitos](#pré-requisitos)
- [Deploy](#deploy)
- [Variáveis de Ambiente](#variáveis-de-ambiente)
- [Estimativa de Custo](#estimativa-de-custo)
- [Decisões Arquiteturais](#decisões-arquiteturais)
- [Roadmap](#roadmap)

---

## Visão Geral

O Materials Knowledge Assistant é um assistente de IA especializado em Engenharia de Materiais construído sobre uma arquitetura RAG (Retrieval Augmented Generation) completamente serverless na AWS. O sistema ingere PDFs técnicos, extrai e indexa seu conteúdo em um vector store, e responde perguntas com citações precisas indicando livro e página de origem.

**Caso de uso:** Especialista atuando de forma isolada na área de análise e avaliação de materiais precisa consultar rapidamente conteúdo técnico distribuído em dezenas de livros e artigos em PDF, inclusive enviando fotos de microestruturas ou fractografias para análise.

---

## Arquitetura

```
┌─────────────────────────────────────────────────────────────────┐
│                        CAMADA DE ACESSO                         │
│                                                                 │
│  Browser ──→ CloudFront ──→ Lambda@Edge ──→ Cognito (auth)     │
│                  └──→ S3 (frontend React estático)              │
└─────────────────────────────────────────────────────────────────┘
                              │ HTTPS + JWT
┌─────────────────────────────────────────────────────────────────┐
│                         CAMADA DE API                           │
│                                                                 │
│  API Gateway ──→ Cognito Authorizer (valida JWT)               │
│       ├──→ Lambda: /chat         (query + streaming)           │
│       ├──→ Lambda: /upload-url   (presigned S3 URL)            │
│       └──→ Lambda: /history      (histórico de conversas)      │
└─────────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────────┐
│                      CAMADA DE COMPUTE                          │
│                                                                 │
│  Lambda (Query Handler)                                         │
│    1. Carrega histórico ──→ DynamoDB                            │
│    2. Gera embedding   ──→ Bedrock (Titan Embeddings v2)        │
│    3. Busca vetores    ──→ OpenSearch Serverless (hybrid kNN)   │
│    4. Monta prompt     ──→ contexto + histórico + citações      │
│    5. Gera resposta    ──→ Bedrock (Claude Sonnet) + Guardrails │
│    6. Salva histórico  ──→ DynamoDB                             │
│    7. Stream resposta  ──→ API Gateway ──→ Browser              │
└─────────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────────┐
│                    CAMADA DE DADOS / IA                         │
│                                                                 │
│  Amazon S3                  (PDFs originais + mídia temp)       │
│  Amazon Textract             (extração estruturada de PDFs)     │
│  Amazon Transcribe           (áudio → texto PT-BR)              │
│  Amazon Rekognition          (pré-classificação de imagens)     │
│  Amazon Bedrock              (embeddings, geração, guardrails)  │
│  OpenSearch Serverless       (vector store, hybrid search)      │
│  Amazon DynamoDB             (metadados + histórico de chat)    │
│  ElastiCache Redis           (semantic cache)                   │
└─────────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────────┐
│                  CAMADA DE OBSERVABILIDADE                      │
│                                                                 │
│  Amazon CloudWatch    (métricas, logs, dashboards, alertas)    │
│  AWS X-Ray            (distributed tracing)                    │
│  AWS CloudTrail       (audit log de todas as chamadas)         │
│  Amazon Macie         (detecção de PII nos PDFs)               │
│  Bedrock Model Evals  (golden dataset + LLM-as-a-Judge)        │
│  SageMaker Clarify    (bias evaluation + model cards)          │
└─────────────────────────────────────────────────────────────────┘
```

---

## Funcionalidades

### Chat com RAG
- Perguntas em linguagem natural sobre conteúdo dos PDFs
- Respostas com citações explícitas: livro, capítulo e página
- Histórico de conversa persistido por sessão no DynamoDB
- Streaming de tokens em tempo real via API Gateway

### Entrada Multimodal
- **Texto:** digitação direta no chat
- **Áudio:** gravação no browser → Amazon Transcribe → texto → RAG
- **Imagem:** upload de foto (microestrutura, fratura, diagrama) → Rekognition (labels) → Bedrock multimodal

### Autenticação em Duas Camadas
- **Camada 1:** Lambda@Edge + Cognito controla acesso ao frontend
- **Camada 2:** JWT via Cognito Authorizer protege todos os endpoints da API
- Login com email/senha, Google OAuth 2.0 e MFA (TOTP)

### Segurança e Governance
- Bedrock Guardrails bloqueia perguntas fora do domínio técnico
- Detecção de prompt injection e jailbreak
- PII detection via Amazon Macie nos PDFs
- IAM least privilege por função Lambda
- Criptografia em repouso com KMS CMK

---

## Serviços AWS Utilizados

| Categoria | Serviço | Papel |
|---|---|---|
| **Storage** | Amazon S3 | PDFs originais, frontend React, mídia temporária |
| **CDN / Auth** | Amazon CloudFront | Serve frontend, HTTPS, OAC |
| **Auth / Edge** | Lambda@Edge | Intercepta requisições, valida sessão Cognito |
| **Identidade** | Amazon Cognito | User pool, OAuth 2.0, MFA, JWT |
| **API** | Amazon API Gateway | REST API com streaming, rate limiting, WAF |
| **Compute** | AWS Lambda | Todos os handlers de ingestão e query |
| **AI / Embeddings** | Amazon Bedrock (Titan) | Geração de embeddings 1536-dim |
| **AI / Geração** | Amazon Bedrock (Claude) | Geração de respostas + multimodal |
| **AI / Controles** | Bedrock Guardrails | Filtros de input/output, prompt injection |
| **AI / Prompts** | Bedrock Prompt Management | Versionamento de system prompts |
| **AI / RAG** | Bedrock Knowledge Bases | Pipeline RAG gerenciado (comparativo) |
| **Vector Store** | OpenSearch Serverless | kNN HNSW, hybrid search, reranking |
| **Banco de Dados** | Amazon DynamoDB | Metadados de chunks + histórico de conversas |
| **Cache** | ElastiCache (Redis) | Semantic caching de respostas |
| **OCR** | Amazon Textract | Extração estruturada de PDFs técnicos |
| **Transcrição** | Amazon Transcribe | Áudio → texto PT-BR |
| **Visão Computacional** | Amazon Rekognition | Pré-classificação de imagens |
| **Segurança** | Amazon Macie | Detecção de PII nos PDFs |
| **Segurança** | AWS WAF | Rate limiting e proteção na borda |
| **Segurança** | AWS KMS | Criptografia CMK para S3 e OpenSearch |
| **Monitoramento** | Amazon CloudWatch | Métricas, logs, dashboards, alertas |
| **Tracing** | AWS X-Ray | Distributed tracing do pipeline RAG |
| **Auditoria** | AWS CloudTrail | Audit log de todas as chamadas à AWS |
| **Avaliação** | Bedrock Model Evaluations | Avaliação automática de qualidade |
| **Responsible AI** | SageMaker Clarify | Bias evaluation, model cards |

---

## Cobertura do Exame AIP-C01

Este projeto foi desenhado para cobrir os 5 domínios do exame na prática:

### Domínio 1 — Foundation Model Integration (31%)
| Task | O que é praticado |
|---|---|
| 1.2 | Seleção de FM (Claude Sonnet vs. outros), benchmarks, LoRA trade-offs |
| 1.3 | Pipeline de validação: Textract + Lambda + Transcribe + Bedrock multimodal |
| 1.4 | Vector store com OpenSearch: hierarquia, metadados, sharding por domínio |
| 1.5 | Chunking fixo vs. hierárquico, Titan embeddings, hybrid search, reranker |
| 1.6 | Bedrock Prompt Management, chain-of-thought, Prompt Flows |

### Domínio 2 — Implementation and Integration (26%)
| Task | O que é praticado |
|---|---|
| 2.3 | CI/CD para GenAI, enterprise integration via API Gateway |
| 2.4 | Streaming API, presigned URLs, exponential backoff, roteamento |
| 2.5 | Bedrock Prompt Flows, Amazon Q Developer, padrões de integração |

### Domínio 3 — AI Safety, Security and Governance (20%)
| Task | O que é praticado |
|---|---|
| 3.1 | Bedrock Guardrails input/output, prompt injection detection |
| 3.2 | VPC endpoints, IAM least privilege, Macie PII, KMS CMK |
| 3.3 | CloudTrail audit, compliance frameworks, data lineage |
| 3.4 | Transparency (citações), fairness (Clarify), model cards |

### Domínio 4 — Operational Efficiency (12%)
| Task | O que é praticado |
|---|---|
| 4.1 | Token optimization, semantic caching (ElastiCache), cost tracking |
| 4.3 | CloudWatch dashboards, X-Ray tracing, Bedrock Invocation Logs |

### Domínio 5 — Testing, Validation and Troubleshooting (11%)
| Task | O que é praticado |
|---|---|
| 5.1 | Golden dataset, Bedrock Model Evaluations, LLM-as-a-Judge |
| 5.2 | Context window overflow, embedding drift, prompt confusion |

---

## Estrutura do Projeto

```
materials-knowledge-assistant/
│
├── infra/                          # IaC (AWS CDK)
│   ├── stacks/
│   │   ├── storage_stack.py        # S3, DynamoDB, ElastiCache
│   │   ├── ingestion_stack.py      # Textract, Lambda ingestão
│   │   ├── vector_stack.py         # OpenSearch Serverless
│   │   ├── api_stack.py            # API Gateway, Lambda handlers
│   │   ├── auth_stack.py           # Cognito, Lambda@Edge
│   │   └── observability_stack.py  # CloudWatch, X-Ray, CloudTrail
│   └── app.py
│
├── lambdas/
│   ├── ingestion/
│   │   ├── pdf_processor.py        # S3 event → Textract → chunking
│   │   ├── chunker.py              # Fixed + hierarchical chunking
│   │   └── embedder.py             # Titan embeddings → OpenSearch
│   │
│   ├── query/
│   │   ├── handler.py              # Query handler principal
│   │   ├── history.py              # Carrega/salva histórico DynamoDB
│   │   ├── retriever.py            # OpenSearch hybrid search
│   │   └── generator.py           # Bedrock Claude + streaming
│   │
│   ├── multimodal/
│   │   ├── audio_handler.py        # Presigned URL + Transcribe
│   │   └── image_handler.py        # Presigned URL + Rekognition
│   │
│   └── auth/
│       └── edge_auth.py            # Lambda@Edge Cognito check
│
├── frontend/                       # React app (deploy → S3)
│   ├── src/
│   │   ├── components/
│   │   │   ├── Chat.tsx
│   │   │   ├── AudioRecorder.tsx
│   │   │   ├── ImageUpload.tsx
│   │   │   └── CitationCard.tsx
│   │   ├── hooks/
│   │   │   ├── useStream.ts        # SSE streaming handler
│   │   │   └── useHistory.ts       # Histórico de conversa
│   │   └── services/
│   │       └── api.ts              # API Gateway client + JWT
│   └── package.json
│
├── evaluation/                     # Fase 5 — Model Evaluation
│   ├── golden_dataset.jsonl        # 50+ pares pergunta/resposta esperada
│   ├── bedrock_eval_job.py         # Configura job no Bedrock Model Evals
│   └── llm_judge.py                # LLM-as-a-Judge pipeline
│
├── docs/
│   ├── architecture-diagram.html
│   └── adr/                        # Architecture Decision Records
│       ├── ADR-001-opensearch-vs-aurora.md
│       ├── ADR-002-managed-vs-manual-rag.md
│       └── ADR-003-serverless-vs-containers.md
│
└── README.md
```

---

## Fases de Desenvolvimento

### Fase 1 — Ingestão de PDFs
**Objetivo:** Pipeline de ingestão automatizado de PDFs para o vector store.

Entregáveis:
- Bucket S3 com S3 Event → Lambda trigger
- Lambda de processamento: Textract → chunking → Titan embeddings → OpenSearch
- Tabela DynamoDB com metadados dos chunks
- Testes unitários do chunker

Serviços: S3, Textract, Lambda, Bedrock (Titan), OpenSearch Serverless, DynamoDB

---

### Fase 2 — RAG Pipeline
**Objetivo:** Pipeline de query e geração com citações.

Entregáveis:
- Lambda Query Handler completo
- Hybrid search (BM25 + kNN) no OpenSearch
- Histórico de conversa no DynamoDB
- Bedrock Prompt Management configurado
- Bedrock Guardrails ativo

Serviços: Lambda, OpenSearch, DynamoDB, Bedrock (Claude + Prompt Management + Guardrails)

---

### Fase 3 — Multimodal
**Objetivo:** Adicionar entrada por voz e imagem.

Entregáveis:
- Lambda para geração de Presigned URLs
- Pipeline áudio: gravação → S3 → Transcribe → texto → RAG
- Pipeline imagem: upload → S3 → Rekognition labels → Bedrock multimodal
- Histórico persistindo tipo de cada mensagem (text/audio/image)

Serviços: Transcribe, Rekognition, Bedrock multimodal, S3, Lambda

---

### Fase 4 — API, Frontend e Autenticação
**Objetivo:** Interface funcional com autenticação em duas camadas.

Entregáveis:
- API Gateway com endpoints /chat, /upload-url, /history
- Cognito User Pool com Google OAuth + MFA
- Lambda@Edge para proteção do CloudFront
- Frontend React com chat + gravação de áudio + upload de imagem
- Deploy automático frontend: GitHub Actions → S3 → CloudFront invalidation

Serviços: API Gateway, Cognito, Lambda@Edge, CloudFront, S3, WAF

---

### Fase 5 — Observabilidade e Model Evaluation
**Objetivo:** Visibilidade operacional e avaliação sistemática de qualidade.

Entregáveis:
- Dashboard CloudWatch: token usage, latência P95, custo/query
- X-Ray tracing end-to-end
- ElastiCache semantic cache
- Golden dataset com 50+ perguntas de Engenharia de Materiais
- Job no Bedrock Model Evaluations com métricas automáticas
- LLM-as-a-Judge pipeline
- SageMaker Clarify bias evaluation + model card

Serviços: CloudWatch, X-Ray, CloudTrail, ElastiCache, Macie, Bedrock Model Evaluations, SageMaker Clarify

---

## Pré-requisitos

```bash
# AWS CLI configurado
aws configure

# AWS CDK instalado
npm install -g aws-cdk
cdk bootstrap

# Python 3.11+
python --version

# Node 18+ (frontend)
node --version

# Habilitar modelos no Amazon Bedrock
# Console AWS → Bedrock → Model access → Solicitar acesso:
# - Anthropic Claude Sonnet
# - Amazon Titan Embeddings V2
```

---

## Deploy

```bash
# Clone e instale dependências
git clone https://github.com/seu-usuario/materials-knowledge-assistant
cd materials-knowledge-assistant

# Deploy da infraestrutura (ordem das stacks)
cd infra
pip install -r requirements.txt

cdk deploy StorageStack
cdk deploy VectorStack
cdk deploy IngestionStack
cdk deploy AuthStack
cdk deploy ApiStack
cdk deploy ObservabilityStack

# Build e deploy do frontend
cd ../frontend
npm install
npm run build
aws s3 sync dist/ s3://$FRONTEND_BUCKET --delete
aws cloudfront create-invalidation --distribution-id $CF_DISTRIBUTION_ID --paths "/*"

# Upload dos PDFs para ingestão
aws s3 cp ./pdfs/ s3://$DOCUMENTS_BUCKET/pdfs/ --recursive
# A ingestão é disparada automaticamente via S3 Event
```

---

## Variáveis de Ambiente

| Variável | Descrição |
|---|---|
| `DOCUMENTS_BUCKET` | Nome do bucket S3 para os PDFs |
| `FRONTEND_BUCKET` | Nome do bucket S3 do frontend |
| `OPENSEARCH_ENDPOINT` | Endpoint do OpenSearch Serverless |
| `OPENSEARCH_INDEX` | Nome do índice de vetores |
| `DYNAMODB_TABLE_METADATA` | Tabela de metadados dos chunks |
| `DYNAMODB_TABLE_HISTORY` | Tabela de histórico de conversas |
| `BEDROCK_REGION` | Região AWS do Bedrock (ex: us-east-1) |
| `BEDROCK_MODEL_ID` | ID do modelo Claude (ex: anthropic.claude-sonnet-4-5) |
| `BEDROCK_EMBEDDING_MODEL_ID` | ID do modelo Titan Embeddings |
| `BEDROCK_GUARDRAIL_ID` | ID do Guardrail configurado |
| `COGNITO_USER_POOL_ID` | ID do Cognito User Pool |
| `COGNITO_CLIENT_ID` | Client ID da aplicação no Cognito |
| `ELASTICACHE_ENDPOINT` | Endpoint do Redis para semantic cache |
| `CF_DISTRIBUTION_ID` | ID da distribuição CloudFront |

---

## Estimativa de Custo

Baseado em uso pessoal com 20–100 PDFs e ~50 queries/dia.

| Serviço | Estimativa Mensal | Observação |
|---|---|---|
| OpenSearch Serverless | ~$8–12 | Mínimo por OCU-hora |
| Amazon Bedrock (Claude) | ~$3–8 | ~50 queries/dia, respostas médias |
| Amazon Bedrock (Titan) | ~$0.50 | Só na ingestão (one-time) |
| Amazon Transcribe | ~$0.50 | Uso esporádico |
| AWS Lambda | ~$0 | Free tier cobre facilmente |
| Amazon DynamoDB | ~$0 | Free tier cobre facilmente |
| Amazon S3 | ~$0.50 | PDFs + frontend + mídia temp |
| CloudFront | ~$0 | Free tier cobre facilmente |
| ElastiCache (cache.t3.micro) | ~$12 | Reduz custo Bedrock em recorrências |
| **Total estimado** | **~$25–35/mês** | |

> **Dica de economia durante desenvolvimento:** Substitua OpenSearch Serverless por Aurora PostgreSQL + pgvector (~$0 no free tier) e remova ElastiCache. Custo cai para ~$5–10/mês.

---

## Decisões Arquiteturais

### ADR-001: OpenSearch Serverless vs. Aurora + pgvector
**Decisão:** OpenSearch Serverless em produção, Aurora em desenvolvimento.
**Razão:** OpenSearch oferece hybrid search nativo (BM25 + kNN), reranker integrado e sharding por domínio técnico. Aurora + pgvector é mais econômico para desenvolvimento mas limitado para hybrid search. **Relevância AIP-C01:** Task 1.5.3 — decisão de vector store cobrada no exame.

### ADR-002: Bedrock Knowledge Bases gerenciado vs. Pipeline manual
**Decisão:** Implementar ambos para fins didáticos; produção usa pipeline manual.
**Razão:** Bedrock KB é mais rápido de configurar mas oferece menos controle sobre chunking, embedding e search. Pipeline manual com Lambda + OpenSearch permite hybrid search, reranking e metadados customizados. **Relevância AIP-C01:** Trade-off central do Domínio 1.

### ADR-003: Serverless vs. Containers
**Decisão:** 100% serverless com Lambda e serviços gerenciados.
**Razão:** Carga esporádica e baixo volume não justificam custo fixo de ECS/EKS. Lambda escala a zero automaticamente. Containers serão usados apenas na fase de agentes para servidor MCP complexo. **Relevância AIP-C01:** Task 2.2 — quando usar cada modelo de deploy.

### ADR-004: Frontend estático vs. SSR
**Decisão:** Frontend React estático no S3 + CloudFront.
**Razão:** Interface de chat não precisa de SSR. Estático é mais simples, barato e seguro. Estado da aplicação (histórico) vive no backend (DynamoDB), não no frontend. Streaming de tokens via SSE funciona perfeitamente com frontend estático.

---

## Roadmap

### v1.0 — MVP (Fases 1–4)
- [x] Arquitetura desenhada
- [ ] Fase 1: Pipeline de ingestão
- [ ] Fase 2: RAG + geração
- [ ] Fase 3: Multimodal (áudio + imagem)
- [ ] Fase 4: API + auth + frontend

### v1.1 — Observabilidade (Fase 5)
- [ ] CloudWatch dashboard
- [ ] X-Ray tracing
- [ ] Semantic cache
- [ ] Bedrock Model Evaluations
- [ ] LLM-as-a-Judge

### v2.0 — Agentes (Fase Futura)
- [ ] Strands Agent com tool de APIs externas de materiais
- [ ] Servidor MCP em ECS para tools complexas
- [ ] AWS Agent Squad para multi-agente
- [ ] Step Functions para ReAct pattern

---

## Referências

- [AWS Certified Generative AI Developer — Exam Guide (AIP-C01)](https://docs.aws.amazon.com/pdfs/aws-certification/latest/ai-professional-01/ai-professional-01.pdf)
- [Amazon Bedrock Documentation](https://docs.aws.amazon.com/bedrock/)
- [Amazon OpenSearch Serverless — Vector Search](https://docs.aws.amazon.com/opensearch-service/latest/developerguide/serverless-vector-search.html)
- [AWS Well-Architected Framework — Generative AI Lens](https://docs.aws.amazon.com/wellarchitected/latest/generative-ai-lens/)
- [Bedrock Guardrails](https://docs.aws.amazon.com/bedrock/latest/userguide/guardrails.html)
- [Bedrock Model Evaluations](https://docs.aws.amazon.com/bedrock/latest/userguide/model-evaluation.html)

---

*Projeto desenvolvido como estudo prático para a certificação AWS Certified Generative AI Developer (AIP-C01) — © 2026 L&K Tech Solutions*
