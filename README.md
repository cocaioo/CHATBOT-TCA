# Chatbot TCA

Chatbot multiusuário com histórico persistente por conversa, feito em Python (FastAPI +
PostgreSQL) e usando modelos da família **Qwen 3**. A interface é a própria API, usada pela
documentação **Swagger**. O enunciado está em `docs/requisitos.md`, e os requisitos e decisões
do projeto em `docs/elicitação dos requisitos.md`. Arquivos de infraestrutura (banco local e
acesso ao EC2) ficam em `infra/`.

## Acesso público

> **Endereço público: a definir após a implantação no AWS EC2.**

Quando publicado, o uso será o mesmo descrito neste README, trocando `http://localhost:8001` pelo
endereço público:

| O quê | Endereço |
|---|---|
| Documentação interativa (Swagger) | `https://<endereço-público>/docs` |
| Verificação de funcionamento | `https://<endereço-público>/saude` |

O acesso público exige HTTPS, porque o cookie de sessão só trafega por conexões seguras.

## Por que Qwen 3

| Característica | Por que importa neste projeto |
|---|---|
| Pesos abertos, licença Apache 2.0 | Roda na infraestrutura da equipe, sem custo por uso nem envio das conversas a terceiros. |
| Vários tamanhos na mesma família (0.6B a 235B) | O mesmo modelo vai de um notebook sem GPU a servidores maiores, trocando só a configuração. |
| Roda em CPU via Ollama | Compatível com as máquinas da equipe e com uma instância EC2 comum. |
| Multilíngue, incluindo português | Idioma das perguntas e respostas. |
| Modo de raciocínio desligável | Reduz a latência: primeiro trecho em ~0,1 s em vez de ~2 s (medido com `qwen3:0.6b`). |

O acesso usa a **API compatível com a da OpenAI** (SDK `openai`), formato adotado pelo Ollama e
pelos principais serviços que executam o Qwen 3. Assim, trocar de provedor não exige mudar código.
Medições e justificativas completas: `docs/elicitação dos requisitos.md`, seção 9, decisão 8.

## Sumário

