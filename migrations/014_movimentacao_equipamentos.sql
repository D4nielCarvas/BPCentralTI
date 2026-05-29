-- =================================================================================
-- MIGRATION 014: Movimentação de Equipamentos em Chamados
-- Data: 2026-05-29
-- =================================================================================

-- ─────────────────────────────────────────────────────────────────────────────
-- Adição de colunas de log temporal na tabela de chamados
-- ─────────────────────────────────────────────────────────────────────────────
ALTER TABLE public.chamados ADD COLUMN IF NOT EXISTS data_saida_fazenda TIMESTAMPTZ DEFAULT NULL;
ALTER TABLE public.chamados ADD COLUMN IF NOT EXISTS data_chegada_ti TIMESTAMPTZ DEFAULT NULL;
ALTER TABLE public.chamados ADD COLUMN IF NOT EXISTS data_saida_ti TIMESTAMPTZ DEFAULT NULL;
ALTER TABLE public.chamados ADD COLUMN IF NOT EXISTS data_chegada_fazenda TIMESTAMPTZ DEFAULT NULL;
