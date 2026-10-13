# Correcoes de seguranca e organizacao

## Primeiro lote

- Build usa InventarioTI.spec como fonte unica; nao copia nem empacota .env.
- Spec inclui templates e static, excluindo static/uploads e arquivos locais de ambiente.
- Modulos internos sao descobertos pelos arquivos Python em blueprints, utils, services e handlers, evitando nomes antigos sem prefixo utils.
- Dependencias de testes e build ficam em requirements-dev.txt e requirements-build.txt.
- Windows usa python-magic-bin; demais plataformas usam python-magic e precisam da biblioteca nativa libmagic.
- Relatorios reais foram substituidos por avisos e foi adicionado um exemplo ficticio. Os nomes legados e o historico Git ainda existem.
- Catalogo de migrations identifica todos os arquivos e distingue prefixos duplicados sem renomear o historico.

## Comandos atualizados

```bash
python -m pip install -r requirements-dev.txt
python -m pytest
```

Build em Windows:

```bash
python -m pip install -r requirements-build.txt
python scripts/build_exe.py
```

## Limitacoes e proximo lote

O README principal ainda descreve pendencias anteriores; esta nota registra o primeiro lote ate sua sincronizacao final. Scripts patch_idor.py e strip_css.py ainda precisam ser reorganizados com verificacoes de seguranca. Os tres caminhos legados de relatorios precisam ser excluidos; substituir o conteudo nao apaga commits anteriores. A limpeza de historico necessita autorizacao especifica e coordenacao com colaboradores.

Nao foram executados o build Windows, a suite Flask nem as migrations em PostgreSQL. Valide o binario em maquina limpa, os recursos estaticos e as dependencias nativas antes de distribuir. Configuracoes e credenciais reais devem permanecer no ambiente do servidor, nunca em um pacote entregue a usuarios finais.
