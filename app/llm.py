"""Acesso ao modelo de linguagem (seção 9, decisão 8).

O Qwen 3 é acessado por uma API compatível com a da OpenAI; o provedor é
escolhido por configuração. O modelo simulado permite desenvolver e testar
sem provedor.
"""

import asyncio
from collections.abc import AsyncIterator
from typing import Protocol

from .config import config

Mensagens = list[dict[str, str]]


class ClienteLLM(Protocol):
    def gerar_stream(self, mensagens: Mensagens) -> AsyncIterator[str]: ...

    async def gerar(self, mensagens: Mensagens) -> str: ...


class LLMFalso:
    """Modelo simulado: repete a pergunta, palavra a palavra."""

    def __init__(self, atraso: float = 0.05) -> None:
        self.atraso = atraso
        self.ultimo_contexto: Mensagens = []

    async def _palavras(self, mensagens: Mensagens) -> AsyncIterator[str]:
        pergunta = next((m["content"] for m in reversed(mensagens) if m["role"] == "user"), "")
        resposta = f"[modelo simulado] Você perguntou: {pergunta}"
        for palavra in resposta.split(" "):
            await asyncio.sleep(self.atraso)
            yield palavra + " "

    async def gerar_stream(self, mensagens: Mensagens) -> AsyncIterator[str]:
        self.ultimo_contexto = mensagens  # contexto da última resposta (usado nos testes)
        async for palavra in self._palavras(mensagens):
            yield palavra

    async def gerar(self, mensagens: Mensagens) -> str:
        partes = [trecho async for trecho in self._palavras(mensagens)]
        return "".join(partes).strip()


class LLMOpenAICompativel:
    """Cliente para qualquer serviço com API compatível com a da OpenAI
    (DashScope, OpenRouter, Groq, Ollama, vLLM...)."""

    def __init__(self) -> None:
        from openai import AsyncOpenAI

        self.cliente = AsyncOpenAI(
            base_url=config.llm_base_url or None,
            api_key=config.llm_api_key or "nao-usada",
            timeout=config.llm_timeout_segundos,
        )

    async def gerar_stream(self, mensagens: Mensagens) -> AsyncIterator[str]:
        stream = await self.cliente.chat.completions.create(
            model=config.llm_modelo,
            messages=mensagens,
            stream=True,
            extra_body=config.llm_extra_body or None,
        )
        async for pedaco in stream:
            if pedaco.choices and (texto := pedaco.choices[0].delta.content):
                yield texto

    async def gerar(self, mensagens: Mensagens) -> str:
        resposta = await self.cliente.chat.completions.create(
            model=config.llm_modelo,
            messages=mensagens,
            extra_body=config.llm_extra_body or None,
        )
        return resposta.choices[0].message.content or ""


def criar_llm() -> ClienteLLM:
    if config.llm_provedor == "openai":
        return LLMOpenAICompativel()
    if config.llm_provedor == "falso":
        return LLMFalso()
    raise ValueError(f"LLM_PROVEDOR desconhecido: {config.llm_provedor!r}")
