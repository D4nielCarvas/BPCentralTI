# BP Central TI — v3.0

Sistema web interno da Branco Peres Agronegocios para centralizar inventario de ativos, pedidos, chamados e operacoes de TI entre unidades e fazendas. Backend Flask, interface Jinja2 e PostgreSQL no Supabase.

## Funcionalidades

Inventario de computadores, celulares, impressoras, dispositivos de protecao eletrica e Starlink; estoque e toners; pedidos, chamados, manutencoes, remessas, transferencias, descartes, historico, dashboard, chips, tutoriais e QR codes. Os contratos e permissoes de cada funcionalidade devem ser consultados nos blueprints e testes.

Endereco informado pelo projeto: https://inventario-ti-v3.onrender.com. Disponibilidade e configuracao dependem do ambiente de deploy.

## Estrutura

```text
BPCentralTI/
├── app.py                     # Inicializacao Flask e registro de blueprints
├── blueprints/                # Rotas web e APIs
├── services/
├── handlers/
├── utils/                     # Banco, autenticacao, criptografia e IDs
├── templates/                 # Interface Jinja2
├── static/                    # Recursos estaticos
├── migrations/                # SQL historico e catalogo completo
├── scripts/
│   ├── COLETAR_PC.bat
│   ├── build_exe.py            # Usa InventarioTI.spec
│   └── maintenance/           # Utilitarios e instrucoes
├── tests/                     # Suite da aplicacao
├── checks/                    # Testes isolados de manutencao
├── examples/                  # Inventario ficticio
├── docs/                      # Estado das correcoes
├── .github/workflows/         # Validacao sintatica, utilitarios e build
├── requirements.txt           # Execucao
├── requirements-dev.txt       # Desenvolvimento e testes
├── requirements-build.txt     # Empacotamento
├── InventarioTI.spec           # Fonte unica do build
├── render.yaml
├── build.sh
├── Procfile
├── pytest.ini
├── .env.example
├── .gitignore
├── .gitattributes
├── patch_idor.py               # Wrapper legado: diagnostico somente leitura
├── strip_css.py                # Wrapper legado: simulacao por padrao
└── README.md
```

A arvore e resumida. app.py cria database/termos/ em execucao; o diretorio nao precisa existir no clone.

## Instalacao local

Use Python 3.10+; o deploy versionado declara Python 3.11.0. Acesso ao banco preparado e dependencias nativas podem ser necessarios.

```bash
git clone https://github.com/D4nielCarvas/BPCentralTI.git
cd BPCentralTI
python -m venv .venv
```

Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
Copy-Item .env.example .env
```

Windows CMD:

```bat
.venv\Scripts\activate.bat
copy .env.example .env
```

Linux/macOS:

```bash
source .venv/bin/activate
cp .env.example .env
```

Preencha o .env e prepare o schema antes de iniciar:

```bash
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python app.py
```

A aplicacao abre http://localhost:5000 e usa bind 0.0.0.0, podendo aceitar conexoes da rede conforme o firewall. Nao exponha o servidor local diretamente a internet. Windows usa python-magic-bin; demais plataformas usam python-magic e precisam de libmagic instalada no sistema.

## Variaveis de ambiente

| Variavel | Uso |
|---|---|
| SUPABASE_DATABASE_URL | Conexao PostgreSQL; obrigatoria na inicializacao |
| SECRET_KEY | Assinatura das sessoes; obrigatoria na inicializacao |
| FERNET_KEY | Criptografia de campos sensiveis; preserve a chave para recuperar os dados |
| SUPABASE_URL, SUPABASE_KEY | Funcionalidades de Storage; configure permissoes adequadas |
| FLASK_ENV | production fora do desenvolvimento; o tratamento de erros consulta este valor |
| SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD | Recuperacao de senha por e-mail |

```bash
python -c "import secrets; print(secrets.token_hex(32))"
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Copie o modelo .env.example sem remove-lo do repositorio. Nunca publique credenciais ou entregue chaves privilegiadas do Supabase ao navegador ou a usuarios finais.

## Banco de dados

O catalogo completo e a sequencia documental estao em migrations/README.md. Nao existe supabase_migration.sql na raiz. Os nomes historicos, incluindo prefixos 010 e 014 duplicados, foram preservados; identifique cada migration pelo nome completo. Para scripts novos, use timestamp UTC unico conforme o catalogo.

