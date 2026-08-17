-- 023_reconcile_chips_estoque.sql
-- Reconciliação do status dos chips (linhas_celular) e atribuições ativas:
-- 1. Encerra atribuições ativas de celulares que estão no Estoque ou Descartados.
-- 2. Limpa o número de aparelhos que estão no Estoque ou Descartados.
-- 3. Atualiza o status de chips órfãos para 'Disponível'.

BEGIN;

-- 1. Encerra atribuições de ativos que estão no Estoque ou Descartados
UPDATE public.atribuicoes_linha
SET data_devolucao = NOW()
WHERE data_devolucao IS NULL
  AND id_ativo IN (
      SELECT id_ativo FROM public.celulares WHERE status IN ('Estoque', 'Descartado')
  );

-- 2. Limpa o campo numero na tabela de celulares para ativos que estão em Estoque ou Descartados
UPDATE public.celulares
SET numero = NULL
WHERE status IN ('Estoque', 'Descartado') AND numero IS NOT NULL;

-- 3. Marca como 'Disponível' qualquer chip que não tenha atribuição ativa aberta
UPDATE public.linhas_celular
SET status = 'Disponível'
WHERE id NOT IN (
    SELECT linha_id FROM public.atribuicoes_linha WHERE data_devolucao IS NULL
) AND status = 'Em Uso';

COMMIT;
