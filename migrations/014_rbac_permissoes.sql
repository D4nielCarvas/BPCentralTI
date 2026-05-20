-- =================================================================================
-- MIGRATION 014: Controle de Acesso Baseado em Perfis (RBAC)
-- Data: 2026-05-20
-- =================================================================================

-- 1. Criação da Tabela de Perfis de Acesso
CREATE TABLE IF NOT EXISTS public.perfis_acesso (
    id SERIAL PRIMARY KEY,
    nome VARCHAR(100) NOT NULL UNIQUE,
    is_admin_master BOOLEAN NOT NULL DEFAULT FALSE,
    permissoes JSONB NOT NULL DEFAULT '{}'::jsonb,
    criado_em TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    atualizado_em TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 2. Inserção dos Perfis Padrão (Baseados nos papéis antigos)
INSERT INTO public.perfis_acesso (nome, is_admin_master, permissoes)
VALUES 
    ('Administrador TI', TRUE, '{"acesso_total": true}'::jsonb),
    ('Gestor da Fazenda (Viewer)', FALSE, '{"ver_telefones": true, "anexar_termos": true}'::jsonb),
    ('Apoio Inspeção', FALSE, '{"acesso_celulares_inspecao": true}'::jsonb)
ON CONFLICT (nome) DO NOTHING;

-- 3. Adição da coluna perfil_id na tabela usuarios
ALTER TABLE public.usuarios 
ADD COLUMN IF NOT EXISTS perfil_id INT REFERENCES public.perfis_acesso(id) ON DELETE SET NULL;

-- 4. Atualizar os usuários existentes para os novos perfis baseado no campo 'role'
UPDATE public.usuarios 
SET perfil_id = (SELECT id FROM public.perfis_acesso WHERE nome = 'Administrador TI')
WHERE role = 'admin' AND perfil_id IS NULL;

UPDATE public.usuarios 
SET perfil_id = (SELECT id FROM public.perfis_acesso WHERE nome = 'Gestor da Fazenda (Viewer)')
WHERE role = 'viewer' AND perfil_id IS NULL;

UPDATE public.usuarios 
SET perfil_id = (SELECT id FROM public.perfis_acesso WHERE nome = 'Apoio Inspeção')
WHERE role = 'apoio' AND perfil_id IS NULL;

-- (Opcional) Podemos tornar perfil_id NOT NULL no futuro após garantir que todos foram migrados
-- ALTER TABLE public.usuarios ALTER COLUMN perfil_id SET NOT NULL;
