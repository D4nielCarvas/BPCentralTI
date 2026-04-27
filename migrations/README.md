# migrations/README.md
# Histórico de Migrações SQL — Supabase (PostgreSQL)

Execute as migrations em ordem crescente de versão no SQL Editor do Supabase:

| Arquivo            | Descrição                          |
|--------------------|-------------------------------------|
| v1_initial.sql     | Schema inicial completo             |
| v2_add_campos.sql  | Adição de campos extras             |
| v3_starlink.sql    | Tabela e campos Starlink            |
| v4_pedidos.sql     | Módulo de pedidos e nota fiscal     |

> Sempre faça backup antes de executar uma nova migration em produção.
