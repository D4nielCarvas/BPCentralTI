-- 018_fix_chips_status.sql
-- Normaliza os valores de status da tabela linhas_celular
-- para corresponder ao padrão exibido na UI (português legível).

BEGIN;

-- Normaliza os dados existentes migrados com valor padrão antigo
UPDATE public.linhas_celular SET status = 'Em Uso'      WHERE status = 'EM_USO';
UPDATE public.linhas_celular SET status = 'Disponível'  WHERE status = 'DISPONIVEL';
UPDATE public.linhas_celular SET status = 'Perdido'     WHERE status = 'PERDIDO';
UPDATE public.linhas_celular SET status = 'Cancelado'   WHERE status = 'CANCELADO';

-- Corrige o DEFAULT da coluna para o novo padrão
ALTER TABLE public.linhas_celular
    ALTER COLUMN status SET DEFAULT 'Em Uso';

COMMIT;
