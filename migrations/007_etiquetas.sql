-- =================================================================================
-- MIGRATION 007: Sistema de Etiquetas (Tags) para Pedidos
-- Data: 2026-05-14
-- Alvo: Banco principal do BP Central TI (Supabase)
-- Executar no SQL Editor do Supabase antes de reiniciar o sistema
-- =================================================================================

-- ─────────────────────────────────────────────────────────────────────────────
-- 1. Tabela de etiquetas disponíveis
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.chamado_etiquetas (
    id      SERIAL PRIMARY KEY,
    nome    VARCHAR(50) UNIQUE NOT NULL,
    cor_hex VARCHAR(7)  DEFAULT '#6c757d'
);

-- ─────────────────────────────────────────────────────────────────────────────
-- 2. Relacionamento N:M entre pedidos_viewer e etiquetas
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.pedidos_viewer_etiquetas (
    pedido_id  INT REFERENCES public.pedidos_viewer(id) ON DELETE CASCADE,
    etiqueta_id INT REFERENCES public.chamado_etiquetas(id) ON DELETE CASCADE,
    PRIMARY KEY (pedido_id, etiqueta_id)
);

-- Índices para acelerar JOINs
CREATE INDEX IF NOT EXISTS idx_pve_pedido   ON public.pedidos_viewer_etiquetas(pedido_id);
CREATE INDEX IF NOT EXISTS idx_pve_etiqueta ON public.pedidos_viewer_etiquetas(etiqueta_id);

-- ─────────────────────────────────────────────────────────────────────────────
-- 3. Seed de etiquetas padrão de TI
-- ─────────────────────────────────────────────────────────────────────────────
INSERT INTO public.chamado_etiquetas (nome, cor_hex) VALUES
    ('Impressora',    '#f59e0b'),
    ('Datasul',       '#3b82f6'),
    ('Gatec',         '#8b5cf6'),
    ('PowerBI',       '#f97316'),
    ('Sistema',       '#06b6d4'),
    ('PC',            '#10b981'),
    ('Periférico',    '#64748b'),
    ('Rede/Internet', '#ef4444')
ON CONFLICT (nome) DO NOTHING;

-- ─────────────────────────────────────────────────────────────────────────────
-- Verificação final:
-- SELECT * FROM chamado_etiquetas ORDER BY nome;
-- SELECT * FROM pedidos_viewer_etiquetas LIMIT 5;
-- ─────────────────────────────────────────────────────────────────────────────
