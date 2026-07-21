-- =================================================================================
-- MIGRATION 020: Controle atômico de sequenciais para geração de id_ativo
-- Data: 2026-07-21
-- Motivo: Eliminar race condition na função proximo_sequencial() que usava
--         SELECT + max+1 sem lock, permitindo duplicatas sob concorrência.
--
-- ATENÇÃO: Após rodar esta migration, execute o script:
--   python scripts/maintenance/bootstrap_id_sequenciais.py
-- para popular a tabela com os máximos atuais de cada prefixo.
-- =================================================================================

BEGIN;

CREATE TABLE IF NOT EXISTS id_sequenciais (
    prefixo  TEXT    PRIMARY KEY,   -- ex: 'NT-CEN-ADM'
    proximo  INTEGER NOT NULL DEFAULT 1
);

COMMENT ON TABLE id_sequenciais IS
    'Controla o próximo sequencial disponível por prefixo de id_ativo. '
    'INSERT ... ON CONFLICT DO UPDATE garante atomicidade sem race condition.';

COMMENT ON COLUMN id_sequenciais.prefixo IS 'Formato: TIPO-LOCAL-SETOR (ex: NT-CEN-ADM, CL-SMN-TRM).';
COMMENT ON COLUMN id_sequenciais.proximo IS 'Próximo número a ser usado. Incrementado atomicamente no SELECT.';

COMMIT;
