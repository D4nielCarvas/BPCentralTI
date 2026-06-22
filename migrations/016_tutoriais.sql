-- =================================================================================
-- MIGRATION 016: Tabela para Tutoriais
-- Data: 2026-06-22
--
-- CONTEXTO:
--   - Tabela para armazenar metadados dos tutoriais de vídeo e imagem.
--   - Os arquivos físicos serão enviados para um Bucket no Supabase Storage.
-- =================================================================================

CREATE TABLE IF NOT EXISTS tutoriais (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    titulo VARCHAR(255) NOT NULL,
    descricao TEXT,
    nome_arquivo VARCHAR(255) NOT NULL,
    mimetype VARCHAR(100),
    url_arquivo TEXT,
    tamanho_bytes BIGINT,
    criado_em TIMESTAMPTZ DEFAULT NOW(),
    criado_por BIGINT REFERENCES usuarios(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_tutoriais_criado_em ON tutoriais(criado_em DESC);
