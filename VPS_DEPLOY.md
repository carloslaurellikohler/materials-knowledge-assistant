# Deploy do MKA em VPS (Hostinger / Ubuntu)

Guia prático para subir o MKA do zero numa VPS Ubuntu limpa, com todos os serviços containerizados (Postgres, Qdrant, Redis, backend, worker, frontend) e um **nginx no host** fazendo proxy reverso + TLS para o domínio `app.meudominio.com`.

> Substitua `app.meudominio.com` pelo seu domínio real em todos os passos.

## Visão geral da topologia

```
Internet  ──443/TLS──►  nginx (host)  ──► 127.0.0.1:3000  ──►  frontend (container)
                                                                   │  /api/v1/* (proxy interno)
                                                                   ▼
                                                              backend (container :8000)
                                                                   ├── postgres   (rede interna)
                                                                   ├── qdrant      (rede interna)
                                                                   └── redis  ◄── worker (Celery)
```

Apenas o **frontend** é publicado, em `127.0.0.1:3000`. Postgres, Qdrant, Redis, backend e worker só são acessíveis pela rede interna do Docker Compose. O frontend já faz proxy de `/api/v1/*` para o backend internamente (`frontend/app/api/v1/[...path]/route.ts`), então o nginx só precisa conversar com o frontend.

> ⚠️ **Docker × UFW:** portas publicadas com `-p 0.0.0.0:porta` **contornam o UFW** (o Docker escreve regras na chain `DOCKER` do iptables). Por isso o `docker-compose.prod.yml` faz bind em `127.0.0.1` — essa é a barreira efetiva. O UFW protege apenas as portas do host (22/80/443).

---

## 1. Preparar a VPS

Acesse via SSH como root (ou o usuário fornecido pela Hostinger) e atualize o sistema:

```bash
apt update && apt upgrade -y
```

Crie um usuário não-root com sudo (substitua `deploy`):

```bash
adduser deploy
usermod -aG sudo deploy
```

(Opcional, recomendado) copie sua chave SSH para o novo usuário e depois desabilite login de root/senha em `/etc/ssh/sshd_config` (`PermitRootLogin no`, `PasswordAuthentication no`) e `systemctl restart ssh`. **Garanta que consegue logar como `deploy` antes de fechar a sessão atual.**

A partir daqui, trabalhe como `deploy`.

## 2. Firewall (UFW)

```bash
sudo ufw allow OpenSSH
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
sudo ufw status
```

As portas dos containers (3000, 5432, 6333, 6379, 8000) **não** precisam de regra — ficam em loopback / rede interna.

## 3. Instalar Docker + Docker Compose plugin

Repositório oficial do Docker:

```bash
sudo apt install -y ca-certificates curl gnupg
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
```

Permita usar o Docker sem `sudo` (reabra a sessão SSH depois):

```bash
sudo usermod -aG docker $USER
```

Verifique: `docker compose version`.

## 4. DNS

No painel de DNS do seu domínio, crie um registro **A**:

| Tipo | Nome | Valor |
|---|---|---|
| A | `app` (→ `app.meudominio.com`) | IP público da VPS |

Aguarde a propagação. Confirme com `dig +short app.meudominio.com` (deve retornar o IP da VPS) **antes** de emitir o certificado TLS (passo 8).

## 5. Clonar o repositório e configurar o `.env`

```bash
cd ~
git clone <URL_DO_SEU_REPO> materials-knowledge-assistant
cd materials-knowledge-assistant
cp .env.example .env
nano .env
```

Preencha o `.env` de produção:

```env
# OpenAI (obrigatório)
OPENAI_API_KEY=sk-...
# Defina um modelo de chat válido (o default do código é placeholder):
OPENAI_CHAT_MODEL=gpt-4.1

# Cohere (opcional)
COHERE_API_KEY=

# Postgres — senha forte (também protege os PDFs, que agora vivem no banco)
POSTGRES_PASSWORD=<senha-forte-aleatoria>

# Clerk (produção — instância production, chaves pk_live_/sk_live_)
CLERK_JWKS_URL=https://clerk.meudominio.com/.well-known/jwks.json
CLERK_JWT_SECRET=irrelevante-quando-ha-jwks

# CORS — domínio público do frontend
CORS_ALLOWED_ORIGINS=https://app.meudominio.com

# Frontend (Clerk)
NEXT_PUBLIC_ENABLE_CLERK=true
NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=pk_live_...
CLERK_SECRET_KEY=sk_live_...
```

