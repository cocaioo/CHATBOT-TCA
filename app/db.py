from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from .config import config

engine = create_async_engine(config.database_url, pool_size=20, max_overflow=20)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def obter_db() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as sessao:
        yield sessao
