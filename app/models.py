import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Conversa(Base):
    __tablename__ = "conversas"

    # uuid4 usa gerador criptográfico (os.urandom): ID imprevisível (seção 2, decisão 5)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    criada_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    ultima_atividade: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    # Preenchido enquanto uma resposta está sendo gerada (bloqueio)
    em_geracao_desde: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resumo: Mapped[str | None] = mapped_column(Text)
    # ID da última mensagem coberta pelo resumo (0 = nenhuma)
    resumo_ate_id: Mapped[int] = mapped_column(BigInteger, default=0, server_default="0")


class Mensagem(Base):
    __tablename__ = "mensagens"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    conversa_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("conversas.id", ondelete="CASCADE"), index=True
    )
    papel: Mapped[str] = mapped_column(String(16))  # "usuario" ou "assistente"
    conteudo: Mapped[str] = mapped_column(Text)
    criada_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
