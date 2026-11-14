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

    # LLM (seção 9, decisão 8): Gemini 2.5 Flash; "falso" é o modelo simulado dos testes
    llm_provedor: str = "gemini"
    gemini_api_key: str = ""
    llm_modelo: str = "gemini-2.5-flash"
    llm_timeout_segundos: float = 90
    # Tokens de "raciocínio" do Gemini 2.5 Flash: 0 desliga (menor latência), -1 automático
    llm_orcamento_raciocinio: int = 0

    prompt_sistema: str = (
        "Você é um assistente prestativo. Responda em português, de forma clara e objetiva."
    )


config = Config()
