"""Amostras compartilhadas das métricas da máquina, sem dados de processos."""

import asyncio
import logging
import platform
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import psutil

logger = logging.getLogger(__name__)


def _metadados_ec2():
    """Consulta somente os dois campos públicos pretendidos, com IMDSv2 e sem proxy."""
    try:
        if Path('/sys/class/dmi/id/sys_vendor').read_text().strip() != 'Amazon EC2':
            return None, None
        cliente = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        raiz = 'http://169.254.169.254/latest/'
        pedido = urllib.request.Request(raiz + 'api/token', method='PUT', headers={'X-aws-ec2-metadata-token-ttl-seconds': '60'})
        with cliente.open(pedido, timeout=1) as resposta:
            token = resposta.read().decode('utf-8')

        def campo(caminho):
            try:
                requisicao = urllib.request.Request(raiz + 'meta-data/' + caminho, headers={'X-aws-ec2-metadata-token': token})
                with cliente.open(requisicao, timeout=1) as resposta:
                    return resposta.read(1024).decode('utf-8').strip() or None
            except (OSError, UnicodeError):
                return None

        return campo('tags/instance/Name'), campo('instance-type')
    except (OSError, UnicodeError):
        return None, None


def coletar_instancia():
    nome, tipo = _metadados_ec2()
    try:
        sistema = platform.freedesktop_os_release().get('PRETTY_NAME') or platform.system()
    except (OSError, AttributeError):
        sistema = platform.system()
    boot = _medir(psutil.boot_time)
    return {
        'nome': nome,
        'tipo': tipo,
        'sistema_operacional': sistema,
        'arquitetura': platform.machine() or None,
        'iniciada_em': datetime.fromtimestamp(boot, timezone.utc).isoformat() if boot is not None else None,
    }


async def laco_instancia(app):
    while True:
        app.state.instancia = await asyncio.to_thread(coletar_instancia)
        await asyncio.sleep(60)


def _medir(funcao):
    try:
        return funcao()
    except (OSError, psutil.Error):
        logger.warning("Métrica indisponível", exc_info=True)
        return None


def _memoria(funcao):
    valor = funcao()
    disponivel = getattr(valor, "available", valor.free)
    return {
        "total_bytes": valor.total,
        "usado_bytes": valor.total - disponivel,
        "disponivel_bytes": disponivel,
        "percentual": valor.percent,
    }


def _disco():
    valor = psutil.disk_usage(Path.home().anchor)
    return {
        "total_bytes": valor.total,
        "usado_bytes": valor.used,
        "disponivel_bytes": valor.free,
        "percentual": valor.percent,
    }


def coletar_metricas(cpu_inicial=False):
    cpu = _medir(lambda: psutil.cpu_percent(interval=None))
    return {
        "coletado_em": datetime.now(timezone.utc).isoformat(),
        "cpu": {"percentual": None if cpu_inicial else cpu, "nucleos": _medir(psutil.cpu_count)},
        "memoria": _medir(lambda: _memoria(psutil.virtual_memory)),
        "swap": _medir(lambda: _memoria(psutil.swap_memory)),
        "disco": _medir(_disco),
        "gpu": None,
    }


async def laco_metricas(app):
    while True:
        await asyncio.sleep(5)
        app.state.metricas = coletar_metricas()
