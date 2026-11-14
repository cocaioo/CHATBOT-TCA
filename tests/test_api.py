import json
import uuid
from datetime import timedelta

from sqlalchemy import func, select, update

from app.config import config
from app.db import SessionLocal
from app.models import Conversa, Mensagem
from app.retencao import remover_inativas

COOKIE = config.cookie_nome


def eventos(texto: str) -> list[tuple[str, dict]]:
    saida = []
    for bloco in texto.strip().split("\n\n"):
        linhas = dict(linha.split(": ", 1) for linha in bloco.splitlines())
        saida.append((linhas["event"], json.loads(linhas["data"])))
    return saida


async def perguntar(cliente, texto: str):
    return await cliente.post("/conversa/mensagens", json={"pergunta": texto})


async def definir(conversa_id: str, **valores):
    async with SessionLocal() as db:
        await db.execute(update(Conversa).where(Conversa.id == uuid.UUID(conversa_id)).values(**valores))
        await db.commit()


async def obter(conversa_id: str) -> Conversa | None:
    async with SessionLocal() as db:
        return await db.get(Conversa, uuid.UUID(conversa_id))


# --- Sessão por cookie (seção 2) ---


async def test_primeira_requisicao_cria_conversa_e_cookie(cliente):
    r = await cliente.get("/conversa")
    assert r.status_code == 200
    assert r.json() == {"mensagens": []}
    set_cookie = r.headers["set-cookie"].lower()
    for atributo in ("httponly", "secure", "samesite=lax", "max-age=3600"):
        assert atributo in set_cookie
    assert uuid.UUID(cliente.cookies[COOKIE]).version == 4


async def test_cookie_mantem_a_mesma_conversa(cliente):
    await cliente.get("/conversa")
    original = cliente.cookies[COOKIE]

    r = await perguntar(cliente, "Qual a capital da França?")
    assert r.status_code == 200
    tipos = [nome for nome, _ in eventos(r.text)]
    assert tipos[-1] == "fim" and "trecho" in tipos

    historico = (await cliente.get("/conversa")).json()["mensagens"]
    assert [m["papel"] for m in historico] == ["usuario", "assistente"]
    assert historico[0]["conteudo"] == "Qual a capital da França?"
    assert cliente.cookies[COOKIE] == original


async def test_id_nao_aparece_no_corpo_das_respostas(cliente):
    await perguntar(cliente, "oi")
    conversa_id = cliente.cookies[COOKIE]
    r = await cliente.get("/conversa")
    assert conversa_id not in r.text


async def test_cookie_invalido_cria_nova_conversa(cliente):
    cliente.cookies.set(COOKIE, "nao-e-um-uuid", domain="teste.local")
    r = await cliente.get("/conversa")
    assert r.status_code == 200
    assert uuid.UUID(cliente.cookies[COOKIE])


async def test_id_inexistente_cria_nova_conversa(cliente):
    inexistente = str(uuid.uuid4())
    cliente.cookies.set(COOKIE, inexistente, domain="teste.local")
    r = await perguntar(cliente, "oi")
    assert r.status_code == 200
    assert cliente.cookies[COOKIE] != inexistente
    assert await obter(inexistente) is None


async def test_conversas_isoladas(novo_cliente):
    a, b = novo_cliente(), novo_cliente()
    await perguntar(a, "Meu nome é Ana")
    await perguntar(b, "Meu nome é Bruno")

    hist_a = (await a.get("/conversa")).json()["mensagens"]
    hist_b = (await b.get("/conversa")).json()["mensagens"]
    assert a.cookies[COOKIE] != b.cookies[COOKIE]
    assert hist_a[0]["conteudo"] == "Meu nome é Ana" and len(hist_a) == 2
    assert hist_b[0]["conteudo"] == "Meu nome é Bruno" and len(hist_b) == 2


# --- Bloqueio de perguntas simultâneas (decisão 1) ---


