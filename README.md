# BP Central TI — v3.0

Sistema web interno da Branco Peres Agronegócios para centralizar inventário de ativos, pedidos, chamados e operações de TI entre unidades e fazendas. Desenvolvido com Flask e PostgreSQL no Supabase.

## Sumário

- [Visão geral](#visão-geral)
- [Arquitetura e estrutura](#arquitetura-e-estrutura)
- [Execução local](#execução-local)
- [Variáveis de ambiente](#variáveis-de-ambiente)
- [Banco de dados](#banco-de-dados)
- [Deploy no Render](#deploy-no-render)
- [Nomenclatura e coleta de hardware](#nomenclatura-e-coleta-de-hardware)
- [APIs](#apis)
- [Testes](#testes)
- [Empacotamento para Windows](#empacotamento-para-windows)
- [Segurança e manutenção](#segurança-e-manutenção)
- [Contribuição](#contribuição)

## Visão geral

O projeto reúne inventário de computadores, celulares, impressoras, dispositivos de proteção elétrica e Starlink; estoque e toners; pedidos; manutenções; transferências; descartes; histórico e dashboard. O backend também registra módulos de autenticação, operação por fazenda, chamados, remessas, chips, tutoriais e QR codes.

Endereço informado pelo projeto: https://inventario-ti-v3.onrender.com. A disponibilidade do serviço e a configuração do ambiente devem ser verificadas pelo responsável pelo deploy.

## Arquitetura e estrutura

O navegador acessa páginas Jinja2 e APIs Flask. `app.py` configura a aplicação, inicializa o pool PostgreSQL e registra os blueprints. Os utilitários de banco, autenticação, criptografia e geração de IDs ficam em `utils/`, não na raiz.

```text
BPCentralTI/
├── app.py                  # Inicialização Flask e registro dos blueprints
├── blueprints/             # Rotas web e APIs por funcionalidade
├── handlers/
├── services/
├── utils/                  # Banco, autenticação, criptografia e IDs
│   ├── db_layer.py
│   ├── auth_utils.py
│   ├── crypto_utils.py
│   └── id_generator.py
├── templates/              # Interface Jinja2
├── static/                 # Recursos estáticos
├── migrations/             # Evolução do schema PostgreSQL
├── scripts/                # Coleta, build, seeds e manutenção
│   ├── COLETAR_PC.bat
│   ├── build_exe.py
│   └── maintenance/
├── tests/
│   ├── conftest.py
│   ├── test_inventario.py
│   └── scratch/            # Diagnósticos excluídos da descoberta padrão
├── .env.example
├── .gitignore
├── .gitattributes
├── requirements.txt
├── pytest.ini
├── render.yaml
├── build.sh
├── Procfile
├── InventarioTI.spec
├── patch_idor.py
├── strip_css.py
└── README.md
```

Na execução, `app.py` cria `database/termos/` para arquivos locais de termos; esse diretório não precisa existir no clone. A estrutura acima é resumida, não uma listagem de todos os arquivos.

Stack: Python, Flask, Jinja2, psycopg2, python-dotenv, cryptography, Flask-Limiter, python-magic e fpdf2. O deploy usa Gunicorn; o empacotamento opcional usa PyInstaller. As dependências estão em `requirements.txt`.

## Execução local

Pré-requisitos: Python 3.10+ (o Blueprint do Render declara 3.11.0), acesso a um banco PostgreSQL preparado e bibliotecas nativas necessárias ao `python-magic` no sistema operacional. A instalação das dependências e a execução não foram validadas em todos os sistemas.

```bash
git clone https://github.com/D4nielCarvas/BPCentralTI.git
cd BPCentralTI
python -m venv .venv
```

Ative o ambiente conforme o terminal:

```powershell
# Windows PowerShell
.\.venv\Scripts\Activate.ps1
Copy-Item .env.example .env
```

```bat
:: Windows CMD
.venv\Scripts\activate.bat
copy .env.example .env
```

```bash
# Linux/macOS
source .venv/bin/activate
cp .env.example .env
```

Instale as dependências, preencha o `.env` e prepare o banco antes de iniciar:

```bash
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python app.py
```

A aplicação abre o navegador em `http://localhost:5000`. O servidor local está configurado com `debug=False` e bind `0.0.0.0`, podendo aceitar conexões de outras máquinas conforme a rede e o firewall. Não exponha essa execução local diretamente à internet.

## Variáveis de ambiente

Copie `.env.example`; não renomeie ou remova o modelo versionado.

| Variável | Uso |
|---|---|
| `SUPABASE_DATABASE_URL` | Conexão PostgreSQL; exigida na inicialização |
| `SECRET_KEY` | Assinatura das sessões Flask; exigida na inicialização |
| `FERNET_KEY` | Chave para criptografia de campos sensíveis, conforme o modelo de ambiente |
| `SUPABASE_URL` | URL do projeto para funcionalidades de Storage |
| `SUPABASE_KEY` | Credencial de acesso ao Supabase Storage; permissões devem corresponder às políticas configuradas |
| `FLASK_ENV` | Use `production` no ambiente de produção; o tratamento de erros consulta esta variável |
| `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD` | Configuração de e-mail para recuperação de senha |

Gere as chaves e coloque os valores no `.env` ou no painel do provedor:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Não publique credenciais. Guarde a `FERNET_KEY` com segurança: perder a chave compromete a recuperação dos campos criptografados. Uma chave privilegiada de serviço do Supabase não deve ser enviada ao navegador nem distribuída aos usuários finais.

## Banco de dados

Os scripts SQL estão em `migrations/`. Não há `supabase_migration.sql` na raiz na estrutura revisada.

A sequência inicial é `v1_initial.sql`, `v2_add_campos.sql`, `v3_starlink.sql` e `v4_pedidos.sql`. Depois existem migrations numeradas de `005` a `024`, incluindo alterações de usuários, chamados, notificações, permissões, arquivos, tutoriais, chips e equipamentos.

Atenção: existem dois arquivos com prefixo `010` e dois com prefixo `014`; `migrations/README.md` documenta apenas as quatro versões iniciais. Antes de preparar uma base nova, revise as dependências e defina a ordem dos arquivos com prefixos iguais. Não trate uma ordenação alfabética como garantia de execução correta.

Use o SQL Editor do Supabase para aplicar scripts revisados em uma base de desenvolvimento. Para um banco existente, identifique quais mudanças já foram aplicadas e não execute novamente toda a pasta indiscriminadamente. Faça backup antes de alterações em produção. Esta revisão documental não valida a execução integral das migrations.

## Deploy no Render

A configuração versionada em `render.yaml` declara:

- Build: `./build.sh`.
- Inicialização: `gunicorn app:app --workers 1 --threads 2 --bind 0.0.0.0:$PORT --timeout 120`.
- Python: `3.11.0`.
- `SECRET_KEY`, `SUPABASE_DATABASE_URL` e `FERNET_KEY`: valores configurados manualmente.
- `FLASK_ENV=production`.

Configure também as variáveis de Storage e SMTP quando essas funcionalidades forem usadas. O deploy automático e a branch acompanhada dependem das configurações efetivas no painel do Render.

O rate limiter de `app.py` usa armazenamento em memória. Revise essa configuração antes de ampliar o número de processos. O aplicativo também cria um diretório local para termos: confirme onde cada tipo de arquivo é armazenado e a estratégia de persistência antes de depender de uploads em produção.

## Nomenclatura e coleta de hardware

A geração de IDs fica em `utils/id_generator.py`. O padrão de inventário é:

```text
TIPO-LOCAL-SETOR-ID
NT-TNG-FT-01
IMP-CEN-ADM-02
CL-SL2-COO-04
DK-SFR-ALP-01
```

Use as siglas de tipo, local e setor definidas no módulo (`SIGLAS_TIPO`, `SIGLAS_LOCAL` e `SIGLAS_SETOR`), mantendo letras maiúsculas e sem acentos. Valide as restrições de hostname no ambiente antes de aplicar o identificador ao sistema operacional.

O coletor Windows fica em `scripts/COLETAR_PC.bat`. O fluxo descrito pelo projeto é executar o coletor na máquina, selecionar o TXT em Computadores → Importar Coleta e informar o identificador do ativo. Revise o conteúdo dos relatórios antes de compartilhar: dados de hardware e rede podem identificar equipamentos internos.

## APIs

As rotas são distribuídas pelos blueprints registrados em `app.py`, incluindo ativos, estoque, pedidos, manutenções, chips, dashboard, descartes, transferências, histórico, importação/exportação, busca, tutoriais e QR codes.

Os decorators e os contratos de cada blueprint são a referência para métodos HTTP, caminhos, payloads e permissões. Não presuma que todos os módulos implementam o mesmo CRUD. Para uma documentação completa da API, catalogue as rotas e seus contratos em documento próprio ou especificação OpenAPI, validando-os contra o código e os testes.

## Testes

O `pytest.ini` descobre testes em `tests/` e exclui `tests/scratch/`. O pytest não está listado em `requirements.txt`; instale-o no ambiente de desenvolvimento:

```bash
python -m pip install pytest
python -m pytest
```

Para executar somente os testes de inventário:

```bash
python -m pytest tests/test_inventario.py -v
```

Revise `tests/conftest.py` e os testes selecionados para identificar mocks, credenciais e dependências externas antes de executá-los. Use uma base de testes separada de produção quando houver acesso ao banco. Esta atualização do README não representa execução ou aprovação da suíte.

## Empacotamento para Windows

Execute a partir da raiz:

```bash
python -m pip install pyinstaller==6.11.1
python scripts/build_exe.py
```

O caminho esperado pelo script é `dist/InventarioTI/InventarioTI.exe`, em distribuição `onedir`.

Aviso: o script atual copia automaticamente o `.env` da raiz para a pasta de distribuição quando ele existe. Embora isso não seja o mesmo que embutir o arquivo no binário, a distribuição resultante pode conter credenciais reais. Não distribua esse pacote sem revisar e remover segredos. Para usuários finais, priorize o acesso web.

O script também mantém hidden imports antigos (`id_generator` e `db_layer`, sem o prefixo `utils`) e declara explicitamente apenas `templates` como dados. Revise o empacotamento dos módulos e dos recursos estáticos e faça um teste do pacote em máquina limpa antes de considerar o executável pronto. `InventarioTI.spec` também está versionado; alinhe os dois caminhos de build antes de padronizar a distribuição.

## Segurança e manutenção

O código de inicialização inclui exigência de `SECRET_KEY`, pool de conexões, utilitários de autenticação e criptografia, rate limiting e tratamento de erros que oculta o traceback fora de desenvolvimento. Isso não substitui uma auditoria de autorização, isolamento por localidade, uploads e gestão de segredos.

Pendências identificadas na revisão estática:

- Atualizar o catálogo e padronizar a identificação das migrations sem alterar o histórico aplicado de forma indiscriminada.
- Revisar os TXT de inventário versionados em `scripts/`; substituir exemplos reais por dados fictícios quando necessário.
- Avaliar mover scripts pontuais da raiz, como `patch_idor.py` e `strip_css.py`, para `scripts/maintenance/`, ajustando os caminhos envolvidos.
- Separar dependências de desenvolvimento e build das dependências de execução.
- Revisar o build Windows, principalmente a cópia automática de credenciais e a inclusão de recursos.
- A raiz revisada não contém `.github/`, `LICENSE`, `CONTRIBUTING.md` ou `SECURITY.md`. Avaliar CI e documentação de contribuição e segurança; a licença deve ser definida pelo titular do projeto, não presumida.

## Contribuição

1. Crie uma branch: `git checkout -b feature/minha-feature`.
2. Preserve a separação entre rotas, serviços e utilitários.
3. Documente novas variáveis, migrations e mudanças de comportamento.
4. Execute os testes aplicáveis em ambiente isolado.
5. Abra um Pull Request descrevendo alterações e validações realizadas.

Revisão documental: 13 de outubro de 2026. Análise estática dos arquivos consultados; sem execução de testes, migrations, build ou validação do serviço em produção.
