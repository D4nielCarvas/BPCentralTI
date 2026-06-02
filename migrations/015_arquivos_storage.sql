-- Migração 015: Tabela central para armazenamento persistente de arquivos (BLOBs)
-- Soluciona o problema de persistência em servidores com filesystem efêmero (Render)

CREATE TABLE IF NOT EXISTS arquivos_storage (
    nome_arquivo VARCHAR(255) PRIMARY KEY,
    dados BYTEA NOT NULL,
    mimetype VARCHAR(100) NOT NULL,
    criado_em TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
