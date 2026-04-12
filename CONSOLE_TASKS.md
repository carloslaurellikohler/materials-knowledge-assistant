# Console AWS — Tarefas Pendentes
> Materials Knowledge Assistant · Fase 1
> Executar antes de continuar o desenvolvimento no Claude Code

---

## Status Atual

- [x] S3 — bucket criado com SSE-KMS e versioning
- [x] S3 — pastas `pdfs/` e `temp/` criadas
- [x] OpenSearch Serverless — collection `materials-kb` Active
- [x] OpenSearch — índice `materials-chunks` criado (knn_vector 1536-dim, HNSW, cosinesimil)
- [x] DynamoDB — tabela `materials-kb-chunks` criada
- [x] DynamoDB — tabela `materials-kb-conversations` criada (com TTL em `expires_at`)
- [x] Bedrock — modelos Titan e Claude acessíveis

---

## Tarefas Pendentes no Console

---

### 1. IAM Role da Lambda de Ingestão 🔴
> **Prioridade alta — necessária para o embedder.py funcionar**

**Console → IAM → Roles → Create role**

**Step 1 — Trusted entity**
- Trusted entity type: `AWS service`
- Use case: `Lambda`
- Next

**Step 2 — Add permissions**
Buscar e adicionar as seguintes managed policies:
- `AmazonTextractFullAccess`
- `AmazonBedrockFullAccess`
- `AmazonDynamoDBFullAccess`
- `AmazonS3ReadOnlyAccess`
- `AWSXRayDaemonWriteAccess`

**Step 3 — Name and create**
- Role name: `materials-kb-lambda-ingestion-role`
- Create role ✓

**Step 4 — Adicionar política inline para OpenSearch Serverless**

Após criar a role, entre nela e:
- Add permissions → Create inline policy → JSON

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "aoss:APIAccessAll"
      ],
      "Resource": "arn:aws:aoss:us-east-1:*:collection/materials-kb"
    }
  ]
}
```

- Policy name: `materials-kb-opensearch-access`
- Save ✓

**Step 5 — Atualizar Data Access Policy do OpenSearch**

Console → OpenSearch Serverless → Security → Data access policies → `materials-kb-data-access` → Edit

Adicionar o ARN da role recém-criada como principal:
```
arn:aws:iam::<SEU-ACCOUNT-ID>:role/materials-kb-lambda-ingestion-role
```

Manter as mesmas permissões já configuradas. Save ✓

---

### 2. Bedrock Guardrails 🟡
> **Prioridade média — didático para o exame (Task 3.1)**

**Console → Amazon Bedrock → Guardrails → Create guardrail**

**Step 1 — Provide guardrail details**
- Name: `materials-kb-guardrail`
- Description: `Restringe respostas ao domínio de Engenharia de Materiais`

**Step 2 — Add content filters**

Harmful categories — configurar todos em **High** para input e output:
- Hate: High / High
- Insults: High / High
- Sexual: High / High
- Violence: High / High
- Misconduct: High / High
- Prompt Attack: High / High (bloqueia prompt injection)

**Step 3 — Add denied topics**

Add denied topic:
- Name: `fora-do-dominio`
- Definition: `Assuntos não relacionados à Engenharia de Materiais, ciência dos materiais, metalurgia, polímeros, cerâmicas ou compósitos`
- Sample phrases:
  - "como fazer um bolo"
  - "me conte uma piada"
  - "qual o resultado do jogo"
- Behavior: `BLOCK`

**Step 4 — Add word filters**
Deixar em branco por ora.

**Step 5 — Add sensitive information filters (PII)**

Habilitar detecção de PII e configurar como `BLOCK` para:
- NAME
- EMAIL
- PHONE
- CPF (adicionar como custom pattern se disponível)

**Step 6 — Add grounding**
- Grounding: Enable ✓
- Threshold: `0.75` (respostas precisam ter 75% de aderência ao contexto recuperado)

**Step 7 — Review and create**
- Create guardrail ✓

> **Anotar o Guardrail ID** exibido após criação — será usado nas variáveis de ambiente das Lambdas.

---

### 3. Bedrock Prompt Management 🟡
> **Prioridade média — versionamento do system prompt (Task 1.6.3)**

**Console → Amazon Bedrock → Prompt Management → Create prompt**

**Configuração:**
- Name: `materials-kb-system-prompt`
- Description: `System prompt do assistente de Engenharia de Materiais`
- Model: `Claude Sonnet` (versão disponível na sua conta)

**Template do prompt:**

```
Você é um assistente especializado em Engenharia de Materiais.

Suas responsabilidades:
- Responder perguntas técnicas sobre materiais metálicos, poliméricos, cerâmicos e compósitos
- Basear TODAS as respostas exclusivamente nos documentos fornecidos no contexto
- Citar sempre a fonte: livro e página de origem de cada informação

Regras obrigatórias:
- Se a informação não estiver nos documentos fornecidos, responda: "Não encontrei essa informação nos documentos disponíveis."
- Nunca invente dados, valores ou referências
- Mantenha linguagem técnica apropriada para uma especialista da área
- Respostas em português brasileiro

Formato das citações:
Ao final de cada informação relevante, inclua: (Fonte: [título do livro], p. [número da página])
```

- Create prompt ✓
- Após criar → **Create version** para fixar a v1

> **Anotar o Prompt ARN** exibido — será usado na Lambda de query (Fase 2).

---

### 4. CloudWatch Log Groups 🟢
> **Prioridade baixa — pode ser criado pelo CDK, mas vale fazer agora para já ter retention configurada**

**Console → CloudWatch → Log groups → Create log group**

**Log group 1:**
- Log group name: `/aws/lambda/materials-kb-pdf-processor`
- Retention: `30 days`
- Create ✓

**Log group 2:**
- Log group name: `/aws/lambda/materials-kb-query-handler`
- Retention: `30 days`
- Create ✓

---

## Informações para Anotar

Antes de fechar o Console, certifique-se de ter anotado:

| Informação | Onde encontrar | Valor |
|---|---|---|
| Account ID | Console → canto superior direito | `____________` |
| OpenSearch Endpoint | OpenSearch → Collections → materials-kb | `____________` |
| Guardrail ID | Bedrock → Guardrails → materials-kb-guardrail | `____________` |
| Prompt ARN | Bedrock → Prompt Management → materials-kb-system-prompt | `____________` |
| Lambda Role ARN | IAM → Roles → materials-kb-lambda-ingestion-role | `____________` |
| Bedrock Model ID (Claude) | Bedrock → Model catalog → Claude Sonnet | `____________` |

---

## Próximos Passos no Claude Code

Com as tarefas acima concluídas, continuar com:

1. `embedder.py` — chama Titan Embeddings → indexa no OpenSearch
2. `pdf_processor.py` — handler principal do S3 Event
3. Deploy das Lambdas via AWS CLI
4. Teste end-to-end com um PDF real
5. CDK — codificar toda a infraestrutura como IaC

---

*Materials Knowledge Assistant · AIP-C01 Study Project · L&K Tech Solutions*
