-- ============================================================
-- Inventário TI v3 — Migration v2
-- Execute este script no Supabase SQL Editor
-- ============================================================

-- ── 1. Celulares Inspeção ────────────────────────────────────
CREATE TABLE IF NOT EXISTS celulares_inspecao (
    id            BIGSERIAL PRIMARY KEY,
    id_ativo      TEXT        NOT NULL UNIQUE,
    id_sistema    TEXT,
    fazenda       TEXT,
    setor         TEXT,
    responsavel   TEXT,
    cargo         TEXT,
    tipo          TEXT,
    modelo        TEXT,
    numero        TEXT,
    status        TEXT        NOT NULL DEFAULT 'Ativo',
    uso_celular   TEXT,
    carregador    TEXT,
    termo_assinado TEXT,
    termo_pdf     TEXT,
    data_entrega  DATE,
    data_devolucao DATE,
    gmail         TEXT,
    senha         TEXT,
    usuario_anterior TEXT,
    imei_1        TEXT,
    imei_2        TEXT,
    num_serie     TEXT,
    armazenamento TEXT,
    observacoes   TEXT,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ── 2. Pedidos ───────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS pedidos (
    id                BIGSERIAL PRIMARY KEY,
    fazenda_solicitante TEXT NOT NULL,
    data_pedido       DATE  NOT NULL DEFAULT CURRENT_DATE,
    status            TEXT  NOT NULL DEFAULT 'Aberto',
    quantidade        INTEGER NOT NULL DEFAULT 1,
    num_requisicao    TEXT,
    item              TEXT  NOT NULL,
    estoque_id        INTEGER REFERENCES estoque(id),
    motivo            TEXT,
    forma_envio       TEXT,
    responsavel       TEXT,
    observacoes       TEXT,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ── 3. Novos campos em manutencoes ──────────────────────────
ALTER TABLE manutencoes
    ADD COLUMN IF NOT EXISTS tipo_manutencao TEXT,
    ADD COLUMN IF NOT EXISTS pecas_utilizadas TEXT,
    ADD COLUMN IF NOT EXISTS subtipo          TEXT,
    ADD COLUMN IF NOT EXISTS arquivo_os       TEXT;

-- ── 4. Novo campo em toner_trocas ───────────────────────────
ALTER TABLE toner_trocas
    ADD COLUMN IF NOT EXISTS tipo_suprimento TEXT NOT NULL DEFAULT 'Toner';

-- ── 5. Índices de performance ────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_cel_insp_status ON celulares_inspecao(status);
CREATE INDEX IF NOT EXISTS idx_cel_insp_fazenda ON celulares_inspecao(fazenda);
CREATE INDEX IF NOT EXISTS idx_pedidos_status ON pedidos(status);
CREATE INDEX IF NOT EXISTS idx_pedidos_fazenda ON pedidos(fazenda_solicitante);

-- ── 6. RLS (Row Level Security) — desabilitar para uso interno
ALTER TABLE celulares_inspecao DISABLE ROW LEVEL SECURITY;
ALTER TABLE pedidos DISABLE ROW LEVEL SECURITY;
