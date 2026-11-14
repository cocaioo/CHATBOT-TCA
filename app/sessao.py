"""Identificação do cliente por cookie de sessão (seção 2 dos requisitos)."""

import uuid
from datetime import timedelta

from fastapi import Request, Response
from sqlalchemy import func, or_, update
from sqlalchemy.ext.asyncio import AsyncSession

from .config import config
from .db import SessionLocal
from .models import Conversa


async def obter_conversa(request: Request, db: AsyncSession) -> uuid.UUID:
    """Devolve a conversa do cookie, ou cria uma nova se o cookie faltar,
    for inválido, não existir no banco ou estiver expirado (decisão 7)."""
    bruto = request.cookies.get(config.cookie_nome)
    if bruto:
        try:
            conversa_id = uuid.UUID(bruto)
        except ValueError:
            conversa_id = None
        if conversa_id is not None:
            limite = func.now() - timedelta(seconds=config.retencao_segundos)
            resultado = await db.execute(
                update(Conversa)
                .where(Conversa.id == conversa_id, Conversa.ultima_atividade >= limite)
                .values(ultima_atividade=func.now())
                .returning(Conversa.id)
            )
            if resultado.scalar_one_or_none() is not None:
                await db.commit()
                return conversa_id
            await db.rollback()

    conversa = Conversa()
    db.add(conversa)
    await db.commit()
    return conversa.id


def definir_cookie(response: Response, conversa_id: uuid.UUID) -> None:
    """Emite ou renova o cookie (decisão 4): validade de 1 hora a cada requisição."""
    response.set_cookie(
        key=config.cookie_nome,
        value=str(conversa_id),
        max_age=config.retencao_segundos,
        httponly=True,
        secure=config.cookie_secure,
        samesite="lax",
    )


async def adquirir_bloqueio(db: AsyncSession, conversa_id: uuid.UUID) -> bool:
    """Marca a conversa como "em geração" de forma atômica.
    Devolve False se já houver uma resposta em geração (HTTP 409)."""
    expira = func.now() - timedelta(seconds=config.bloqueio_expira_segundos)
    resultado = await db.execute(
        update(Conversa)
        .where(
            Conversa.id == conversa_id,
            or_(Conversa.em_geracao_desde.is_(None), Conversa.em_geracao_desde < expira),
        )
        .values(em_geracao_desde=func.now(), ultima_atividade=func.now())
        .returning(Conversa.id)
    )
    adquirido = resultado.scalar_one_or_none() is not None
    await db.commit()
    return adquirido


async def liberar_bloqueio(conversa_id: uuid.UUID) -> None:
    async with SessionLocal() as db:
        await db.execute(
            update(Conversa).where(Conversa.id == conversa_id).values(em_geracao_desde=None)
        )
        await db.commit()
