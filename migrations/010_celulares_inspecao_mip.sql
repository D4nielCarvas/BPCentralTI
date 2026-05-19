-- ============================================================
--  010_celulares_inspecao_mip.sql
--  Adiciona campos usuario_mip e senha_mip na tabela
--  celulares_inspecao para credenciais do sistema MIP.
--
--  Execute no SQL Editor do Supabase antes de reiniciar a app.
-- ============================================================

ALTER TABLE celulares_inspecao
    ADD COLUMN IF NOT EXISTS usuario_mip TEXT,
    ADD COLUMN IF NOT EXISTS senha_mip   TEXT;

COMMENT ON COLUMN celulares_inspecao.usuario_mip IS 'Usuário de acesso ao sistema MIP.';
COMMENT ON COLUMN celulares_inspecao.senha_mip   IS 'Senha de acesso ao sistema MIP.';
