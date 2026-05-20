-- =================================================================================
-- MIGRATION V3: Adições para Refinamentos (Abril 2026)
-- Data: 2026-04-14
-- Alvo: Banco principal do BP Central TI
-- Executar no SQL Editor do Supabase antes de testar as novas funcionalidades
-- =================================================================================

-- 1. Adicionar o tipo_suprimento na tabela principal de Toners para que o cadastro 
-- possa diferenciar Toners de Cilindros (sem afetar tabelas em uso ativas).
ALTER TABLE public.toners
ADD COLUMN IF NOT EXISTS tipo_suprimento TEXT DEFAULT 'Toner';

-- Obs: O sistema já previa tipo_suprimento na tabela de histórico de trocas:
-- ('toner_trocas'), então não é preciso modificar lá.
