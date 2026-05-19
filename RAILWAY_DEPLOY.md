# Deploy do MKA no Railway

Guia operacional para subir o projeto em produção. Os `docker-compose*.yml` continuam servindo apenas para desenvolvimento local — no Railway, cada serviço é criado individualmente e consome os `Dockerfile` de `backend/` e `frontend/`.

## Resumo dos serviços a criar

| # | Serviço Railway | Tipo | Fonte | Observações |
|---|-----------------|------|-------|-------------|
| 1 | `postgres` | Plugin gerenciado | Marketplace → Postgres | Expõe `DATABASE_URL`, `PGUSER`, `PGPASSWORD`, `PGHOST`, `PGPORT`, `PGDATABASE` |
| 2 | `redis` | Plugin gerenciado | Marketplace → Redis | Expõe `REDIS_URL` |
| 3 | `qdrant` | Docker Image | `qdrant/qdrant:v1.11.3` | **Anexar Volume** em `/qdrant/storage` |
| 4 | `backend` | GitHub repo, root `backend/` | usa `backend/Dockerfile` + `backend/railway.json` | Healthcheck `/api/v1/health` |
| 5 | `worker` | GitHub repo, root `backend/` | mesma source do backend | **Override do Start Command** no dashboard |
| 6 | `frontend` | GitHub repo, root `frontend/` | usa `frontend/Dockerfile` + `frontend/railway.json` | Healthcheck `/` |

Crie nessa ordem — backend/worker dependem dos plugins, e frontend depende do backend.

## Passos prévios (uma vez)

1. **Rotacionar segredos** que existem hoje em `.env` locais (OpenAI, Cohere, Supabase service_role, Clerk). Eles serão recriados no painel Railway.
2. **Clerk → produção**: criar uma *production instance* no Clerk, configurar o domínio do frontend, gerar novas `pk_live_*` / `sk_live_*` e copiar a nova `JWKS URL`.
3. **CORS**: a lista de origins é lida de `CORS_ALLOWED_ORIGINS` (string separada por vírgula). Adicione o domínio público do frontend Railway nessa variável.
4. **Garantir que `backend/.dockerignore` cobre `.env`** (já cobre) para a imagem não vazar segredos.

## Variáveis por serviço

Use *variable references* (`${{Service.VAR}}`) sempre que possível, em vez de copiar/colar valores.

### `qdrant`
Nenhuma variável obrigatória além da imagem. **Anexe um Volume** com mount path `/qdrant/storage` — sem isso, o índice vetorial é perdido a cada redeploy. Não expor publicamente.

### `backend`
| Variável | Valor recomendado |
|---|---|
| `DATABASE_URL` | `postgresql+asyncpg://${{Postgres.PGUSER}}:${{Postgres.PGPASSWORD}}@${{Postgres.RAILWAY_PRIVATE_DOMAIN}}:${{Postgres.PGPORT}}/${{Postgres.PGDATABASE}}` |
| `REDIS_URL` | `${{Redis.REDIS_URL}}/0` |
| `QDRANT_URL` | `http://${{qdrant.RAILWAY_PRIVATE_DOMAIN}}:6333` |
| `APP_ENV` | `prod` |
| `OPENAI_API_KEY` | *(secret)* |
| `COHERE_API_KEY` | *(secret, opcional)* |
| `CLERK_JWKS_URL` | URL JWKS da instance Clerk de produção |
| `CLERK_JWT_SECRET` | qualquer string (não usada quando há JWKS) |
| `SUPABASE_URL` | URL do projeto Supabase |
| `SUPABASE_KEY` | service_role key |
| `SUPABASE_BUCKET` | `mka-documents` |
| `CORS_ALLOWED_ORIGINS` | `https://${{frontend.RAILWAY_PUBLIC_DOMAIN}}` *(adicionar outras origins separadas por vírgula se necessário)* |
| `PORT` | injetada pelo Railway — **não setar manualmente** |

