-- ============================================================
--  supabase_migration.sql — Criação das tabelas no Supabase
--  Execute este script no SQL Editor do Supabase:
--  https://supabase.com/dashboard/project/SEU_PROJETO/sql
--
--  As tabelas existentes são preservadas (IF NOT EXISTS).
--  Execute uma vez após criar o projeto no Supabase.
-- ============================================================

-- ── CELULARES ─────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS celulares (
    id SERIAL PRIMARY KEY,
    id_ativo TEXT UNIQUE NOT NULL,
    fazenda TEXT, setor TEXT, responsavel TEXT,
    tipo TEXT, modelo TEXT, numero TEXT,
    status TEXT DEFAULT 'Ativo',
    uso_celular TEXT, carregador TEXT,
    termo_assinado TEXT, data_entrega DATE, data_devolucao DATE,
    gmail TEXT, senha TEXT, usuario_anterior TEXT,
    imei_1 TEXT, imei_2 TEXT, num_serie TEXT,
    armazenamento TEXT, termo_pdf TEXT, cargo TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- ── CELULARES DE PONTO/TURMA ──────────────────────────────────
CREATE TABLE IF NOT EXISTS celulares_ponto (
    id SERIAL PRIMARY KEY,
    id_ativo TEXT UNIQUE NOT NULL,
    fazenda TEXT, funcao TEXT, responsavel TEXT,
    num_turma TEXT, tipo TEXT, modelo TEXT,
    status TEXT DEFAULT 'Ativo',
    uso_celular TEXT, carregador TEXT,
    termo_assinado TEXT, data_entrega DATE, data_devolucao DATE,
    gmail_clockin TEXT, senha TEXT, usuario_anterior TEXT,
    imei_1 TEXT, imei_2 TEXT, num_serie TEXT,
    armazenamento TEXT, termo_pdf TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- ── COMPUTADORES ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS computadores (
    id SERIAL PRIMARY KEY,
    id_ativo TEXT UNIQUE NOT NULL,
    fazenda TEXT, setor TEXT, responsavel TEXT,
    tipo TEXT, modelo TEXT, marca TEXT,
    numero_serie TEXT, patrimonio TEXT,
    processador TEXT, memoria_ram TEXT, armazenamento TEXT,
    sistema_operacional TEXT, versao_so TEXT,
    status TEXT DEFAULT 'Ativo',
    data_aquisicao DATE, data_entrega DATE, data_devolucao DATE,
    usuario_windows TEXT, senha_windows TEXT,
    usuario_anterior TEXT, observacoes TEXT,
    termo_assinado TEXT, termo_pdf TEXT, cargo TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- ── IMPRESSORAS ───────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS impressoras (
    id SERIAL PRIMARY KEY,
    id_ativo TEXT UNIQUE NOT NULL,
    fazenda TEXT, setor TEXT, responsavel TEXT,
    marca TEXT, modelo TEXT, tipo TEXT,
    numero_serie TEXT, patrimonio TEXT,
    ip_rede TEXT, hostname TEXT,
    status TEXT DEFAULT 'Ativo',
    data_aquisicao DATE, data_instalacao DATE,
    suprimento_atual TEXT, observacoes TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- ── ESTABILIZADORES / NOBREAKES ───────────────────────────────
CREATE TABLE IF NOT EXISTS estabilizadores (
    id SERIAL PRIMARY KEY,
    id_ativo TEXT UNIQUE NOT NULL,
    fazenda TEXT, setor TEXT,
    modelo TEXT, status TEXT DEFAULT 'Ativo',
    uso TEXT, num_serie TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- ── ANTENAS STARLINK ──────────────────────────────────────────
CREATE TABLE IF NOT EXISTS starlink (
    id SERIAL PRIMARY KEY,
    id_ativo TEXT UNIQUE NOT NULL,
    fazenda TEXT, setor TEXT, responsavel TEXT,
    modelo TEXT, num_serie TEXT, mac_address TEXT,
    ip_rede TEXT, status TEXT DEFAULT 'Ativo',
    data_instalacao DATE, data_aquisicao DATE,
    plano TEXT, observacoes TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- ── ESTOQUE GERAL ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS estoque (
    id SERIAL PRIMARY KEY,
    item TEXT NOT NULL,
    cod_pedido TEXT,
    quantidade INTEGER DEFAULT 0,
    unidade TEXT DEFAULT 'un',
    localizacao TEXT, observacoes TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- ── MOVIMENTAÇÕES DE ESTOQUE ──────────────────────────────────
CREATE TABLE IF NOT EXISTS estoque_movimentacoes (
    id SERIAL PRIMARY KEY,
    estoque_id INTEGER NOT NULL REFERENCES estoque(id),
    tipo TEXT NOT NULL CHECK (tipo IN ('entrada', 'saida')),
    quantidade INTEGER NOT NULL CHECK (quantidade > 0),
    motivo TEXT, responsavel TEXT,
    data_hora TIMESTAMPTZ DEFAULT NOW()
);

-- ── TONERS ───────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS toners (
    id SERIAL PRIMARY KEY,
    modelo_impressora TEXT NOT NULL,
    modelo_toner TEXT NOT NULL,
    cor TEXT DEFAULT 'Preto',
    quantidade_estoque INTEGER DEFAULT 0,
    data_ultima_troca DATE,
    quantidade_minima INTEGER DEFAULT 1,
    observacoes TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- ── TROCAS DE TONER ───────────────────────────────────────────
CREATE TABLE IF NOT EXISTS toner_trocas (
    id SERIAL PRIMARY KEY,
    toner_id INTEGER NOT NULL REFERENCES toners(id),
    quantidade INTEGER DEFAULT 1,
    responsavel TEXT,
    impressora_id_ativo TEXT,
    data_troca DATE DEFAULT CURRENT_DATE,
    observacoes TEXT
);

-- ── MANUTENÇÕES ───────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS manutencoes (
    id SERIAL PRIMARY KEY,
    id_ativo TEXT NOT NULL,
    tipo_equipamento TEXT NOT NULL,
    modelo TEXT, local_atual TEXT,
    data_recebimento DATE, pessoa_recebimento TEXT,
    problema_relatado TEXT,
    data_manutencao DATE,
    os_manutencao TEXT,
    orcamento NUMERIC(10,2),
    status TEXT DEFAULT 'Aberta',
    data_envio DATE, forma_envio TEXT,
    data_retorno DATE, solucao_aplicada TEXT,
    tecnico TEXT, observacoes TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- ── DESCARTES ─────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS descartes (
    id SERIAL PRIMARY KEY,
    id_ativo TEXT NOT NULL,
    tipo_equipamento TEXT NOT NULL,
    modelo TEXT, motivo TEXT,
    data_descarte DATE,
    responsavel_descarte TEXT,
    forma_descarte TEXT,
    destinatario TEXT,
    documento_referencia TEXT,
    observacoes TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ── TRANSFERÊNCIAS ────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS transferencias (
    id SERIAL PRIMARY KEY,
    id_ativo TEXT NOT NULL,
    tipo_equipamento TEXT NOT NULL,
    responsavel_origem TEXT,
    fazenda_origem TEXT,
    setor_origem TEXT,
    responsavel_destino TEXT,
    fazenda_destino TEXT,
    setor_destino TEXT,
    tipo_transferencia TEXT NOT NULL,
    motivo TEXT,
    data_transferencia DATE NOT NULL DEFAULT CURRENT_DATE,
    registrado_por TEXT,
    observacoes TEXT,
    termo_pdf TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ── HISTÓRICO ─────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS historico (
    id SERIAL PRIMARY KEY,
    id_ativo TEXT,
    tipo_equipamento TEXT,
    acao TEXT,
    campo_alterado TEXT,
    valor_anterior TEXT,
    valor_novo TEXT,
    usuario TEXT DEFAULT 'Sistema',
    data_hora TIMESTAMPTZ DEFAULT NOW()
);

-- ── ÍNDICES para performance ──────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_historico_id_ativo ON historico(id_ativo);
CREATE INDEX IF NOT EXISTS idx_historico_data ON historico(data_hora DESC);
CREATE INDEX IF NOT EXISTS idx_manutencoes_status ON manutencoes(status);
CREATE INDEX IF NOT EXISTS idx_transferencias_id_ativo ON transferencias(id_ativo);
CREATE INDEX IF NOT EXISTS idx_transferencias_data ON transferencias(data_transferencia DESC);
CREATE INDEX IF NOT EXISTS idx_computadores_num_serie ON computadores(numero_serie);
CREATE INDEX IF NOT EXISTS idx_celulares_status ON celulares(status);
CREATE INDEX IF NOT EXISTS idx_computadores_status ON computadores(status);

-- ── Comentário final ──────────────────────────────────────────
-- Execute no SQL Editor do Supabase:
-- https://supabase.com/dashboard/project/SEU_PROJETO/sql/new
--
-- Após executar, configure o .env com a connection string e inicie o sistema.