Nao reaplique toda a pasta em uma base existente. Faca backup, registre as migrations ja aplicadas e valide as pendentes em PostgreSQL isolado. A cadeia completa ainda nao foi executada nesta revisao. Nenhuma alteracao foi aplicada ao banco de producao.

## Deploy

render.yaml declara build ./build.sh e inicializacao:

```bash
gunicorn app:app --workers 1 --threads 2 --bind 0.0.0.0:$PORT --timeout 120
```

Configure as variaveis no painel do provedor, incluindo Storage e SMTP quando utilizados. Deploy automatico depende do painel do Render. O rate limiter usa memoria; revise o armazenamento antes de aumentar processos. Confirme a persistencia dos arquivos locais de termos e a estrategia de Storage antes de depender de uploads em producao.

## IDs e coleta

A geracao de IDs fica em utils/id_generator.py. Use as siglas definidas no modulo, maiusculas e sem acentos:

```text
TIPO-LOCAL-SETOR-ID
NT-TNG-FT-01
IMP-CEN-ADM-02
```

Valide as restricoes de hostname antes de aplicar o ID ao sistema operacional. O coletor Windows fica em scripts/COLETAR_PC.bat; o fluxo descrito pelo projeto e importar o TXT em Computadores → Importar Coleta. O exemplo de demonstracao esta em examples/inventario_ficticio.txt.

Os tres relatorios reais tiveram o conteudo substituido por avisos. Seus caminhos legados ainda aguardam exclusao; dados antigos continuam no historico Git. A limpeza do historico nao foi realizada. Novas coletas sao ignoradas pelo Git; nao force sua inclusao.

## Testes e validacao

Suite da aplicacao:

```bash
python -m pip install -r requirements-dev.txt
python -m pytest
```

pytest.ini descobre tests/ e exclui tests/scratch/. Revise conftest.py e as dependencias externas; nunca use a base de producao para testes. A suite completa ainda nao foi executada nesta revisao.

Testes isolados dos utilitarios, sem Flask ou banco:

```bash
python -m unittest discover -s checks -v
```

Cinco testes da logica dos novos utilitarios passaram no ambiente de revisao. Isso nao valida a aplicacao inteira. O workflow Repository checks executa validacao sintatica, esses testes e empacotamento Windows; consulte seu resultado antes de declarar o build aprovado. O workflow nao executa migrations, suite Flask completa nem teste funcional do executavel.

## Build Windows

```bash
python -m pip install -r requirements-build.txt
python scripts/build_exe.py
```

Saida esperada: dist/InventarioTI/InventarioTI.exe, em modo onedir. O script utiliza InventarioTI.spec, que inclui templates e static, excluindo uploads e arquivos locais de ambiente. Modulos internos sao descobertos pelos arquivos Python das pastas do projeto.

O .env nao e copiado nem empacotado. O script bloqueia a distribuicao se encontrar arquivos de ambiente na saida. Configure credenciais no destino e nao entregue um pacote com segredos a usuarios finais. O empacotamento em CI nao substitui um teste em maquina limpa nem verifica o acesso ao banco.

## Manutencao e seguranca

Consulte scripts/maintenance/README.md. A antiga reescrita de autorizacao por regex foi aposentada: audit_idor.py apenas lista funcoes para revisao e nao certifica protecao contra IDOR. strip_css.py simula por padrao; --apply exige verificacoes e grava backup. Wrappers legados na raiz preservam compatibilidade, sem efeitos ao importar. Os demais scripts antigos nao foram auditados integralmente.

O codigo inclui autenticacao, criptografia, pool de conexoes, rate limiting e tratamento de erros. Isso nao equivale a auditoria completa de autorizacao, isolamento por localidade ou uploads. O estado das correcoes e limitacoes esta em docs/correcoes-repositorio.md.

## Contribuicao

Crie uma branch, preserve a separacao entre rotas e servicos, documente variaveis e migrations, execute os testes aplicaveis em ambiente isolado e abra um Pull Request com os resultados. A licenca deve ser definida pelo titular; nenhuma licenca foi presumida nesta revisao.

Revisao: 13 de outubro de 2026. Sem acesso ao banco de producao ou reescrita do historico Git.
