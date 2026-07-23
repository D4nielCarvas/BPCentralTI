-- =================================================================================
-- MIGRATION 021: Índices compostos para performance da tabela transferencias
-- Data: 2026-07-23
-- Motivo: A rota GET /api/transferencias realiza SELECT com filtros em
--         data_transferencia e id_ativo sem índice composto, resultando em
--         full table scan O(n) que degrada conforme o volume cresce.
--
-- Índices criados:
--   idx_transf_data_ativo  — acelera paginação filtrada por data + ativo
--   idx_transf_id_ativo_id — acelera /historico (ORDER BY id DESC para 1 ativo)
-- =================================================================================

BEGIN;

-- Índice composto para listagem paginada com filtros de data e id_ativo
-- Reduz full scan O(n) para index scan O(log n + k)
CREATE INDEX IF NOT EXISTS idx_transf_data_ativo
    ON transferencias(data_transferencia DESC, id_ativo);

-- Índice para a rota /historico: filtra por id_ativo e ordena por id DESC
CREATE INDEX IF NOT EXISTS idx_transf_id_ativo_id
    ON transferencias(id_ativo, id DESC);

COMMIT;
