from typing import Any

from pydantic_settings import BaseSettings, SettingsConfigDict


class Config(BaseSettings):
    """Configurações lidas de variáveis de ambiente (ou do arquivo .env)."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://chatbot:chatbot@localhost:5434/chatbot"

    # Sessão (seção 2 dos requisitos)
    cookie_nome: str = "sessao"
    cookie_secure: bool = True

    # Retenção: 1 hora sem atividade (seção 9, decisão 5)
    retencao_segundos: int = 3600
    intervalo_limpeza_segundos: int = 300

    # Bloqueio: marca mais antiga que isso é considerada abandonada (seção 9, decisão 1)
    bloqueio_expira_segundos: int = 120

    # Resumo (seção 9, decisão 9)
    mensagens_recentes: int = 10
    lote_resumo: int = 10

    # LLM (seção 9, decisão 8): "falso" para desenvolvimento, "openai" para API compatível
    llm_provedor: str = "falso"
    llm_base_url: str = ""
    llm_api_key: str = ""
    llm_modelo: str = "qwen3"
    llm_timeout_segundos: float = 90
    llm_extra_body: dict[str, Any] = {}

    prompt_sistema: str = (
        "Você é um assistente prestativo. Responda em português, de forma clara e objetiva."
    )


config = Config()
