# Chatbot TCA

Chatbot multiusuário com histórico persistente por conversa, feito em Python (FastAPI +
PostgreSQL) e usando o modelo **Gemini 3.1 Flash-Lite**, do Google. A interface é a própria API, usada pela
documentação **Swagger**. O enunciado está em `docs/requisitos.md`, e os requisitos e decisões
do projeto em `docs/elicitação dos requisitos.md`. Arquivos de infraestrutura (banco local e
implantação no EC2) ficam em `infra/`.

## Acesso público

A aplicação está publicada no AWS EC2. O uso é o mesmo descrito neste README, trocando
`http://localhost:8001` pelo endereço público:

| O quê | Endereço |
|---|---|
| Documentação interativa (Swagger) | https://13.58.162.232/docs |
| Verificação de funcionamento | https://13.58.162.232/saude |

O acesso público exige HTTPS, porque o cookie de sessão só trafega por conexões seguras. O
certificado é emitido pela Let's Encrypt para o endereço IP da instância.

Como o servidor está montado e como mantê-lo: [seção 9](#9-servidor-aws-ec2).

## Por que Gemini 3.1 Flash-Lite

| Característica | Por que importa neste projeto |
|---|---|
| Executado como serviço pelo Google | O servidor da aplicação não precisa de GPU nem de memória para o modelo: uma instância EC2 pequena basta. |
| Menor custo da linha Flash | O crédito pré-pago é de só R$ 30; o 2.5 Flash, escolhido antes, foi bloqueado pelo Google para novos usuários. |
| Linha "Flash": foco em baixa latência | Respostas rápidas, compatíveis com as metas de tempo até o primeiro trecho (TTFT). |
| Escala com vários usuários | O processamento acontece na infraestrutura do Google, não numa CPU compartilhada. |
| Qualidade superior a modelos pequenos locais | Na avaliação, o Qwen 3 local (0.6B e 1.7B) errou fatos simples; a qualidade das respostas é critério de avaliação. |
| Multilíngue, incluindo português | Idioma das perguntas e respostas. |
| Raciocínio ajustável (*thinking budget*) | Desligado por padrão, para o primeiro trecho chegar mais cedo. |
| SDK oficial em Python (`google-genai`) | Streaming assíncrono, integrado ao FastAPI. |
| Citado no enunciado | O enunciado lista o Google Gemini como opção de modelo. |

Justificativas completas e histórico da escolha: `docs/elicitação dos requisitos.md`, seção 9,
decisão 8.

## Sumário

1. [Pré-requisitos](#1-pré-requisitos)
2. [Rodando localmente](#2-rodando-localmente)
3. [Usando a API pelo Swagger](#3-usando-a-api-pelo-swagger)
4. [Configurando o modelo](#4-configurando-o-modelo)
5. [Rodando os testes](#5-rodando-os-testes)
6. [Configurações](#6-configurações)
7. [Referência da API](#7-referência-da-api)
8. [Problemas comuns](#8-problemas-comuns)
9. [Servidor (AWS EC2)](#9-servidor-aws-ec2)

## 1. Pré-requisitos

| Ferramenta | Para quê | Obrigatório? |
|---|---|---|
| Python 3.12 ou superior | Rodar a aplicação | Sim |
| Docker Desktop (ou Docker no Linux) | Rodar o PostgreSQL | Sim |
| Git | Baixar o projeto | Sim |
| Chave de API do Gemini | Acessar o modelo | Sim, para usar a aplicação; os testes automatizados não precisam |

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

Depois, abra o `.env` e preencha `GEMINI_API_KEY` com sua chave (veja a
[seção 4](#4-configurando-o-modelo)).

O `.env` não é versionado: nunca coloque a chave em outro arquivo, nem a compartilhe no GitHub.

### 2.4 Iniciar a aplicação

```bash
uvicorn app.main:app --port 8001
```

Abra **http://localhost:8001/** para conversar pela interface web ou
**http://localhost:8001/docs** para acessar o Swagger. Para parar, use `Ctrl+C`.

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

Para começar outra conversa, execute **`POST /conversa/nova`** no Swagger. A resposta
contém um histórico vazio e substitui o cookie de sessão. O histórico anterior permanece
no banco até a limpeza após uma hora de inatividade, mas não pode mais ser consultado
com o novo cookie. Uma resposta em andamento é interrompida: o stream anterior recebe
o evento SSE `interrompido`, quando ainda estiver conectado; a pergunta permanece no
histórico anterior e a resposta parcial não é salva. O provedor ainda pode contabilizar
parte da chamada interrompida.

Se o banco já existia antes desta funcionalidade, pare a aplicação e execute uma vez a
migração abaixo em cada banco existente, inclusive o de testes se utilizado:

```powershell
Get-Content -Raw infra/migracao-geracao-id.sql | docker exec -i chatbot-tca-db-1 psql -U chatbot -d chatbot
Get-Content -Raw infra/migracao-geracao-id.sql | docker exec -i chatbot-tca-db-1 psql -U chatbot -d chatbot_test
```

Em outro ambiente PostgreSQL, execute `infra/migracao-geracao-id.sql` com `psql` apontando
para o banco correspondente. Bancos novos recebem a coluna automaticamente na criação.

## 4. Configurando o modelo

A aplicação usa o **Gemini 3.1 Flash-Lite** pelo SDK oficial do Google (`google-genai`).

### 4.1 Gerar a chave

1. Acesse o **Google AI Studio** (https://aistudio.google.com/apikey) com uma conta Google.
2. Crie uma chave de API.
3. Cole-a no `.env`:

```ini
LLM_PROVEDOR=gemini
GEMINI_API_KEY=<sua chave, sem aspas>
LLM_MODELO=gemini-3.1-flash-lite
```

4. Reinicie a aplicação.

A chave dá acesso à sua cota no Google: não a coloque em nenhum arquivo versionado, nem a envie
por mensagens.

### 4.2 Limites de uso

O plano gratuito da API do Gemini tem limites de requisições por minuto e por dia. Em 14/11/2026,
o limite verificado para o `gemini-2.5-flash` foi de **5 requisições por minuto**. Cada pergunta
usa uma requisição, e a atualização periódica do resumo da conversa, outra. Ao ultrapassar o
limite, a API recusa novas chamadas por alguns segundos (erro 429), e a aplicação responde com o
evento `erro`. Consulte os limites atuais da sua conta no Google AI Studio, principalmente antes
de demonstrações ou testes com vários usuários.

No projeto da equipe, o faturamento **pré-pago** está ativado (créditos de R$ 30, sem recarga
automática), o que remove o limite de 5 por minuto. Quando o crédito acabar, a API para de
responder e a aplicação passa a devolver o evento `erro`, sem cobrança adicional.

### 4.3 Raciocínio do modelo

O Gemini pode "pensar" antes de responder, o que atrasa o primeiro trecho da resposta.
Por padrão a aplicação desliga esse modo (`LLM_ORCAMENTO_RACIOCINIO=0`). Para deixar o modelo
decidir quanto pensar, use `-1`.

### 4.4 Modelo simulado (testes)

```ini
LLM_PROVEDOR=falso
```

Não chama nenhum serviço: apenas repete a pergunta. É o que os testes automatizados usam, para
rodar sem chave nem internet.

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
| `LLM_PROVEDOR` | `gemini` | `gemini` ou `falso` (simulado, usado nos testes) |
| `GEMINI_API_KEY` | vazio | Chave da API do Gemini (obrigatória com `gemini`) |
| `LLM_MODELO` | `gemini-3.1-flash-lite` | Nome do modelo |
| `LLM_ORCAMENTO_RACIOCINIO` | `0` | Tokens de raciocínio: `0` desliga, `-1` automático |
| `LLM_TIMEOUT_SEGUNDOS` | `90` | Tempo máximo de espera pelo modelo |
| `PROMPT_SISTEMA` | assistente em português | Instrução de sistema enviada ao modelo |

## 7. Referência da API

| Endpoint | Descrição |
|---|---|
| `GET /conversa` | Histórico da conversa. Cria a conversa se ainda não existir. |
| `POST /conversa/mensagens` | Envia `{"pergunta": "..."}`. A resposta chega por SSE. |
| `POST /conversa/nova` | Começa outra conversa (troca o cookie) e interrompe a resposta em andamento. |
| `GET /saude` | Verifica se a aplicação está no ar. |

`POST /conversa/mensagens` responde com `text/event-stream`, com os eventos:

| Evento | Conteúdo | Quando |
|---|---|---|
| `trecho` | `{"texto": "..."}` | A cada parte da resposta |
| `fim` | `{"mensagem_id": 123}` | Ao concluir |
| `erro` | `{"detail": "..."}` | Se o modelo falhar |
| `interrompido` | `{}` | Se `POST /conversa/nova` for chamado durante a resposta |

Respostas de erro:

| Código | Motivo |
|---|---|
| `409` | Ainda há uma resposta em geração nesta conversa. Aguarde e envie de novo. |
| `422` | Pergunta vazia ou com mais de 4000 caracteres. |

### Usando com `curl`

O `curl` precisa guardar o cookie entre as chamadas:

```bash
curl -c cookies.txt -b cookies.txt -N -X POST https://13.58.162.232/conversa/mensagens \
  -H "Content-Type: application/json" -d '{"pergunta": "Olá!"}'

curl -c cookies.txt -b cookies.txt https://13.58.162.232/conversa
```

## 8. Problemas comuns

| Sintoma | Causa e solução |
|---|---|
| `failed to connect to the docker API` | O Docker Desktop está fechado. Abra-o e repita o comando. |
| `port is already allocated` ao subir o banco | Outro programa usa a porta 5434. Troque a porta em `infra/docker-compose.yml` e em `DATABASE_URL`. |
| `address already in use` ao iniciar a aplicação | Outro programa usa a porta 8001. Use outra: `uvicorn app.main:app --port 8002`. |
| PowerShell não deixa ativar o `.venv` | Rode uma vez: `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`. |
| Com `curl` local, cada chamada cria uma conversa nova | O `curl` não guarda cookie `Secure` vindo de `http://`. Para testes locais com `curl`, use `COOKIE_SECURE=false` no `.env`. O navegador e o Swagger não têm esse problema. |
| A aplicação não inicia: `GEMINI_API_KEY não configurada` | Preencha a chave no `.env` (seção 4.1). |
| Toda pergunta recebe o evento `erro` | Chave inválida, sem internet ou limite de uso atingido (seção 4.2). O terminal da aplicação mostra o erro detalhado. |

## 9. Servidor (AWS EC2)

A instância é uma `t3.micro` com Ubuntu 26.04 (908 MB de RAM e 1 GB de swap). Tudo roda direto
nela, sem Docker:

| Componente | Detalhes |
|---|---|
| nginx | Portas 80 (redireciona para HTTPS) e 443, com certificado da Let's Encrypt. Repassa as requisições para a aplicação |
| Aplicação | `/home/ubuntu/CHATBOT-TCA`, branch `dev`, serviço `chatbot` do systemd em `127.0.0.1:8000`. Reinicia sozinha se cair e sobe junto com a instância |
| Banco | PostgreSQL 18, acessível só de dentro da instância |
| Configuração | `.env` na pasta da aplicação, com a senha do banco e a chave do Gemini |

O certificado do IP tem validade de seis dias. O timer `snap.certbot.renew.timer` executa a
renovação automática e o Certbot recarrega o nginx após renová-lo. Para verificar a renovação,
execute `sudo /snap/bin/certbot renew --dry-run --cert-name chatbot-ip --run-deploy-hooks --no-random-sleep-on-renew`.
A conta do Certbot foi criada sem e-mail; não há avisos por e-mail
se a renovação falhar. Se o IP público mudar, será necessário emitir outro certificado para ele.

### Acesso SSH

A porta 22 só aceita IPs liberados no *security group* da instância. Informe seu IP público
(https://checkip.amazonaws.com) a quem administra a conta da AWS e peça uma regra de entrada
**SSH, TCP 22, origem `<seu IP>/32`**. Se o SSH passar a expirar, confira se o seu IP mudou.

A chave `chatbot-key.pem` não é versionada: peça-a à equipe e guarde-a em `infra/`.

```bash
ssh -i infra/chatbot-key.pem ubuntu@13.58.162.232
```

### Publicar uma nova versão

Depois do merge na `dev`, dentro da instância:

```bash
cd ~/CHATBOT-TCA
git pull --ff-only origin dev
venv/bin/pip install -r requirements.txt   # só se requirements.txt mudou
sudo systemctl restart chatbot
```

Tabelas novas são criadas na inicialização, mas colunas novas em tabelas existentes não: se a
versão trouxer um `infra/migracao-*.sql`, rode-o antes de reiniciar, com
`sudo -u postgres psql -d chatbot -f infra/migracao-<nome>.sql`.

### Logs

O erro 500 público mostra só `Internal Server Error`; a causa fica no log do serviço:

```bash
sudo journalctl -u chatbot -n 100 --no-pager   # últimas linhas
sudo journalctl -u chatbot -f                  # em tempo real
```

Para mudar uma configuração (seção 6), edite o `.env` e rode `sudo systemctl restart chatbot`.

> Use sempre o PostgreSQL. O primeiro deploy usou SQLite, e todo envio de pergunta falhava com
> HTTP 500: no SQLite, a chave `BIGINT` da tabela `mensagens` não é gerada automaticamente.
