# Chatbot TCA

Chatbot multiusuário com histórico persistente por conversa, em Python (FastAPI + PostgreSQL),
usando um modelo da família Qwen 3. Requisitos e decisões em `elicitação dos requisitos.md`.

## Como usar a API

A interface é a documentação Swagger, em `/docs`.

- Cada cliente (navegador) tem **uma única conversa**, identificada por um cookie de sessão
  criado automaticamente na primeira requisição. Pelo Swagger, o navegador guarda e envia o
  cookie sozinho.
- A conversa é removida após **1 hora sem atividade**; depois disso, uma nova é criada.

| Endpoint | Descrição |
|---|---|
| `GET /conversa` | Histórico da conversa (cria a conversa se ainda não existir). |
| `POST /conversa/mensagens` | Envia `{"pergunta": "..."}`; a resposta chega por SSE. |
| `GET /saude` | Verifica se a aplicação está no ar. |

`POST /conversa/mensagens` responde com `text/event-stream`, com os eventos `trecho`
(`{"texto"}`), `fim` (`{"mensagem_id"}`) ou `erro` (`{"detail"}`). Se outra resposta da mesma
conversa ainda estiver em geração, retorna **HTTP 409**.

Com `curl`, por HTTPS, mantenha os cookies entre chamadas:

```bash
curl -c cookies.txt -b cookies.txt -N -X POST https://SEU-HOST/conversa/mensagens \
  -H "Content-Type: application/json" -d '{"pergunta": "Olá!"}'
```

## Desenvolvimento local

Requisitos: Python 3.12+ e Docker.

```bash
docker compose up -d --wait          # PostgreSQL em 127.0.0.1:5434
python -m venv .venv
.venv/Scripts/activate               # Linux/macOS: source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env                 # ajuste se necessário
uvicorn app.main:app --port 8001     # Swagger em http://localhost:8001/docs
pytest                               # usa o banco chatbot_test
```

Sem configuração, a aplicação usa um **modelo simulado**, que só repete a pergunta. Para usar o
Qwen 3, defina no `.env` `LLM_PROVEDOR=openai`, `LLM_BASE_URL`, `LLM_API_KEY` e `LLM_MODELO`
(qualquer provedor com API compatível com a da OpenAI).
