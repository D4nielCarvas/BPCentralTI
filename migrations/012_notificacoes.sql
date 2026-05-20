-- Alvo: Banco principal do BP Central TI (Supabase)
-- Descrição: Criação da tabela de notificações in-app para administradores.

CREATE TABLE IF NOT EXISTS notificacoes (
    id SERIAL PRIMARY KEY,
    usuario_id INT NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    chamado_id INT REFERENCES chamados(id) ON DELETE CASCADE,
    mensagem TEXT NOT NULL,
    lida BOOLEAN DEFAULT FALSE,
    criado_em TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_notificacoes_usuario_lida 
ON notificacoes(usuario_id, lida);