1. [Pré-requisitos](#1-pré-requisitos)
2. [Rodando localmente](#2-rodando-localmente)
3. [Usando a API pelo Swagger](#3-usando-a-api-pelo-swagger)
4. [Trocando de modelo](#4-trocando-de-modelo)
5. [Rodando os testes](#5-rodando-os-testes)
6. [Configurações](#6-configurações)
7. [Referência da API](#7-referência-da-api)
8. [Problemas comuns](#8-problemas-comuns)

## 1. Pré-requisitos

| Ferramenta | Para quê | Obrigatório? |
|---|---|---|
| Python 3.12 ou superior | Rodar a aplicação | Sim |
| Docker Desktop (ou Docker no Linux) | Rodar o PostgreSQL | Sim |
| Git | Baixar o projeto | Sim |
| [Ollama](https://ollama.com) | Rodar modelos Qwen 3 localmente | Não; sem ele, a aplicação usa um modelo simulado |

## 2. Rodando localmente

Todos os comandos são executados na pasta do projeto.

### 2.1 Subir o banco de dados

Com o Docker Desktop aberto:

```bash
docker compose -f infra/docker-compose.yml up -d --wait
```

Isso cria um PostgreSQL acessível só pela sua máquina, em `127.0.0.1:5434`, com dois bancos:
`chatbot` (aplicação) e `chatbot_test` (testes automatizados). Os dados ficam num volume do Docker
e sobrevivem a reinícios. Para desligar: `docker compose -f infra/docker-compose.yml down`. Para
desligar **e apagar os dados**: `docker compose -f infra/docker-compose.yml down -v`.

### 2.2 Criar o ambiente virtual e instalar as dependências

**Windows (PowerShell):**

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
```

**Linux / macOS:**

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
```

Isso só precisa ser feito uma vez. Nas próximas vezes, basta ativar o ambiente (segunda linha).

### 2.3 Criar o arquivo de configuração

```bash
cp .env.example .env        # PowerShell: Copy-Item .env.example .env
```

Sem nenhuma alteração, a aplicação usa o **modelo simulado**, que apenas repete a pergunta. Isso
basta para testar a API. Para usar um Qwen 3 de verdade, veja a [seção 4](#4-trocando-de-modelo).

O `.env` não é versionado: nunca coloque chaves de API em outro arquivo.

### 2.4 Iniciar a aplicação

```bash
uvicorn app.main:app --port 8001
```

Abra **http://localhost:8001/docs** no navegador. Para parar, use `Ctrl+C`.

## 3. Usando a API pelo Swagger

1. Abra http://localhost:8001/docs.
2. Em **`POST /conversa/mensagens`**, clique em *Try it out*, escreva a pergunta e clique em
   *Execute*:
   ```json
   {"pergunta": "Qual a capital da França?"}
   ```
3. Em **`GET /conversa`**, clique em *Try it out* e *Execute* para ver o histórico.

Como funciona a sessão:

- Na primeira requisição, a aplicação cria uma conversa e um **cookie de sessão**. O navegador o
  guarda e o envia sozinho, então não é preciso copiar nenhum ID.
- **Cada navegador tem uma única conversa.** Todas as abas do mesmo navegador compartilham a
  conversa. Para simular outro usuário, use outro navegador ou uma janela anônima.
- A conversa é **apagada após 1 hora sem atividade**. Depois disso, uma nova é criada
  automaticamente.

A resposta da pergunta chega em partes (SSE), mas o Swagger só a exibe completa, ao final.

## 4. Trocando de modelo

A aplicação fala com qualquer serviço que use o **formato da API da OpenAI**. Esse formato é
apenas um padrão de requisição: o modelo continua sendo o Qwen 3, e nada passa pela OpenAI. Para
trocar de modelo ou de provedor, **edite o `.env` e reinicie a aplicação**. Não é preciso mudar
código.

### 4.1 Modelo simulado (padrão)

```ini
LLM_PROVEDOR=falso
```

Não usa nenhum serviço. Útil para desenvolver e testar sem internet nem créditos.

### 4.2 Qwen 3 local com Ollama

O Ollama roda modelos pequenos usando só a CPU. Depois de instalá-lo, baixe um modelo, por
exemplo:

```bash
ollama pull qwen3:0.6b        # o mais leve
ollama pull qwen3:1.7b        # um pouco maior e melhor
```

No `.env`:

```ini
LLM_PROVEDOR=openai
LLM_BASE_URL=http://127.0.0.1:11434/v1
LLM_API_KEY=
LLM_MODELO=qwen3:0.6b
LLM_EXTRA_BODY={"reasoning_effort": "none"}
```

Use `127.0.0.1` em vez de `localhost`: no Windows, `localhost` pode tentar o IPv6 primeiro e
atrasar cada conexão em cerca de 2 s. A linha `LLM_EXTRA_BODY` desliga o modo de raciocínio
(seção 4.4).

Para alternar entre modelos, troque só `LLM_MODELO` (por exemplo, para `qwen3:1.7b`) e reinicie
a aplicação. O comando `ollama list` mostra os modelos baixados.

Modelos pequenos em CPU servem para **validar o funcionamento**. Com muitos usuários
simultâneos, as respostas ficam lentas, porque a CPU processa as gerações praticamente em fila.

### 4.3 Qwen 3 por um serviço de API

Qualquer serviço compatível com o formato da OpenAI que ofereça Qwen 3 (por exemplo,
DashScope/Alibaba, OpenRouter ou Groq):

```ini
LLM_PROVEDOR=openai
LLM_BASE_URL=<endereço da API do serviço, terminando em /v1>
LLM_API_KEY=<sua chave>
LLM_MODELO=<nome exato do modelo Qwen 3 nesse serviço>
```

### 4.4 Modo de raciocínio do Qwen 3

Alguns modelos Qwen 3 "pensam em voz alta" antes de responder, o que deixa a resposta mais lenta.
O texto desse raciocínio não aparece para o usuário, mas nenhum trecho da resposta chega enquanto
o modelo pensa. Se o provedor permitir desligar esse modo, configure `LLM_EXTRA_BODY` com o
parâmetro dele, em JSON. Por exemplo:

```ini
# Ollama (testado: primeiro trecho em ~0,1 s em vez de ~2 s)
LLM_EXTRA_BODY={"reasoning_effort": "none"}
# DashScope
LLM_EXTRA_BODY={"enable_thinking": false}
# vLLM
LLM_EXTRA_BODY={"chat_template_kwargs": {"enable_thinking": false}}
```

## 5. Rodando os testes

Com o banco no ar (seção 2.1) e o ambiente virtual ativado:

```bash
pytest
```

Os testes usam o banco `chatbot_test`, que é recriado a cada teste, e o modelo simulado. Eles não
tocam nos dados da aplicação nem chamam nenhum serviço externo.

## 6. Configurações

Todas são lidas do `.env` (ou de variáveis de ambiente).

| Variável | Padrão | Descrição |
|---|---|---|
| `DATABASE_URL` | `postgresql+asyncpg://chatbot:chatbot@localhost:5434/chatbot` | Conexão com o PostgreSQL |
| `COOKIE_SECURE` | `true` | Envia o cookie só por HTTPS. Deixe `true` em produção |
| `LLM_PROVEDOR` | `falso` | `falso` (simulado) ou `openai` (formato compatível) |
| `LLM_BASE_URL` | vazio | Endereço do serviço do modelo |
| `LLM_API_KEY` | vazio | Chave de acesso do serviço (o Ollama não precisa) |
| `LLM_MODELO` | `qwen3` | Nome do modelo no serviço |
| `LLM_EXTRA_BODY` | `{}` | Parâmetros extras do provedor, em JSON |
| `LLM_TIMEOUT_SEGUNDOS` | `90` | Tempo máximo de espera pelo modelo |
| `PROMPT_SISTEMA` | assistente em português | Instrução de sistema enviada ao modelo |

## 7. Referência da API

| Endpoint | Descrição |
|---|---|
| `GET /conversa` | Histórico da conversa. Cria a conversa se ainda não existir. |
| `POST /conversa/mensagens` | Envia `{"pergunta": "..."}`. A resposta chega por SSE. |
| `GET /saude` | Verifica se a aplicação está no ar. |

`POST /conversa/mensagens` responde com `text/event-stream`, com os eventos:

| Evento | Conteúdo | Quando |
|---|---|---|
| `trecho` | `{"texto": "..."}` | A cada parte da resposta |
| `fim` | `{"mensagem_id": 123}` | Ao concluir |
| `erro` | `{"detail": "..."}` | Se o modelo falhar |

Respostas de erro:

| Código | Motivo |
|---|---|
| `409` | Ainda há uma resposta em geração nesta conversa. Aguarde e envie de novo. |
| `422` | Pergunta vazia ou com mais de 4000 caracteres. |

### Usando com `curl`

O `curl` precisa guardar o cookie entre as chamadas:

```bash
curl -c cookies.txt -b cookies.txt -N -X POST https://SEU-HOST/conversa/mensagens \
  -H "Content-Type: application/json" -d '{"pergunta": "Olá!"}'

curl -c cookies.txt -b cookies.txt https://SEU-HOST/conversa
```

## 8. Problemas comuns

| Sintoma | Causa e solução |
|---|---|
| `failed to connect to the docker API` | O Docker Desktop está fechado. Abra-o e repita o comando. |
| `port is already allocated` ao subir o banco | Outro programa usa a porta 5434. Troque a porta em `infra/docker-compose.yml` e em `DATABASE_URL`. |
| `address already in use` ao iniciar a aplicação | Outro programa usa a porta 8001. Use outra: `uvicorn app.main:app --port 8002`. |
| PowerShell não deixa ativar o `.venv` | Rode uma vez: `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`. |
| Com `curl` local, cada chamada cria uma conversa nova | O `curl` não guarda cookie `Secure` vindo de `http://`. Para testes locais com `curl`, use `COOKIE_SECURE=false` no `.env`. O navegador e o Swagger não têm esse problema. |
| Respostas lentas com o Ollama | É esperado com modelos em CPU. Use um modelo menor (`qwen3:0.6b`) ou um serviço de API. |
