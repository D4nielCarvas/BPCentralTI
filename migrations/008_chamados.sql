-- =================================================================================
-- MIGRATION 008: Módulo de Chamados (Helpdesk)
-- Data: 2026-05-14
-- Alvo: Banco principal do BP Central TI (Supabase)
-- =================================================================================

-- ─────────────────────────────────────────────────────────────────────────────
-- Tabela principal de chamados
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.chamados (
    id           SERIAL PRIMARY KEY,
    localidade_id INT  NOT NULL REFERENCES public.localidades(id),
    criado_por   BIGINT NOT NULL REFERENCES public.usuarios(id),
    atribuido_a  BIGINT REFERENCES public.usuarios(id),
    id_ativo     VARCHAR(50),          -- ID do equipamento com problema (opcional)
    titulo       VARCHAR(150) NOT NULL,
    descricao    TEXT NOT NULL,
    prioridade   VARCHAR(20)  DEFAULT 'media'
                 CHECK (prioridade IN ('baixa', 'media', 'alta', 'urgente')),
    status       VARCHAR(20)  DEFAULT 'aberto'
                 CHECK (status IN ('aberto', 'em_atendimento', 'pendente_usuario', 'resolvido', 'fechado')),
    criado_em    TIMESTAMPTZ  DEFAULT now(),
    atualizado_em TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_chamados_localidade  ON public.chamados(localidade_id);
CREATE INDEX IF NOT EXISTS idx_chamados_atribuido   ON public.chamados(atribuido_a);
CREATE INDEX IF NOT EXISTS idx_chamados_status      ON public.chamados(status);

-- ─────────────────────────────────────────────────────────────────────────────
-- Tabela de mensagens do chat por chamado
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.chamado_mensagens (
    id          SERIAL PRIMARY KEY,
    chamado_id  INT     NOT NULL REFERENCES public.chamados(id) ON DELETE CASCADE,
    usuario_id  BIGINT  NOT NULL REFERENCES public.usuarios(id),
    mensagem    TEXT    NOT NULL,
    is_sistema  BOOLEAN DEFAULT FALSE,  -- Mensagens automáticas da TI
    criado_em   TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_chamado_msgs_chamado ON public.chamado_mensagens(chamado_id);

-- ─────────────────────────────────────────────────────────────────────────────
-- Trigger para atualizar atualizado_em automaticamente
-- ─────────────────────────────────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION update_chamado_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.atualizado_em = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_chamado_updated_at ON public.chamados;
CREATE TRIGGER trg_chamado_updated_at
    BEFORE UPDATE ON public.chamados
    FOR EACH ROW EXECUTE FUNCTION update_chamado_timestamp();

-- ─────────────────────────────────────────────────────────────────────────────
-- Verificação:
-- SELECT * FROM chamados LIMIT 3;
-- SELECT * FROM chamado_mensagens LIMIT 3;
-- ─────────────────────────────────────────────────────────────────────────────
