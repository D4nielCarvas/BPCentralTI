-- Tabela para rastreabilidade de equipamentos
CREATE TABLE IF NOT EXISTS remessas_equipamentos (
    id SERIAL PRIMARY KEY,
    id_ativo VARCHAR(100) NOT NULL,
    tipo_equipamento VARCHAR(100),
    modelo VARCHAR(100),
    chamado_id INTEGER REFERENCES chamados(id) ON DELETE SET NULL,
    localidade_id INTEGER REFERENCES localidades(id) ON DELETE SET NULL,
    evento VARCHAR(50) NOT NULL,
    forma_envio VARCHAR(50),
    forma_detalhe VARCHAR(255),
    entregue_por VARCHAR(100),
    recebido_por VARCHAR(100),
    usuario_id INTEGER REFERENCES usuarios(id),
    data_hora TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    observacoes TEXT,
    criado_em TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_remessas_ativo ON remessas_equipamentos(id_ativo);
CREATE INDEX IF NOT EXISTS idx_remessas_chamado ON remessas_equipamentos(chamado_id);
