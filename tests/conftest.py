import os

# Antes de importar a aplicação: banco de teste e modelo simulado.
os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+asyncpg://chatbot:chatbot@localhost:5434/chatbot_test"
)
os.environ["LLM_PROVEDOR"] = "falso"

import httpx  # noqa: E402
import pytest  # noqa: E402

from app.db import engine  # noqa: E402
from app.llm import LLMFalso  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Base  # noqa: E402


@pytest.fixture
async def banco():
    async with engine.begin() as conexao:
        await conexao.run_sync(Base.metadata.drop_all)
        await conexao.run_sync(Base.metadata.create_all)
    yield
    # Cada teste roda em um event loop próprio; descarta conexões do loop anterior.
    await engine.dispose()


@pytest.fixture
def llm():
    falso = LLMFalso(atraso=0)
    app.state.llm = falso
    return falso


@pytest.fixture
async def novo_cliente(banco, llm):
    """Fábrica de clientes HTTP; cada um tem seu próprio pote de cookies (= um usuário)."""
    clientes: list[httpx.AsyncClient] = []

    def fabricar() -> httpx.AsyncClient:
        cliente = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="https://teste")
        clientes.append(cliente)
        return cliente

    yield fabricar
    for cliente in clientes:
        await cliente.aclose()


@pytest.fixture
async def cliente(novo_cliente):
    return novo_cliente()
