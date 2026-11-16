import asyncio
import json
import logging
import uuid
from collections.abc import AsyncIterator
from datetime import datetime
from typing import Annotated

import anyio
from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, ConfigDict, StringConstraints
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .db import SessionLocal, obter_db
from .llm import ClienteLLM
from .models import Conversa, Mensagem
from .resumo import atualizar_resumo_se_necessario, montar_contexto
from .sessao import (
    adquirir_bloqueio, criar_nova_conversa, definir_cookie, liberar_bloqueio, obter_conversa,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/conversa", tags=["Conversa"])

MSG_409 = "Já existe uma resposta em geração nesta conversa. Aguarde a conclusão e envie novamente."
MSG_ERRO_LLM = "Não foi possível gerar a resposta. Tente novamente."


class MensagemSaida(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    papel: str
    conteudo: str
    criada_em: datetime


class HistoricoSaida(BaseModel):
    id_sessao: uuid.UUID
    mensagens: list[MensagemSaida]


class PerguntaEntrada(BaseModel):
    pergunta: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=4000)]


def _evento(nome: str, dados: dict) -> str:
    return f"event: {nome}\ndata: {json.dumps(dados, ensure_ascii=False)}\n\n"


@router.get("", response_model=HistoricoSaida, summary="Consultar o histórico da conversa")
async def historico(request: Request, response: Response, db: AsyncSession = Depends(obter_db)):
    """Devolve o histórico da conversa do cookie de sessão.
    Sem cookie válido, cria uma nova conversa (histórico vazio) e emite o cookie."""
    conversa_id = await obter_conversa(request, db)
    definir_cookie(response, conversa_id)
    resultado = await db.execute(
        select(Mensagem).where(Mensagem.conversa_id == conversa_id).order_by(Mensagem.id)
    )
    return {"id_sessao": conversa_id, "mensagens": list(resultado.scalars())}


@router.post("/nova", response_model=HistoricoSaida, summary="Iniciar uma nova conversa")
async def nova_conversa(request: Request, response: Response, db: AsyncSession = Depends(obter_db)):
    """Preserva a conversa anterior e interrompe qualquer resposta em geração."""
    conversa_id = await criar_nova_conversa(request, db)
    definir_cookie(response, conversa_id)
    return {"id_sessao": conversa_id, "mensagens": []}


@router.post(
    "/mensagens",
    summary="Enviar uma pergunta (resposta por SSE)",
    response_class=StreamingResponse,
    responses={
        200: {
            "description": (
                "Stream SSE. Eventos: `trecho` ({\"texto\"}) a cada parte da resposta; "
                "`fim` ({\"mensagem_id\"}) ao concluir; `interrompido` ({}) ao criar nova conversa; `erro` ({\"detail\"}) em caso de falha."
            ),
            "content": {"text/event-stream": {}},
        },
        409: {"description": MSG_409},
    },
)
async def perguntar(
    entrada: PerguntaEntrada, request: Request, db: AsyncSession = Depends(obter_db)
):
    conversa_id = await obter_conversa(request, db)

    geracao_id = await adquirir_bloqueio(db, conversa_id)
    if not geracao_id:
        resposta = JSONResponse(status_code=409, content={"detail": MSG_409})
        definir_cookie(resposta, conversa_id)
        return resposta

    try:
        db.add(Mensagem(conversa_id=conversa_id, papel="usuario", conteudo=entrada.pergunta))
        await db.commit()
    except BaseException:
        with anyio.CancelScope(shield=True):
            await liberar_bloqueio(conversa_id, geracao_id)
        raise

    llm: ClienteLLM = request.app.state.llm
    resposta = StreamingResponse(
        _gerar_eventos(llm, conversa_id, geracao_id),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
    definir_cookie(resposta, conversa_id)
    return resposta


async def _aguardar_cancelamento(conversa_id: uuid.UUID, geracao_id: uuid.UUID) -> None:
    while True:
        async with SessionLocal() as db:
            atual = await db.scalar(select(Conversa.geracao_id).where(Conversa.id == conversa_id))
        if atual != geracao_id:
            return
        await asyncio.sleep(0.25)


async def _gerar_eventos(
    llm: ClienteLLM, conversa_id: uuid.UUID, geracao_id: uuid.UUID
) -> AsyncIterator[str]:
    monitor = asyncio.create_task(_aguardar_cancelamento(conversa_id, geracao_id))
    fluxo = None
    proximo = None
    try:
        partes: list[str] = []
        try:
            async with SessionLocal() as db:
                contexto = await montar_contexto(db, conversa_id)
            fluxo = llm.gerar_stream(contexto)
            while True:
                proximo = asyncio.create_task(anext(fluxo))
                concluidos, _ = await asyncio.wait((proximo, monitor), return_when=asyncio.FIRST_COMPLETED)
                if monitor in concluidos:
                    await monitor  # Propaga erros de acesso ao banco.
                    proximo.cancel()
                    await asyncio.gather(proximo, return_exceptions=True)
                    yield _evento("interrompido", {})
                    return
                try:
                    trecho = proximo.result()
                except StopAsyncIteration:
                    break
                partes.append(trecho)
                yield _evento("trecho", {"texto": trecho})
        except Exception:
            logger.exception("Falha ao gerar resposta")
            yield _evento("erro", {"detail": MSG_ERRO_LLM})
            return

        # A linha bloqueada serializa a conclusão com o cancelamento da geração.
        async with SessionLocal() as db:
            conversa = await db.scalar(select(Conversa).where(Conversa.id == conversa_id).with_for_update())
            if conversa is None or conversa.geracao_id != geracao_id:
                yield _evento("interrompido", {})
                return
            mensagem = Mensagem(conversa_id=conversa_id, papel="assistente", conteudo="".join(partes))
            db.add(mensagem)
            await db.commit()
        yield _evento("fim", {"mensagem_id": mensagem.id})
        await atualizar_resumo_se_necessario(llm, conversa_id)
    finally:
        with anyio.CancelScope(shield=True):
            monitor.cancel()
            if proximo and not proximo.done():
                proximo.cancel()
            await asyncio.gather(monitor, *([proximo] if proximo else []), return_exceptions=True)
            try:
                if fluxo is not None:
                    await fluxo.aclose()
            finally:
                await liberar_bloqueio(conversa_id, geracao_id)
