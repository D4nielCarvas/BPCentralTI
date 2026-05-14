-- =================================================================================
-- MIGRATION 006: Email de usuario + tabela de tokens de recuperacao de senha
-- Data: 2026-05-12
-- Execute no SQL Editor do Supabase antes de reiniciar o sistema
-- =================================================================================

-- ─────────────────────────────────────────────────────────────────────────────
-- 1. Email na tabela de usuarios
-- ─────────────────────────────────────────────────────────────────────────────
ALTER TABLE public.usuarios
    ADD COLUMN IF NOT EXISTS email VARCHAR(120) UNIQUE;

CREATE INDEX IF NOT EXISTS idx_usuarios_email ON public.usuarios(email);


-- ─────────────────────────────────────────────────────────────────────────────
-- 2. Tabela de tokens de recuperacao de senha
--    - token: gerado com secrets.token_urlsafe(32) no backend
--    - expira_em: NOW() + 1 hora no momento da criacao
--    - usado: marcado TRUE apos uso; tokens usados sao ignorados
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.password_reset_tokens (
    id          SERIAL      PRIMARY KEY,
    usuario_id  BIGINT      NOT NULL REFERENCES public.usuarios(id) ON DELETE CASCADE,
    token       VARCHAR(100) UNIQUE NOT NULL,
    expira_em   TIMESTAMPTZ NOT NULL,
    usado       BOOLEAN     NOT NULL DEFAULT FALSE,
    criado_em   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_reset_tokens_token      ON public.password_reset_tokens(token);
CREATE INDEX IF NOT EXISTS idx_reset_tokens_usuario    ON public.password_reset_tokens(usuario_id);
CREATE INDEX IF NOT EXISTS idx_reset_tokens_expira     ON public.password_reset_tokens(expira_em);

ALTER TABLE public.password_reset_tokens DISABLE ROW LEVEL SECURITY;


-- ─────────────────────────────────────────────────────────────────────────────
-- Verificacao pos-execucao
-- ─────────────────────────────────────────────────────────────────────────────
-- SELECT column_name FROM information_schema.columns
--   WHERE table_name = 'usuarios' AND column_name = 'email';
-- SELECT table_name FROM information_schema.tables
--   WHERE table_name = 'password_reset_tokens';
