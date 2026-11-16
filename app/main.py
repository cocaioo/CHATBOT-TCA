import asyncio
import logging
from contextlib import asynccontextmanager, suppress
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .db import engine
from .llm import criar_llm
from .monitoramento import coletar_metricas, laco_instancia, laco_metricas
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
    app.state.metricas = coletar_metricas(cpu_inicial=True)
    metricas = asyncio.create_task(laco_metricas(app))
    instancia = asyncio.create_task(laco_instancia(app))
    yield
    limpeza.cancel()
    metricas.cancel()
    instancia.cancel()
    for tarefa in (limpeza, metricas, instancia):
        with suppress(asyncio.CancelledError):
            await tarefa
    await engine.dispose()


app = FastAPI(title="Chatbot TCA", description=DESCRICAO, version="0.1.0", lifespan=lifespan)
app.include_router(router)


@app.get("/saude", tags=["Infraestrutura"], summary="Verificar se a aplicação está no ar")
async def saude():
    return {"status": "ok"}


@app.get("/api/metricas", tags=["Infraestrutura"], summary="Consultar métricas da instância")
async def metricas():
    from fastapi.responses import JSONResponse

    return JSONResponse(getattr(app.state, "metricas", {}), headers={"Cache-Control": "no-store"})


@app.get("/api/instancia", tags=["Infraestrutura"], summary="Consultar informações públicas da instância")
async def informacoes_instancia():
    from fastapi.responses import JSONResponse

    return JSONResponse(getattr(app.state, "instancia", {}), headers={"Cache-Control": "no-store"})


_STATIC_DIR = Path(__file__).parent / "static"


@app.get("/", include_in_schema=False)
async def frontend():
    return FileResponse(_STATIC_DIR / "index.html", media_type="text/html")


@app.get("/monitoramento", include_in_schema=False)
async def monitoramento():
    return FileResponse(_STATIC_DIR / "monitoramento.html", media_type="text/html")


app.mount("/static", StaticFiles(directory=_STATIC_DIR), name="static")