async def test_pergunta_durante_geracao_recebe_409(cliente):
    await cliente.get("/conversa")
    conversa_id = cliente.cookies[COOKIE]
    await definir(conversa_id, em_geracao_desde=func.now())

    r = await perguntar(cliente, "segunda pergunta")
    assert r.status_code == 409
    assert (await cliente.get("/conversa")).json()["mensagens"] == []


async def test_bloqueio_abandonado_e_ignorado(cliente):
    await cliente.get("/conversa")
    conversa_id = cliente.cookies[COOKIE]
    await definir(conversa_id, em_geracao_desde=func.now() - timedelta(minutes=3))

    r = await perguntar(cliente, "oi")
    assert r.status_code == 200


async def test_bloqueio_liberado_apos_resposta(cliente):
    await perguntar(cliente, "oi")
    conversa = await obter(cliente.cookies[COOKIE])
    assert conversa.em_geracao_desde is None


async def test_falha_do_modelo_envia_erro_e_libera_bloqueio(cliente, llm):
    async def quebrar(_mensagens):
        raise RuntimeError("provedor fora do ar")
        yield  # pragma: no cover

    llm.gerar_stream = quebrar
    r = await perguntar(cliente, "oi")
    assert eventos(r.text) == [("erro", {"detail": "Não foi possível gerar a resposta. Tente novamente."})]

    conversa_id = cliente.cookies[COOKIE]
    assert (await obter(conversa_id)).em_geracao_desde is None
    papeis = [m["papel"] for m in (await cliente.get("/conversa")).json()["mensagens"]]
    assert papeis == ["usuario"]  # resposta parcial não é salva


async def test_pergunta_vazia_recebe_422(cliente):
    r = await perguntar(cliente, "   ")
    assert r.status_code == 422


# --- Retenção de 1 hora sem atividade (decisão 5) ---


async def test_conversa_expirada_vira_nova(cliente):
    await perguntar(cliente, "oi")
    antigo = cliente.cookies[COOKIE]
    await definir(antigo, ultima_atividade=func.now() - timedelta(hours=2))

    r = await cliente.get("/conversa")
    assert r.json() == {"mensagens": []}
    assert cliente.cookies[COOKIE] != antigo


async def test_limpeza_remove_conversas_inativas(novo_cliente):
    ativo, inativo = novo_cliente(), novo_cliente()
    await perguntar(ativo, "oi")
    await perguntar(inativo, "oi")
    await definir(inativo.cookies[COOKIE], ultima_atividade=func.now() - timedelta(minutes=61))

    async with SessionLocal() as db:
        assert await remover_inativas(db) == 1
        restantes = (await db.execute(select(Mensagem.conversa_id).distinct())).scalars().all()

    assert await obter(inativo.cookies[COOKIE]) is None
    assert [str(c) for c in restantes] == [ativo.cookies[COOKIE]]


# --- Contexto: mensagens recentes + resumo (seção 7, decisão 9) ---


async def test_resumo_em_lote_e_contexto(cliente, llm, monkeypatch):
    monkeypatch.setattr(config, "mensagens_recentes", 2)
    monkeypatch.setattr(config, "lote_resumo", 2)

    await perguntar(cliente, "pergunta 1")
    assert (await obter(cliente.cookies[COOKIE])).resumo is None

    await perguntar(cliente, "pergunta 2")  # 4 mensagens: 2 antigas -> resumidas
    conversa = await obter(cliente.cookies[COOKIE])
    assert conversa.resumo
    assert conversa.resumo_ate_id > 0

    await perguntar(cliente, "pergunta 3")
    sistema, *resto = llm.ultimo_contexto
    assert "Resumo da conversa até aqui" in sistema["content"]
    # Só as mensagens não resumidas vão inteiras: pergunta 2, resposta 2, pergunta 3
    assert [m["content"] for m in resto if m["role"] == "user"] == ["pergunta 2", "pergunta 3"]

    # O histórico completo continua preservado
    assert len((await cliente.get("/conversa")).json()["mensagens"]) == 6
