from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app import monitoramento
from app.main import app


def test_metadados_imdsv2_usa_apenas_nome_e_tipo(monkeypatch):
    monkeypatch.setattr(monitoramento.Path, "read_text", lambda self: "Amazon EC2\n")
    respostas = [b"token", b"servidor-tca", b"t3.micro"]
    cliente = MagicMock()
    cliente.open.side_effect = [MagicMock(__enter__=lambda self, b=b: SimpleNamespace(read=lambda *args: b), __exit__=lambda *args: None) for b in respostas]
    monkeypatch.setattr(monitoramento.urllib.request, "build_opener", lambda *args: cliente)
    assert monitoramento._metadados_ec2() == ("servidor-tca", "t3.micro")
    pedidos = [call.args[0] for call in cliente.open.call_args_list]
    assert pedidos[0].get_method() == "PUT"
    assert [p.full_url.rsplit("/", 1)[-1] for p in pedidos[1:]] == ["Name", "instance-type"]
    assert all(p.get_header("X-aws-ec2-metadata-token") == "token" for p in pedidos[1:])


def test_metadados_sem_imds_ou_fora_da_aws(monkeypatch):
    monkeypatch.setattr(monitoramento.Path, "read_text", lambda self: "outro")
    assert monitoramento._metadados_ec2() == (None, None)
    monkeypatch.setattr(monitoramento.Path, "read_text", lambda self: "Amazon EC2")
    cliente = MagicMock()
    cliente.open.side_effect = OSError("sem acesso")
    monkeypatch.setattr(monitoramento.urllib.request, "build_opener", lambda *args: cliente)
    assert monitoramento._metadados_ec2() == (None, None)


def test_nome_ausente_nao_impede_tipo(monkeypatch):
    monkeypatch.setattr(monitoramento.Path, "read_text", lambda self: "Amazon EC2")
    cliente = MagicMock()
    token = MagicMock(__enter__=lambda self: SimpleNamespace(read=lambda: b"token"), __exit__=lambda *args: None)
    tipo = MagicMock(__enter__=lambda self: SimpleNamespace(read=lambda *args: b"t3.micro"), __exit__=lambda *args: None)
    cliente.open.side_effect = [token, OSError("tag ausente"), tipo]
    monkeypatch.setattr(monitoramento.urllib.request, "build_opener", lambda *args: cliente)
    assert monitoramento._metadados_ec2() == (None, "t3.micro")


def test_coleta_metricas_preserva_capacidades_e_primeira_cpu(monkeypatch):
    monkeypatch.setattr(monitoramento.psutil, "cpu_percent", lambda interval: 37.5)
    monkeypatch.setattr(monitoramento.psutil, "cpu_count", lambda: 2)
    monkeypatch.setattr(monitoramento.psutil, "virtual_memory", lambda: SimpleNamespace(total=100, available=40, free=10, percent=60))
    monkeypatch.setattr(monitoramento.psutil, "swap_memory", lambda: SimpleNamespace(total=80, free=60, percent=25))
    monkeypatch.setattr(monitoramento.psutil, "disk_usage", lambda path: SimpleNamespace(total=200, used=120, free=80, percent=60))

    inicial = monitoramento.coletar_metricas(cpu_inicial=True)
    assert inicial["cpu"] == {"percentual": None, "nucleos": 2}
    assert inicial["memoria"] == {"total_bytes": 100, "usado_bytes": 60, "disponivel_bytes": 40, "percentual": 60}
    assert inicial["swap"]["usado_bytes"] == 20
    assert inicial["disco"]["disponivel_bytes"] == 80
    assert inicial["gpu"] is None
    assert monitoramento.coletar_metricas()["cpu"]["percentual"] == 37.5


def test_coleta_tolera_metrica_indisponivel(monkeypatch):
    def falha():
        raise OSError("indisponível")

    monkeypatch.setattr(monitoramento.psutil, "virtual_memory", falha)
    resultado = monitoramento.coletar_metricas()
    assert resultado["memoria"] is None
    assert resultado["disco"] is not None


@pytest.mark.asyncio
async def test_endpoint_publico_retornando_amostra_e_pagina(cliente, monkeypatch):
    amostra = {"cpu": {"percentual": 42}, "gpu": None, "coletado_em": "2026-01-01T00:00:00+00:00"}
    monkeypatch.setattr(app.state, "metricas", amostra, raising=False)
    resposta = await cliente.get("/api/metricas")
    pagina = await cliente.get("/monitoramento")
    assert resposta.status_code == 200 and resposta.json() == amostra
    assert resposta.headers["cache-control"] == "no-store"
    assert pagina.status_code == 200 and 'data-metric="cpu"' in pagina.text
    info = {"nome": "servidor-tca", "tipo": "t3.micro"}
    monkeypatch.setattr(app.state, "instancia", info, raising=False)
    resposta_info = await cliente.get("/api/instancia")
    assert resposta_info.status_code == 200 and resposta_info.json() == info
    assert resposta_info.headers["cache-control"] == "no-store"
