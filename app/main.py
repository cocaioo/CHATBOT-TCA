import asyncio
import logging
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI

from .db import engine
from .llm import criar_llm
from .models import Base
from .retencao import laco_limpeza
from .rotas import router

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

DESCRICAO = """
Chatbot multiusuário com histórico persistente por conversa.

**Sessão:** cada cliente tem uma única conversa, identificada por um cookie de sessão
(`HttpOnly`, válido por 1 hora sem atividade). Pelo Swagger, o navegador guarda e envia o
cookie automaticamente: basta usar os endpoints abaixo. Com `curl`, mantenha os cookies entre
chamadas (`curl -c cookies.txt -b cookies.txt ...`).

**Nova conversa:** `POST /conversa/nova` troca o cookie e interrompe a geração anterior.
O histórico anterior permanece no banco até expirar.

**Perguntas:** `POST /conversa/mensagens` responde por SSE (`text/event-stream`). O Swagger mostra
a resposta completa ao final; clientes de stream a recebem em partes. Enquanto uma resposta está
sendo gerada, outra pergunta na mesma conversa recebe HTTP 409.
"""


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conexao:
        await conexao.run_sync(Base.metadata.create_all)
    app.state.llm = criar_llm()
    limpeza = asyncio.create_task(laco_limpeza())
    yield
    limpeza.cancel()
    with suppress(asyncio.CancelledError):
        await limpeza
    await engine.dispose()


app = FastAPI(title="Chatbot TCA", description=DESCRICAO, version="0.1.0", lifespan=lifespan)
app.include_router(router)


@app.get("/saude", tags=["Infraestrutura"], summary="Verificar se a aplicação está no ar")
async def saude():
    return {"status": "ok"}
