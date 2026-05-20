-- =================================================================================
-- MIGRATION 005: Sistema Multi-Tenant por Localidade
-- Data: 2026-05-12
-- Alvo: Banco principal do BP Central TI (Supabase)
--
-- CONTEXTO:
--   - Não existe tabela `usuarios` no schema atual — criada aqui do zero.
--   - A tabela `pedidos` já existe com schema diferente (pedidos internos/estoque).
--     Para não quebrar o fluxo existente, os pedidos dos viewers ficam em
--     `pedidos_viewer` (nova tabela), evitando conflito de constraints e status.
--   - As colunas `localidade_id` são adicionadas nas tabelas de equipamentos,
--     estoque e manutenções via ALTER TABLE ... ADD COLUMN IF NOT EXISTS.
--
-- Execute no SQL Editor do Supabase:
--   https://supabase.com/dashboard/project/SEU_PROJETO/sql/new
-- =================================================================================


-- ─────────────────────────────────────────────────────────────────────────────
-- 1. LOCALIDADES (fazendas + CD + central)
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS localidades (
    id    BIGSERIAL PRIMARY KEY,
    nome  VARCHAR(100) NOT NULL,
    sigla VARCHAR(10),                              -- ex: CEN, SMN, TNG (opcional)
    tipo  VARCHAR(20)  NOT NULL
          CHECK (tipo IN ('fazenda', 'cd', 'central'))
);

CREATE INDEX IF NOT EXISTS idx_localidades_tipo ON localidades(tipo);


