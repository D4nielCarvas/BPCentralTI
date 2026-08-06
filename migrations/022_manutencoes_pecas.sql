-- Migração 022: Tabela associativa manutencoes_pecas e vinculo com chamados
CREATE TABLE manutencoes_pecas (
    id SERIAL PRIMARY KEY,
    manutencao_id INTEGER REFERENCES manutencoes(id) ON DELETE CASCADE,
    estoque_id INTEGER REFERENCES estoque(id) ON DELETE RESTRICT,
    nome_peca VARCHAR(255),
    quantidade INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

ALTER TABLE manutencoes ADD COLUMN chamado_id INTEGER REFERENCES chamados(id) ON DELETE SET NULL;
