-- ============================================================
--  011_celulares_inspecao_drop_numero.sql
--  Remove o campo numero da tabela celulares_inspecao.
--
--  Execute no SQL Editor do Supabase.
-- ============================================================

ALTER TABLE celulares_inspecao
    DROP COLUMN IF EXISTS numero;
