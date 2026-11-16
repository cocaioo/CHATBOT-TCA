-- Execute com a aplicação parada, uma vez em cada banco existente.
ALTER TABLE conversas ADD COLUMN IF NOT EXISTS geracao_id UUID;