-- ─────────────────────────────────────────────────────────────────────────────
-- 2. USUÁRIOS
--    Não existia tabela de usuários no schema anterior.
--    Autenticação por login/senha (hash bcrypt armazenado em senha_hash).
--    role: 'admin' => acesso total | 'viewer' => acesso restrito à localidade.
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS usuarios (
    id             BIGSERIAL PRIMARY KEY,
    nome           VARCHAR(150) NOT NULL,
    login          VARCHAR(80)  NOT NULL UNIQUE,
    senha_hash     TEXT         NOT NULL,
    role           VARCHAR(10)  NOT NULL DEFAULT 'viewer'
                   CHECK (role IN ('admin', 'viewer')),
    localidade_id  BIGINT       REFERENCES localidades(id) ON DELETE SET NULL,
    ativo          BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at     TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at     TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_usuarios_login        ON usuarios(login);
CREATE INDEX IF NOT EXISTS idx_usuarios_localidade   ON usuarios(localidade_id);


-- ─────────────────────────────────────────────────────────────────────────────
-- 3. ADICIONAR localidade_id NAS TABELAS EXISTENTES
--    Tabelas de equipamentos
-- ─────────────────────────────────────────────────────────────────────────────

-- Celulares (todos os tipos)
ALTER TABLE celulares          ADD COLUMN IF NOT EXISTS localidade_id BIGINT REFERENCES localidades(id) ON DELETE SET NULL;
ALTER TABLE celulares_ponto    ADD COLUMN IF NOT EXISTS localidade_id BIGINT REFERENCES localidades(id) ON DELETE SET NULL;
ALTER TABLE celulares_inspecao ADD COLUMN IF NOT EXISTS localidade_id BIGINT REFERENCES localidades(id) ON DELETE SET NULL;
ALTER TABLE celulares_turma    ADD COLUMN IF NOT EXISTS localidade_id BIGINT REFERENCES localidades(id) ON DELETE SET NULL;

-- Demais equipamentos
ALTER TABLE computadores   ADD COLUMN IF NOT EXISTS localidade_id BIGINT REFERENCES localidades(id) ON DELETE SET NULL;
ALTER TABLE impressoras     ADD COLUMN IF NOT EXISTS localidade_id BIGINT REFERENCES localidades(id) ON DELETE SET NULL;
ALTER TABLE estabilizadores ADD COLUMN IF NOT EXISTS localidade_id BIGINT REFERENCES localidades(id) ON DELETE SET NULL;
ALTER TABLE starlink        ADD COLUMN IF NOT EXISTS localidade_id BIGINT REFERENCES localidades(id) ON DELETE SET NULL;

-- Estoque geral
ALTER TABLE estoque ADD COLUMN IF NOT EXISTS localidade_id BIGINT REFERENCES localidades(id) ON DELETE SET NULL;

-- Manutenções
ALTER TABLE manutencoes ADD COLUMN IF NOT EXISTS localidade_id BIGINT REFERENCES localidades(id) ON DELETE SET NULL;

-- Índices de performance para filtros por localidade
CREATE INDEX IF NOT EXISTS idx_celulares_localidade    ON celulares(localidade_id);
CREATE INDEX IF NOT EXISTS idx_computadores_localidade ON computadores(localidade_id);
CREATE INDEX IF NOT EXISTS idx_impressoras_localidade  ON impressoras(localidade_id);
CREATE INDEX IF NOT EXISTS idx_estoque_localidade      ON estoque(localidade_id);
CREATE INDEX IF NOT EXISTS idx_manutencoes_localidade  ON manutencoes(localidade_id);


-- ─────────────────────────────────────────────────────────────────────────────
-- 4. PEDIDOS DOS VIEWERS (tabela separada da `pedidos` existente)
--    A tabela `pedidos` já existe para pedidos internos de estoque/compras.
--    `pedidos_viewer` registra as solicitações feitas pelas fazendas/CD.
--    Status: pendente → em_analise → aprovado/recusado → concluido
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS pedidos_viewer (
    id             BIGSERIAL PRIMARY KEY,
    localidade_id  BIGINT       NOT NULL REFERENCES localidades(id),
    usuario_id     BIGINT       NOT NULL REFERENCES usuarios(id),
    descricao      TEXT         NOT NULL,
    status         VARCHAR(20)  NOT NULL DEFAULT 'pendente'
                   CHECK (status IN ('pendente', 'em_analise', 'aprovado', 'recusado', 'concluido')),
    criado_em      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    atualizado_em  TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_pedidos_viewer_localidade ON pedidos_viewer(localidade_id);
CREATE INDEX IF NOT EXISTS idx_pedidos_viewer_usuario    ON pedidos_viewer(usuario_id);
CREATE INDEX IF NOT EXISTS idx_pedidos_viewer_status     ON pedidos_viewer(status);


-- ─────────────────────────────────────────────────────────────────────────────
-- 5. HISTÓRICO DE STATUS DOS PEDIDOS VIEWER
--    Rastreabilidade completa de cada mudança de status.
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS pedido_viewer_historico (
    id              BIGSERIAL PRIMARY KEY,
    pedido_id       BIGINT      NOT NULL REFERENCES pedidos_viewer(id) ON DELETE CASCADE,
    status_anterior VARCHAR(20),
    status_novo     VARCHAR(20),
    observacao      TEXT,
    alterado_por    BIGINT      REFERENCES usuarios(id) ON DELETE SET NULL,
    alterado_em     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_pedido_viewer_hist_pedido ON pedido_viewer_historico(pedido_id);


-- ─────────────────────────────────────────────────────────────────────────────
-- 6. TRIGGER: atualiza `atualizado_em` em pedidos_viewer automaticamente
-- ─────────────────────────────────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION fn_update_pedidos_viewer_ts()
RETURNS TRIGGER AS $$
BEGIN
    NEW.atualizado_em = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_pedidos_viewer_updated_at ON pedidos_viewer;
CREATE TRIGGER trg_pedidos_viewer_updated_at
    BEFORE UPDATE ON pedidos_viewer
    FOR EACH ROW EXECUTE FUNCTION fn_update_pedidos_viewer_ts();


-- ─────────────────────────────────────────────────────────────────────────────
-- 7. RLS — desabilitar para acesso direto via psycopg2 (mesmo padrão do projeto)
-- ─────────────────────────────────────────────────────────────────────────────
ALTER TABLE localidades            DISABLE ROW LEVEL SECURITY;
ALTER TABLE usuarios               DISABLE ROW LEVEL SECURITY;
ALTER TABLE pedidos_viewer         DISABLE ROW LEVEL SECURITY;
ALTER TABLE pedido_viewer_historico DISABLE ROW LEVEL SECURITY;


-- ─────────────────────────────────────────────────────────────────────────────
-- Verificação pós-execução
-- ─────────────────────────────────────────────────────────────────────────────
-- SELECT table_name FROM information_schema.tables
--   WHERE table_schema = 'public'
--   AND table_name IN ('localidades','usuarios','pedidos_viewer','pedido_viewer_historico');
--
-- SELECT column_name FROM information_schema.columns
--   WHERE table_name = 'celulares' AND column_name = 'localidade_id';
