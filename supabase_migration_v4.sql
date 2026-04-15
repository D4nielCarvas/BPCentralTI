-- =================================================================================
-- MIGRATION V4: 9 Melhorias (Abril 2026)
-- Data: 2026-04-15
-- Alvo: Banco principal do Inventário TI (Supabase)
-- Executar no SQL Editor do Supabase antes de reiniciar o sistema
-- =================================================================================

-- ─────────────────────────────────────────────────────────────────────────────
-- ITEM 4: Nova tabela celulares_turma
-- IDs no formato CL-TRM-NN (sem fazenda fixa)
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.celulares_turma (
    id               BIGSERIAL PRIMARY KEY,
    id_ativo         VARCHAR(30)  UNIQUE NOT NULL,   -- formato: CL-TRM-01
    num_turma        VARCHAR(50),
    responsavel      VARCHAR(150),
    fazenda          VARCHAR(100),                    -- opcional (itinerante)
    setor            VARCHAR(100),
    modelo           VARCHAR(100),
    tipo             VARCHAR(50),
    status           VARCHAR(50)  DEFAULT 'Ativo',
    uso_celular      VARCHAR(100),
    carregador       VARCHAR(10),
    termo_assinado   VARCHAR(10),
    data_entrega     DATE,
    data_devolucao   DATE,
    gmail_clockin    VARCHAR(150),
    senha            VARCHAR(255),
    usuario_anterior VARCHAR(150),
    imei_1           VARCHAR(50),
    imei_2           VARCHAR(50),
    num_serie        VARCHAR(100),
    armazenamento    VARCHAR(50),
    observacoes      TEXT,
    termo_pdf        VARCHAR(255),
    created_at       TIMESTAMPTZ  DEFAULT NOW(),
    updated_at       TIMESTAMPTZ  DEFAULT NOW()
);

-- Índice para busca global por id_ativo
CREATE INDEX IF NOT EXISTS idx_celulares_turma_id_ativo ON public.celulares_turma(id_ativo);
-- Índice para busca por responsável/fazenda
CREATE INDEX IF NOT EXISTS idx_celulares_turma_resp ON public.celulares_turma(responsavel);

-- ─────────────────────────────────────────────────────────────────────────────
-- ITEM 7: Starlink — novos campos de identificação e login
-- ─────────────────────────────────────────────────────────────────────────────
ALTER TABLE public.starlink
    ADD COLUMN IF NOT EXISTS id_starlink   VARCHAR(100),
    ADD COLUMN IF NOT EXISTS numero_kit    VARCHAR(100),
    ADD COLUMN IF NOT EXISTS email_login   VARCHAR(150),
    ADD COLUMN IF NOT EXISTS senha_login   VARCHAR(255);

-- ─────────────────────────────────────────────────────────────────────────────
-- ITEM 9: Pedidos — campos condicionais por forma de envio
-- ─────────────────────────────────────────────────────────────────────────────
ALTER TABLE public.pedidos
    ADD COLUMN IF NOT EXISTS nota_fiscal_pdf   VARCHAR(255),
    ADD COLUMN IF NOT EXISTS responsavel_envio VARCHAR(150);

-- ─────────────────────────────────────────────────────────────────────────────
-- ITEM 5/6: Índice de performance para regen de ID após transferência
-- Permite LIKE scan eficiente em id_ativo (prefixo)
-- ─────────────────────────────────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_celulares_id_prefix       ON public.celulares      (id_ativo text_pattern_ops);
CREATE INDEX IF NOT EXISTS idx_computadores_id_prefix    ON public.computadores   (id_ativo text_pattern_ops);
CREATE INDEX IF NOT EXISTS idx_impressoras_id_prefix     ON public.impressoras    (id_ativo text_pattern_ops);
CREATE INDEX IF NOT EXISTS idx_estabilizadores_id_prefix ON public.estabilizadores(id_ativo text_pattern_ops);
CREATE INDEX IF NOT EXISTS idx_starlink_id_prefix        ON public.starlink       (id_ativo text_pattern_ops);
CREATE INDEX IF NOT EXISTS idx_celulares_turma_id_prefix ON public.celulares_turma(id_ativo text_pattern_ops);

-- ─────────────────────────────────────────────────────────────────────────────
-- Verificação final
-- ─────────────────────────────────────────────────────────────────────────────
-- Após executar, confirme com:
-- SELECT column_name FROM information_schema.columns WHERE table_name = 'celulares_turma';
-- SELECT column_name FROM information_schema.columns WHERE table_name = 'starlink' AND column_name IN ('id_starlink','numero_kit','email_login','senha_login');
-- SELECT column_name FROM information_schema.columns WHERE table_name = 'pedidos' AND column_name IN ('nota_fiscal_pdf','responsavel_envio');
