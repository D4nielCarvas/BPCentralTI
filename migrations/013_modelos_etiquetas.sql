-- =================================================================================
-- MIGRATION 013: Modelos de Chamados <-> Etiquetas
-- Data: 2026-05-20
-- =================================================================================

-- ─────────────────────────────────────────────────────────────────────────────
-- Tabela de relacionamento muitos-para-muitos entre Modelos e Etiquetas
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.chamado_modelos_etiquetas_rel (
    modelo_id INT NOT NULL REFERENCES public.chamado_modelos(id) ON DELETE CASCADE,
    etiqueta_id INT NOT NULL REFERENCES public.chamado_etiquetas(id) ON DELETE CASCADE,
    PRIMARY KEY (modelo_id, etiqueta_id)
);

CREATE INDEX IF NOT EXISTS idx_chamado_modelos_etiquetas_modelo ON public.chamado_modelos_etiquetas_rel(modelo_id);
