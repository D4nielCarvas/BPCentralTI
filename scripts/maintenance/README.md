# Utilitarios de manutencao

Execute os scripts revisados abaixo com Python. Eles resolvem os caminhos pela localizacao do arquivo, nao pelo diretorio atual.

## audit_idor.py

Substitui a antiga reescrita automatica de patch_idor.py por uma listagem AST somente leitura de funcoes get_* com argumento id_ativo em blueprints/celulares.py. Nao detecta todas as vulnerabilidades e nao corrige autorizacao. A antiga reescrita por regex foi aposentada porque nao validava o contexto da rota nem a seguranca da mudanca.

```bash
python scripts/maintenance/audit_idor.py
```

## strip_css.py

Simula por padrao. Exige exatamente um bloco style, ausencia de referencia previa a admin.css e existencia do CSS de destino. Antes de aplicar, confirme manualmente que o CSS externo contem todas as regras do bloco. A aplicacao grava backup sem sobrescrever backup anterior.

```bash
python scripts/maintenance/strip_css.py
python scripts/maintenance/strip_css.py --apply
```

Os wrappers na raiz permanecem apenas por compatibilidade e nao executam alteracoes ao serem importados. Os demais scripts antigos desta pasta nao foram auditados por esta revisao; nao os execute indiscriminadamente nem aponte credenciais de producao para diagnosticos.
