"""Cliente do Gemini: testado sem chamar a API (sem chave nem internet)."""

import pytest

from app.config import config
from app.llm import LLMFalso, LLMGemini, criar_llm, para_gemini


def test_conversao_separa_sistema_e_traduz_papeis():
    sistema, conteudos = para_gemini(
        [
            {"role": "system", "content": "Seja breve."},
            {"role": "system", "content": "Resumo: o usuário se chama Ana."},
            {"role": "user", "content": "Oi"},
            {"role": "assistant", "content": "Olá!"},
            {"role": "user", "content": "Qual é meu nome?"},
        ]
    )
    assert sistema == "Seja breve.\n\nResumo: o usuário se chama Ana."
    assert [c.role for c in conteudos] == ["user", "model", "user"]
    assert [c.parts[0].text for c in conteudos] == ["Oi", "Olá!", "Qual é meu nome?"]


def test_conversao_sem_sistema():
    sistema, conteudos = para_gemini([{"role": "user", "content": "Oi"}])
    assert sistema is None
    assert len(conteudos) == 1


def test_gemini_sem_chave_falha_com_mensagem_clara(monkeypatch):
    monkeypatch.setattr(config, "gemini_api_key", "")
    with pytest.raises(RuntimeError, match="GEMINI_API_KEY"):
        LLMGemini()


def test_configuracao_desliga_raciocinio(monkeypatch):
    monkeypatch.setattr(config, "gemini_api_key", "chave-de-teste")
    cliente = LLMGemini()  # só constrói o cliente; nenhuma requisição é feita
    cfg = cliente._configuracao("Seja breve.")
    assert cfg.system_instruction == "Seja breve."
    assert cfg.thinking_config.thinking_budget == 0


def test_criar_llm(monkeypatch):
    monkeypatch.setattr(config, "llm_provedor", "falso")
    assert isinstance(criar_llm(), LLMFalso)
    monkeypatch.setattr(config, "llm_provedor", "openai")
    with pytest.raises(ValueError, match="gemini"):
        criar_llm()
