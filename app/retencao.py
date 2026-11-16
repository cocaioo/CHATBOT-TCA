"""Remoção de conversas com 1 hora sem atividade (seção 9, decisão 5)."""

import asyncio
import logging
from datetime import timedelta

from sqlalchemy import delete, func
from sqlalchemy.ext.asyncio import AsyncSession

from .config import config
from .db import SessionLocal
from .models import Conversa

logger = logging.getLogger(__name__)


async def remover_inativas(db: AsyncSession) -> int:
    """Apaga conversas inativas; as mensagens saem junto (ON DELETE CASCADE)."""
    limite = func.now() - timedelta(seconds=config.retencao_segundos)
    resultado = await db.execute(delete(Conversa).where(Conversa.ultima_atividade < limite))
    await db.commit()
    return resultado.rowcount or 0


async def laco_limpeza() -> None:
    while True:
        try:
            async with SessionLocal() as db:
                removidas = await remover_inativas(db)
            if removidas:
                logger.info("Conversas inativas removidas: %d", removidas)
        except Exception:
            logger.exception("Falha na limpeza de conversas inativas")
        await asyncio.sleep(config.intervalo_limpeza_segundos)
