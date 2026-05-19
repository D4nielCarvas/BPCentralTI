-- ============================================================
--  009_manutencoes_usuario_id.sql
--  Adiciona coluna usuario_id em manutencoes para permitir
--  filtro de visibilidade por usuário (necessário para role 'apoio').
--
--  Execute no SQL Editor do Supabase antes de reiniciar a app.
-- ============================================================

ALTER TABLE manutencoes
    ADD COLUMN IF NOT EXISTS usuario_id BIGINT
        REFERENCES public.usuarios(id)
        ON DELETE SET NULL;

-- Índice para performance nas queries filtradas por usuário
CREATE INDEX IF NOT EXISTS idx_manutencoes_usuario
    ON manutencoes(usuario_id);

-- Comentário descritivo
COMMENT ON COLUMN manutencoes.usuario_id IS
    'Usuário responsável/criador da OS. NULL = criado pelo sistema/admin sem vínculo direto.';
