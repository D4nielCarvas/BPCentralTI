-- 017_linhas_celulares.sql
-- Desacopla o Número de Telefone da tabela de celulares e cria histórico de atribuição.

BEGIN;

-- 1. Criação das novas tabelas estruturais
CREATE TABLE IF NOT EXISTS public.funcionarios (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    nome VARCHAR(255) UNIQUE NOT NULL,
    status VARCHAR(20) DEFAULT 'ATIVO'
);

CREATE TABLE IF NOT EXISTS public.linhas_celular (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    numero VARCHAR(50) UNIQUE NOT NULL,
    status VARCHAR(20) DEFAULT 'EM_USO'
);

CREATE TABLE IF NOT EXISTS public.atribuicoes_linha (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    linha_id UUID REFERENCES public.linhas_celular(id),
    funcionario_id UUID REFERENCES public.funcionarios(id),
    id_ativo VARCHAR(100), -- Referência de qual aparelho o chip está inserido (FK lógica para celulares.id_ativo)
    data_inicio TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    data_devolucao TIMESTAMP WITH TIME ZONE
);

CREATE INDEX IF NOT EXISTS idx_atribuicoes_linha_atual ON public.atribuicoes_linha(linha_id) WHERE data_devolucao IS NULL;
CREATE INDEX IF NOT EXISTS idx_atribuicoes_id_ativo ON public.atribuicoes_linha(id_ativo) WHERE data_devolucao IS NULL;
CREATE INDEX IF NOT EXISTS idx_atribuicoes_funcionario ON public.atribuicoes_linha(funcionario_id);

-- ==========================================
-- INÍCIO DA EXTRAÇÃO DOS DADOS EXISTENTES
-- ==========================================

-- 2. Migrar nomes únicos (Responsáveis) que não estejam nulos/vazios
INSERT INTO public.funcionarios (nome)
SELECT DISTINCT TRIM(responsavel) 
FROM public.celulares 
WHERE responsavel IS NOT NULL AND TRIM(responsavel) != ''
ON CONFLICT (nome) DO NOTHING;

-- 3. Migrar números de linha únicos
INSERT INTO public.linhas_celular (numero)
SELECT DISTINCT TRIM(numero) 
FROM public.celulares 
WHERE numero IS NOT NULL AND TRIM(numero) != ''
ON CONFLICT (numero) DO NOTHING;

-- 4. Vincular Funcionário <-> Número (Gerando a Atribuição inicial)
INSERT INTO public.atribuicoes_linha (linha_id, funcionario_id, id_ativo, data_inicio)
SELECT 
    l.id AS linha_id,
    f.id AS funcionario_id,
    c.id_ativo,
    COALESCE(c.data_entrega::timestamp with time zone, CURRENT_TIMESTAMP) AS data_inicio
FROM public.celulares c
JOIN public.linhas_celular l ON TRIM(c.numero) = l.numero
JOIN public.funcionarios f ON TRIM(c.responsavel) = f.nome
WHERE c.numero IS NOT NULL AND c.numero != '' AND c.responsavel IS NOT NULL AND c.responsavel != '';

COMMIT;