O `.env` está no `.gitignore` — nunca o comite.

## 6. Subir o stack

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up --build -d
```

Acompanhe:

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml ps
docker compose -f docker-compose.yml -f docker-compose.prod.yml logs -f backend
```

O backend cria as tabelas (`documents`, `document_blobs`) automaticamente no startup. Teste local na própria VPS:

```bash
curl -s http://127.0.0.1:3000 | head    # frontend respondendo
```

## 7. Nginx no host (proxy reverso)

```bash
sudo apt install -y nginx
sudo nano /etc/nginx/sites-available/app.meudominio.com
```

Conteúdo (atenção ao suporte a **SSE/streaming** do `/chat` e ao limite de upload de PDF):

```nginx
server {
    listen 80;
    server_name app.meudominio.com;

    # Uploads de PDF (alinhe com MAX_UPLOAD_MB, default 100 MB)
    client_max_body_size 110M;

    location / {
        proxy_pass http://127.0.0.1:3000;
        proxy_http_version 1.1;
        proxy_set_header Host              $host;
        proxy_set_header X-Real-IP         $remote_addr;
        proxy_set_header X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # Streaming SSE (event: token ...): desligar buffering e cache
        proxy_buffering off;
        proxy_cache off;
        proxy_set_header Connection '';
        proxy_read_timeout 3600s;
    }
}
```

Ative e recarregue:

```bash
sudo ln -s /etc/nginx/sites-available/app.meudominio.com /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

## 8. TLS com Let's Encrypt (certbot)

Com o DNS já apontando para a VPS (passo 4):

```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d app.meudominio.com
```

O certbot ajusta o server block para HTTPS (443) e redireciona 80→443. A renovação automática é instalada via systemd timer; valide com:

```bash
sudo systemctl status certbot.timer
sudo certbot renew --dry-run
```

Acesse `https://app.meudominio.com` no navegador. **Depois**, no painel do Clerk (instância production), adicione `https://app.meudominio.com` às *Allowed origins*.

## 9. (Opcional) Indexar o corpus administrativo

Para pré-carregar um corpus base no Qdrant, coloque os PDFs em `backend/livros/` e rode dentro do container backend:

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml exec backend python reindex_corpus.py --recreate
```

> Vetores ingeridos por esse caminho não recebem `user_id` e não aparecem na busca filtrada por usuário — use apenas para corpus compartilhado/bootstrap.

## 10. Operação

| Tarefa | Comando |
|---|---|
| Ver logs | `docker compose -f docker-compose.yml -f docker-compose.prod.yml logs -f` |
| Reiniciar um serviço | `docker compose -f docker-compose.yml -f docker-compose.prod.yml restart backend` |
| Atualizar o código | `git pull && docker compose -f docker-compose.yml -f docker-compose.prod.yml up --build -d` |
| Parar tudo | `docker compose -f docker-compose.yml -f docker-compose.prod.yml down` |

### Backup

Os PDFs dos usuários agora vivem no Postgres (tabela `document_blobs`), então um dump do Postgres cobre **metadados + arquivos**. O Qdrant (vetores) pode ser reindexado a partir dos PDFs, mas vale versionar também:

```bash
# Backup do Postgres (metadados + bytes dos PDFs)
docker compose -f docker-compose.yml -f docker-compose.prod.yml exec -T postgres \
  pg_dump -U mka mka | gzip > backup_mka_$(date +%F).sql.gz

# Backup do volume do Qdrant
docker run --rm -v materials-knowledge-assistant_qdrant_data:/data -v "$PWD":/backup \
  alpine tar czf /backup/qdrant_$(date +%F).tar.gz -C /data .
```

> O nome do volume segue `<nome-do-projeto>_qdrant_data`; confirme com `docker volume ls`.
