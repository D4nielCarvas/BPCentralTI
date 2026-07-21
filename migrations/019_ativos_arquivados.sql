-- =================================================================================
-- MIGRATION 019: Tabela de arquivo para ativos migrados de tipo
-- Data: 2026-07-21
-- Motivo: Garantir auditabilidade quando um ativo muda de tipo (ex: Celular → Celular Turma)
--         e o registro original é deletado da tabela de origem.
--         O snapshot JSONB preserva o estado completo antes da deleção.
-- =================================================================================

BEGIN;

CREATE TABLE IF NOT EXISTS ativos_arquivados (
    id              SERIAL PRIMARY KEY,
    id_ativo_origem TEXT        NOT NULL,
    tabela_origem   TEXT        NOT NULL,
    motivo          TEXT        NOT NULL DEFAULT 'Migração de Tipo',
    migrado_para    TEXT,                          -- novo id_ativo após migração
    snapshot        JSONB       NOT NULL,          -- estado completo da linha original
    arquivado_em    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    arquivado_por   TEXT
);

COMMENT ON TABLE ativos_arquivados IS
    'Arquivo imutável de ativos deletados por migração de tipo. '
    'snapshot contém a linha completa em JSON para fins de auditoria.';

CREATE INDEX IF NOT EXISTS idx_arquivados_origem  ON ativos_arquivados (id_ativo_origem);
CREATE INDEX IF NOT EXISTS idx_arquivados_migrado ON ativos_arquivados (migrado_para);
CREATE INDEX IF NOT EXISTS idx_arquivados_data    ON ativos_arquivados (arquivado_em DESC);

COMMIT;