> **Por que reescrever `DATABASE_URL`:** o plugin Postgres expõe a URL com schema `postgresql://`, mas o backend usa `postgresql+asyncpg://` (e converte internamente para `postgresql+psycopg2://` no worker). Montando manualmente garantimos o driver correto.

Expor domínio público (Settings → Networking → Generate Domain).

### `worker`
- Source idêntica ao backend (mesmo repo, root `backend/`).
- **Start Command (override no dashboard):**
  ```
  celery -A app.workers.celery_app.celery_app worker --loglevel=INFO
  ```
- Mesmas variáveis do backend (`DATABASE_URL`, `REDIS_URL`, `QDRANT_URL`, OpenAI/Cohere/Supabase, Clerk).
- **Sem domínio público** — worker não escuta HTTP.
- Sem healthcheck HTTP (Celery não tem). Pode deixar o restart policy do `railway.json` agindo.

### `frontend`
| Variável | Valor |
|---|---|
| `BACKEND_URL` | `https://${{backend.RAILWAY_PUBLIC_DOMAIN}}` *(ou `http://${{backend.RAILWAY_PRIVATE_DOMAIN}}:${{backend.PORT}}` se todas as chamadas forem server-side)* |
| `NEXT_PUBLIC_ENABLE_CLERK` | `true` |
| `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` | `pk_live_...` |
| `CLERK_SECRET_KEY` | `sk_live_...` |
| `NEXT_TELEMETRY_DISABLED` | `1` |
| `PORT` | injetada pelo Railway |

Expor domínio público. **Depois do primeiro deploy**, voltar no Clerk e adicionar esse domínio nas *Allowed origins*.

## Migrations (Alembic)

Estado atual: o `pyproject.toml` declara `alembic>=1.13`, mas **não há `alembic.ini` nem pasta `migrations/`**. O backend cria as tabelas no startup via `Base.metadata.create_all()` em `app/main.py:23`.

- **Primeiro deploy**: funciona como está. A tabela `documents` é criada automaticamente quando o backend sobe contra o Postgres do Railway.
- **Limitação importante**: `create_all` só cria tabelas que não existem. **Qualquer alteração futura no schema** (nova coluna, índice, mudança de tipo) precisa de Alembic — caso contrário o Postgres de produção fica defasado em relação aos modelos.
- **Ação recomendada antes da próxima mudança de schema**:
  1. `cd backend && alembic init migrations`
  2. Configurar `migrations/env.py` para usar `app.db.database.Base.metadata`.
  3. Gerar baseline: `alembic revision --autogenerate -m "baseline"`.
  4. Marcar como aplicada no banco existente: `alembic stamp head`.
  5. Substituir `await create_tables()` no lifespan por `alembic upgrade head` (programaticamente) ou rodá-lo como pre-deploy command no Railway.

## Reindexação inicial do corpus

O `backend/reindex_corpus.py` precisa rodar **uma vez** após o primeiro deploy do backend, para popular o Qdrant. Opções:

- **Mais simples**: `railway run --service backend python reindex_corpus.py` pelo CLI local (executa contra as variáveis do serviço).
- Alternativa: rodar como deploy command pontual ou job manual via Railway Cron.

## Notas finais

- Os `docker-compose*.yml` **podem ficar no repositório** — Railway os ignora e eles seguem úteis para dev local.
- Os arquivos `.env` (raiz, backend, frontend) **não vão para o Railway**. Já estão no `.gitignore`. As variáveis são definidas no painel/CLI.
- Para alterações futuras, prefira editar `backend/railway.json` e `frontend/railway.json` em vez do dashboard — mudanças versionadas são auditáveis.
- O `worker` não tem `railway.json` próprio porque compartilha source com o backend; o `startCommand` dele fica no dashboard. Se isso incomodar, alternativa é mover o worker para uma subpasta com Dockerfile + railway.json próprios.
