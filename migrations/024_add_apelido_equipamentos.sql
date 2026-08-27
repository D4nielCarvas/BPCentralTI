-- MIGRATION 024: Adiciona coluna apelido nas 8 tabelas de equipamentos
-- Permite que usuários de fazenda com permissão possam nomear/identificar seus ativos

ALTER TABLE celulares          ADD COLUMN IF NOT EXISTS apelido VARCHAR(150);
ALTER TABLE celulares_ponto    ADD COLUMN IF NOT EXISTS apelido VARCHAR(150);
ALTER TABLE celulares_inspecao ADD COLUMN IF NOT EXISTS apelido VARCHAR(150);
ALTER TABLE celulares_turma    ADD COLUMN IF NOT EXISTS apelido VARCHAR(150);
ALTER TABLE computadores       ADD COLUMN IF NOT EXISTS apelido VARCHAR(150);
ALTER TABLE impressoras        ADD COLUMN IF NOT EXISTS apelido VARCHAR(150);
ALTER TABLE estabilizadores    ADD COLUMN IF NOT EXISTS apelido VARCHAR(150);
ALTER TABLE starlink           ADD COLUMN IF NOT EXISTS apelido VARCHAR(150);
