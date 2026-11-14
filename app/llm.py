"""Acesso ao modelo de linguagem (seção 9, decisão 8).

O modelo é o Gemini 2.5 Flash, acessado pelo SDK oficial do Google (`google-genai`).
O modelo simulado permite rodar os testes automatizados sem chave nem internet.

O restante da aplicação trabalha com mensagens no formato
`{"role": "system" | "user" | "assistant", "content": "..."}`;
a conversão para o formato do Gemini fica isolada neste módulo.
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
    """Modelo simulado: repete a pergunta, palavra a palavra. Usado nos testes."""

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


# Papéis da aplicação -> papéis do Gemini
PAPEL_GEMINI = {"user": "user", "assistant": "model"}


def para_gemini(mensagens: Mensagens):
    """Separa a instrução de sistema e converte as demais mensagens para `types.Content`.

    O Gemini recebe a instrução de sistema à parte (`system_instruction`) e chama
    o papel do assistente de "model".
    """
    from google.genai import types

    sistema = "\n\n".join(m["content"] for m in mensagens if m["role"] == "system") or None
    conteudos = [
        types.Content(role=PAPEL_GEMINI[m["role"]], parts=[types.Part.from_text(text=m["content"])])
        for m in mensagens
        if m["role"] != "system"
    ]
    return sistema, conteudos


class LLMGemini:
    """Cliente do Gemini pelo SDK oficial `google-genai`."""

    def __init__(self) -> None:
        if not config.gemini_api_key:
            raise RuntimeError(
                "GEMINI_API_KEY não configurada. Gere uma chave no Google AI Studio e "
                "coloque-a no arquivo .env (veja o README)."
            )
        from google import genai

        self.cliente = genai.Client(
            api_key=config.gemini_api_key,
            http_options={
                # A instrução de sistema (system_instruction) só é aceita na versão v1beta da
                # API; na v1, padrão desta versão do SDK, a chamada é recusada com erro 400.
                "api_version": "v1beta",
                "timeout": int(config.llm_timeout_segundos * 1000),
            },
        )

    def _configuracao(self, sistema: str | None):
        from google.genai import types

        return types.GenerateContentConfig(
            system_instruction=sistema,
            # 0 desliga o "raciocínio" do Gemini 2.5 Flash: o primeiro trecho chega mais cedo.
            thinking_config=types.ThinkingConfig(thinking_budget=config.llm_orcamento_raciocinio),
        )

    async def gerar_stream(self, mensagens: Mensagens) -> AsyncIterator[str]:
        sistema, conteudos = para_gemini(mensagens)
        stream = await self.cliente.aio.models.generate_content_stream(
            model=config.llm_modelo, contents=conteudos, config=self._configuracao(sistema)
        )
        async for pedaco in stream:
            if pedaco.text:
                yield pedaco.text

    async def gerar(self, mensagens: Mensagens) -> str:
        sistema, conteudos = para_gemini(mensagens)
        resposta = await self.cliente.aio.models.generate_content(
            model=config.llm_modelo, contents=conteudos, config=self._configuracao(sistema)
        )
        return resposta.text or ""


def criar_llm() -> ClienteLLM:
    if config.llm_provedor == "gemini":
        return LLMGemini()
    if config.llm_provedor == "falso":
        return LLMFalso()
    raise ValueError(f"LLM_PROVEDOR desconhecido: {config.llm_provedor!r} (use 'gemini' ou 'falso')")
