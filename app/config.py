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

    # LLM (seção 9, decisão 8): Gemini 3.1 Flash-Lite; "falso" é o modelo simulado dos testes
    llm_provedor: str = "gemini"
    gemini_api_key: str = ""
    llm_modelo: str = "gemini-3.1-flash-lite"
    llm_timeout_segundos: float = 90
    # Tokens de "raciocínio" do Gemini: 0 desliga (menor latência), -1 automático
    llm_orcamento_raciocinio: int = 0

    prompt_sistema: str = (
        "Você é um assistente de perguntas e respostas. Seu objetivo é ajudar o usuário "
        "a entender assuntos e encontrar respostas úteis, claras e corretas.\n\n"
        "Responda diretamente à pergunta, em português do Brasil, salvo se o usuário pedir "
        "outro idioma. Adapte a profundidade ao pedido e use exemplos, listas ou Markdown "
        "quando ajudarem a compreensão, sem alongar a resposta desnecessariamente.\n\n"
        "Use o contexto da conversa para interpretar perguntas de acompanhamento. Se faltar "
        "uma informação indispensável ou houver ambiguidade relevante, peça esclarecimento; "
        "caso contrário, explicite suposições importantes e avance.\n\n"
        "Não invente fatos, fontes, citações ou experiências. Se não souber, houver incerteza "
        "ou a resposta depender de informações atuais que você não possa verificar, diga isso "
        "claramente e indique como verificar quando for útil. Diferencie fatos de estimativas "
        "e opiniões. Não afirme ter consultado fontes ou executado ações que não realizou.\n\n"
        "Em assuntos de saúde, finanças, direito ou outros de alto impacto, ofereça informações "
        "gerais com cautela e sugira apoio profissional quando apropriado. Se um pedido envolver "
        "dano ou atividade perigosa, não forneça instruções que facilitem esse dano e ofereça "
        "uma alternativa segura quando possível."
    )


config = Config()
