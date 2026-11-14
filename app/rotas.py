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
from .models import Mensagem
from .resumo import atualizar_resumo_se_necessario, montar_contexto
from .sessao import adquirir_bloqueio, definir_cookie, liberar_bloqueio, obter_conversa

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
    return {"mensagens": list(resultado.scalars())}


@router.post(
    "/mensagens",
    summary="Enviar uma pergunta (resposta por SSE)",
    response_class=StreamingResponse,
    responses={
        200: {
            "description": (
                "Stream SSE. Eventos: `trecho` ({\"texto\"}) a cada parte da resposta; "
                "`fim` ({\"mensagem_id\"}) ao concluir; `erro` ({\"detail\"}) em caso de falha."
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

    if not await adquirir_bloqueio(db, conversa_id):
        resposta = JSONResponse(status_code=409, content={"detail": MSG_409})
        definir_cookie(resposta, conversa_id)
        return resposta

    try:
        db.add(Mensagem(conversa_id=conversa_id, papel="usuario", conteudo=entrada.pergunta))
        await db.commit()
    except BaseException:
        with anyio.CancelScope(shield=True):
            await liberar_bloqueio(conversa_id)
        raise

    llm: ClienteLLM = request.app.state.llm
    resposta = StreamingResponse(
        _gerar_eventos(llm, conversa_id),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
    definir_cookie(resposta, conversa_id)
    return resposta


async def _gerar_eventos(llm: ClienteLLM, conversa_id: uuid.UUID) -> AsyncIterator[str]:
    try:
        partes: list[str] = []
        try:
            async with SessionLocal() as db:
                contexto = await montar_contexto(db, conversa_id)
            async for trecho in llm.gerar_stream(contexto):
                partes.append(trecho)
                yield _evento("trecho", {"texto": trecho})
        except Exception:
            # Tratamento detalhado de falhas está em aberto (seção 9.2, item 1).
            # A resposta parcial não é salva: falha não vira resposta do modelo (invariante 6).
            logger.exception("Falha ao gerar resposta")
            yield _evento("erro", {"detail": MSG_ERRO_LLM})
            return

        async with SessionLocal() as db:
            mensagem = Mensagem(conversa_id=conversa_id, papel="assistente", conteudo="".join(partes))
            db.add(mensagem)
            await db.commit()
        yield _evento("fim", {"mensagem_id": mensagem.id})

        # Depois da resposta (não afeta o TTFT) e ainda sob o bloqueio (decisão 9).
        await atualizar_resumo_se_necessario(llm, conversa_id)
    finally:
        # Protegido contra cancelamento: se o cliente desconectar, o bloqueio ainda é liberado.
        with anyio.CancelScope(shield=True):
            await liberar_bloqueio(conversa_id)
