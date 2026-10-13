# Estado das correcoes

## Aplicado no primeiro lote

- Build usa InventarioTI.spec e nao copia nem inclui .env.
- Recursos templates/static incluidos; uploads excluidos.
- Dependencias de execucao, desenvolvimento e build separadas.
- Conteudo de tres relatorios reais substituido por avisos; exemplo ficticio adicionado.
- Catalogo das migrations completo; nomes historicos preservados.

## Segundo lote

- README sincronizado com os arquivos atuais.
- Logica dos utilitarios movida para scripts/maintenance/. Wrappers na raiz permanecem por compatibilidade.
- Reescrita automatica de autorizacao desativada; audit_idor.py e somente leitura.
- strip_css.py simula por padrao, exige --apply e cria backup sem sobrescrita.
- Cinco testes isolados da logica dos utilitarios passaram no ambiente de revisao.
- Workflow de CI preparado para sintaxe, testes isolados e empacotamento Windows. O resultado do workflow deve ser verificado apos o commit.

## Ainda pendente

- Exclusao dos tres caminhos legados de TXT: a ferramenta exige confirmacoes individuais.
- Opcional: remover wrappers da raiz apos confirmar que nao ha uso dos caminhos antigos.
- Executar e corrigir a suite completa Flask em ambiente isolado.
- Executar a cadeia completa das migrations em PostgreSQL isolado, revisando SQL especifico do Supabase.
- Confirmar o resultado do build em CI e testar o executavel em maquina limpa, incluindo recursos e dependencias nativas.

Nenhuma migration foi executada em producao. Os relatorios antigos continuam no historico Git; sua limpeza exige autorizacao especifica e coordenacao com colaboradores. CI nao e auditoria de seguranca nem teste funcional completo da aplicacao.
