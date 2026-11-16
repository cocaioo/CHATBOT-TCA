"""Contexto do modelo: mensagens recentes + resumo das antigas (seção 7)."""

import logging
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .config import config
from .db import SessionLocal
from .llm import ClienteLLM, Mensagens
from .models import Conversa, Mensagem

logger = logging.getLogger(__name__)

PAPEL_LLM = {"usuario": "user", "assistente": "assistant"}
ROTULO = {"usuario": "Usuário", "assistente": "Assistente"}


async def _nao_resumidas(db: AsyncSession, conversa: Conversa) -> list[Mensagem]:
    resultado = await db.execute(
        select(Mensagem)
        .where(Mensagem.conversa_id == conversa.id, Mensagem.id > conversa.resumo_ate_id)
        .order_by(Mensagem.id)
    )
    return list(resultado.scalars())


async def montar_contexto(db: AsyncSession, conversa_id: uuid.UUID) -> Mensagens:
    """Prompt de sistema (com o resumo, se houver) + todas as mensagens ainda não resumidas."""
    conversa = await db.get(Conversa, conversa_id)
    if conversa is None:
        raise LookupError("conversa inexistente")

    sistema = config.prompt_sistema
    if conversa.resumo:
        sistema += f"\n\nResumo da conversa até aqui:\n{conversa.resumo}"

    contexto: Mensagens = [{"role": "system", "content": sistema}]
    for m in await _nao_resumidas(db, conversa):
        contexto.append({"role": PAPEL_LLM[m.papel], "content": m.conteudo})
    return contexto


async def atualizar_resumo_se_necessario(llm: ClienteLLM, conversa_id: uuid.UUID) -> None:
    """Resume em lote as mensagens fora da janela das recentes (decisão 9).
    Falhas são registradas e não interrompem a conversa: o resumo é refeito depois."""
    try:
        async with SessionLocal() as db:
            conversa = await db.get(Conversa, conversa_id)
            if conversa is None:
                return
            mensagens = await _nao_resumidas(db, conversa)
            antigas = mensagens[: -config.mensagens_recentes] if config.mensagens_recentes else mensagens
            if len(antigas) < config.lote_resumo:
                return

            transcricao = "\n".join(f"{ROTULO[m.papel]}: {m.conteudo}" for m in antigas)
            prompt: Mensagens = [
                {
                    "role": "system",
                    "content": (
                        "Você resume conversas. Produza um resumo curto, em português, que "
                        "preserve fatos, nomes, números e preferências informados pelo usuário."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"Resumo atual:\n{conversa.resumo or '(vazio)'}\n\n"
                        f"Novas mensagens:\n{transcricao}\n\n"
                        "Escreva o resumo atualizado, incorporando as novas mensagens."
                    ),
                },
            ]
            novo = (await llm.gerar(prompt)).strip()
            if not novo:
                return
            conversa.resumo = novo
            conversa.resumo_ate_id = antigas[-1].id
            await db.commit()
    except Exception:
        logger.exception("Falha ao atualizar o resumo")
