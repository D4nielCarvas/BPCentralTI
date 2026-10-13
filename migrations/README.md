# Catalogo de migrations PostgreSQL

Os nomes historicos dos SQL foram preservados. O identificador completo abaixo, nao apenas o prefixo numerico, distingue cada migration. A tabela estabelece a sequencia documental; nao e um executor automatico nem prova de que uma base vazia reproduz o schema de producao.

| ID unico | Arquivo | Finalidade |
|---|---|---|
| v1_initial | v1_initial.sql | Tabelas iniciais e indices |
| v2_add_campos | v2_add_campos.sql | Celulares de inspecao, pedidos e campos adicionais |
| v3_starlink | v3_starlink.sql | Apesar do nome historico, adiciona tipo_suprimento em toners |
| v4_pedidos | v4_pedidos.sql | Celulares de turma, campos Starlink e pedidos |
| 005_multi_tenant | 005_multi_tenant.sql | Localidades, usuarios e pedidos viewer |
| 006_email_reset_token | 006_email_reset_token.sql | E-mail e recuperacao de senha |
| 007_etiquetas | 007_etiquetas.sql | Etiquetas |
| 008_chamados | 008_chamados.sql | Chamados |
| 009_manutencoes_usuario_id | 009_manutencoes_usuario_id.sql | Vinculo de manutencoes com usuario |
| 010_celulares_inspecao_mip | 010_celulares_inspecao_mip.sql | Campos de credenciais MIP em celulares_inspecao |
| 010_remessas_equipamentos | 010_remessas_equipamentos.sql | Remessas vinculadas a chamados, localidades e usuarios |
| 011_celulares_inspecao_drop_numero | 011_celulares_inspecao_drop_numero.sql | Remocao de campo numero |
| 012_notificacoes | 012_notificacoes.sql | Notificacoes |
| 013_modelos_etiquetas | 013_modelos_etiquetas.sql | Modelos de etiquetas |
| 014_rbac_permissoes | 014_rbac_permissoes.sql | Perfis e permissoes; depende de usuarios |
| 014_movimentacao_equipamentos | 014_movimentacao_equipamentos.sql | Datas de movimentacao; depende de chamados |
| 015_arquivos_storage | 015_arquivos_storage.sql | Arquivos e Storage |
| 016_tutoriais | 016_tutoriais.sql | Tutoriais |
| 017_linhas_celulares | 017_linhas_celulares.sql | Linhas celulares |
| 018_fix_chips_status | 018_fix_chips_status.sql | Ajuste de status de chips |
| 019_ativos_arquivados | 019_ativos_arquivados.sql | Arquivamento de ativos |
| 020_seq_id_lock | 020_seq_id_lock.sql | Controle de sequenciais |
| 021_fix_transferencias | 021_fix_transferencias.sql | Ajustes de transferencias |
| 022_manutencoes_pecas | 022_manutencoes_pecas.sql | Pecas de manutencao |
| 023_reconcile_chips_estoque | 023_reconcile_chips_estoque.sql | Reconciliacao entre chips e estoque |
| 024_add_apelido_equipamentos | 024_add_apelido_equipamentos.sql | Apelidos de equipamentos |

## Prefixos historicos duplicados

Os dois arquivos 010 nao dependem um do outro: o MIP exige celulares_inspecao, criada em v2; remessas exige chamados (008), localidades e usuarios (005). Os dois arquivos 014 tambem trabalham em objetos distintos: RBAC depende de usuarios e movimentacao depende de chamados. A ordem acima resolve a ambiguidade documental desses pares sem renomear scripts publicados.

Antes de cada execucao, revise o SQL e o schema existente. As finalidades dos arquivos nao inspecionados integralmente foram resumidas pelos nomes; valide o contrato real no SQL. A cadeia completa ainda requer teste em PostgreSQL isolado.

## Procedimento seguro

1. Faca backup do banco existente.
2. Registre os identificadores completos ja aplicados; nao deduza isso pelo numero do prefixo.
3. Teste os scripts pendentes em uma copia isolada.
4. Revise dependencias, alteracoes destrutivas, constraints, dados e politicas de acesso.
5. Aplique apenas scripts pendentes e guarde data, responsavel e resultado.

Nao reaplique a pasta inteira em producao. IF NOT EXISTS nao torna todas as operacoes inofensivas. Nao renumere migrations ja aplicadas para disfarcar duplicidade.

## Convencao para novas migrations

Use YYYYMMDDHHMMSS_descricao.sql com timestamp UTC unico. Nao edite SQL historico aplicado: publique uma nova migration corretiva. Atualize este catalogo e inclua testes e instrucoes de rollback quando viaveis.
