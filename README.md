# 🖥️ Inventário TI — v3.0

> Sistema de gerenciamento e inventário de ativos de TI para empresas agrícolas, desenvolvido com **Flask + Supabase (PostgreSQL)** e interface web integrada.

---

## 📋 Sumário

- [Visão Geral](#-visão-geral)
- [Arquitetura do Sistema](#-arquitetura-do-sistema)
- [Estrutura de Arquivos](#-estrutura-de-arquivos)
- [Pré-requisitos](#-pré-requisitos)
- [Instalação e Configuração](#-instalação-e-configuração)
- [Variáveis de Ambiente](#-variáveis-de-ambiente)
- [Banco de Dados](#-banco-de-dados)
- [Padronização de Nomenclatura de TI](#-padronização-de-nomenclatura-de-ti)
- [Módulos do Sistema](#-módulos-do-sistema)
- [API REST — Referência Completa](#-api-rest--referência-completa)
- [Coleta Automática via BAT](#-coleta-automática-via-bat)
- [Build para Executável (.exe)](#-build-para-executável-exe)
- [Testes](#-testes)
- [Fluxos de Uso Principais](#-fluxos-de-uso-principais)
- [Segurança e Boas Práticas](#-segurança-e-boas-práticas)

---

## 🎯 Visão Geral

O **Inventário TI v3** é uma aplicação web local (desktop-like) que centraliza o controle de todos os equipamentos de TI distribuídos entre fazendas e setores. O sistema roda como um servidor Flask local, abrindo automaticamente o navegador, e persiste os dados no **Supabase (PostgreSQL)** na nuvem.

### Funcionalidades principais

| Módulo | Descrição |
|---|---|
| **Celulares** | Cadastro, edição e rastreamento de smartphones corporativos |
| **Celulares de Ponto** | Controle de celulares usados para registro de ponto por turma/função |
| **Computadores / Notebooks** | Inventário completo com specs de hardware e OS |
| **Impressoras** | Gestão de impressoras com IP de rede e suprimentos |
| **Estabilizadores / Nobreaks** | Controle de dispositivos de proteção elétrica |
| **Starlink** | Cadastro de antenas com MAC address e plano de internet |
| **Estoque** | Estoque geral de acessórios e peças com movimentações |
| **Toners** | Controle de toners com alertas de estoque mínimo |
| **Manutenções** | Abertura e acompanhamento de ordens de serviço |
| **Descartes** | Registro de baixa patrimonial de ativos |
| **Transferências** | Movimentação de ativos entre responsáveis/fazendas |
| **Pedidos** | Registro de pedidos feitos pelos funcionario |
| **Histórico** | Auditoria de todas as operações realizadas |
| **Dashboard** | Painel com estatísticas gerais e atividade recente |
| **Coleta Automática** | Importação de dados de hardware via script `.bat` |

---

## 🏗️ Arquitetura do Sistema

```text
┌──────────────────────────────────────────────────────────┐
│                     Navegador (Frontend)                  │
│              templates/index.html (HTML/JS)               │
└─────────────────────────┬────────────────────────────────┘
                          │ HTTP (localhost:5000)
┌─────────────────────────▼────────────────────────────────┐
│                    Flask Backend (app.py)                  │
│  ┌──────────────┐  ┌──────────────┐  ┌────────────────┐  │
│  │  REST API    │  │ id_generator │  │ Upload de PDFs │  │
│  │  (rotas)     │  │   .py        │  │  (termos)      │  │
│  └──────────────┘  └──────────────┘  └────────────────┘  │
└─────────────────────────┬────────────────────────────────┘
                          │ psycopg2 (SSL)
┌─────────────────────────▼────────────────────────────────┐
│               Supabase — PostgreSQL (nuvem)                │
│  celulares | computadores | impressoras | manutencoes     │
│  estoque | toners | transferencias | historico | ...      │
└──────────────────────────────────────────────────────────┘
```

**Stack tecnológico:**
- **Backend:** Python 3.10+ · Flask · psycopg2-binary
- **Banco:** Supabase (PostgreSQL 15+)
- **Frontend:** HTML5 · JavaScript (Vanilla) · servido pelo Flask
- **Empacotamento:** PyInstaller (`.exe` para distribuição interna)
- **Automação:** Script `.bat` para coleta de dados de hardware no Windows

---

## 📁 Estrutura de Arquivos

```text
inventario-ti-v3/
│
├── app.py                  # Backend Flask — inicialização e rotas gerais do frontend
├── db_layer.py             # Camada de banco de dados e pool de conexões PostgreSQL
├── id_generator.py         # Geração de IDs padronizados (TIPO-LOCAL-SETOR-ID)
├── auth_utils.py           # Segurança, criptografia e controle de acesso multi-tenant
├── requirements.txt        # Dependências Python do projeto
├── pytest.ini              # Configuração do framework Pytest
├── .env.example            # Modelo de configuração de variáveis de ambiente
├── .gitignore              # Arquivos e pastas ignorados pelo Git
├── InventarioTI.spec       # Spec do PyInstaller para geração do executável (.exe)
│
├── blueprints/             # Módulos de controle separados por funcionalidade (Flask Blueprints)
│   ├── auth.py             # Login, logout e controle de permissões
│   ├── admin.py            # Dashboard e administração geral do sistema
│   ├── celulares.py        # Gestão de smartphones corporativos e de ponto
│   └── ...                 # Demais módulos segmentados (fazendas, chamados, pedidos)
│
├── templates/              # Arquivos HTML da interface (Jinja2 Templates por módulo)
│   ├── admin/              # Telas administrativas
│   ├── fazenda/            # Telas operacionais das fazendas (estoque, pedidos, etc.)
│   └── ...                 # Telas de suporte, apoio e autenticação
│
├── static/                 # Recursos estáticos do frontend (CSS, JS, uploads de imagens)
│
├── database/               # Armazenamento de termos PDF e dados locais do sistema
│
├── migrations/             # Histórico de alterações e scripts DDL do banco (PostgreSQL)
│
├── scripts/                # Scripts utilitários de automação e carga de dados
│   ├── COLETAR_PC.bat      # Script Windows para inventário automático de hardware
│   ├── build_exe.py        # Script para empacotamento em arquivo executável (.exe)
│   ├── seed_localidades.py # Popular base de dados com localidades oficiais e primeiro admin
│   └── maintenance/        # Scripts de diagnóstico e manutenção periódica do banco
│
└── tests/                  # Suíte de testes automatizados e interativos
    ├── test_inventario.py  # Testes de integração de lógica de negócio e regras
    └── scratch/            # Rascunhos de testes interativos e diagnósticos pontuais
```


---

## ✅ Pré-requisitos

- **Python 3.10+** instalado
- **Conta no [Supabase](https://supabase.com)** (plano gratuito funciona)
- **pip** atualizado (`python -m pip install --upgrade pip`)
- Sistema operacional: Windows, Linux ou macOS

---

## 🚀 Instalação e Configuração

### 1. Clone o repositório

```bash
git clone https://github.com/D4nielCarvas/inventario-ti-v3.git
cd inventario-ti-v3
```

### 2. Crie e ative um ambiente virtual

```bash
# Windows
python -m venv venv
venv\Scripts\activate

# Linux / macOS
python -m venv venv
source venv/bin/activate
```

### 3. Instale as dependências

```bash
pip install -r requirements.txt
```

### 4. Configure as variáveis de ambiente

```bash
# Copie o arquivo de exemplo
cp .env.example .env

# Edite o .env com a URL do seu projeto Supabase
```

### 5. Execute a migration no Supabase

No painel do Supabase, vá em **SQL Editor** e execute o conteúdo de `supabase_migration.sql`. Isso criará todas as tabelas necessárias.

### 6. Inicie a aplicação

```bash
python app.py
```

O sistema iniciará em `http://localhost:5000` e abrirá o navegador automaticamente.

---

## 🔐 Variáveis de Ambiente

Renomeie `.env.example` para `.env` e preencha:

```env
# String de conexão direta com o PostgreSQL do Supabase
# Formato: postgresql://postgres:[PASSWORD]@db.[PROJECT-REF].supabase.co:5432/postgres
SUPABASE_DATABASE_URL=postgresql://postgres:SUA_SENHA@db.XXXXXXXXXXXX.supabase.co:5432/postgres
```

> ⚠️ **Nunca commite o arquivo `.env`** com credenciais reais. Ele já está listado no `.gitignore`.

---

## 🗄️ Banco de Dados

O arquivo `supabase_migration.sql` contém o schema completo. As tabelas criadas são: `celulares`, `celulares_ponto`, `computadores`, `impressoras`, `estabilizadores`, `starlink`, `estoque`, `estoque_movimentacoes`, `toners`, `toner_trocas`, `manutencoes`, `descartes`, `transferencias` e `historico`.

---

## 🔤 Padronização de Nomenclatura de TI

O sistema utiliza e gera automaticamente (via `id_generator.py`) IDs semânticos que seguem o **Guia de Padronização de Nomenclatura de TI**. O nome de cada equipamento deve seguir rigorosamente a seguinte ordem, separados por hífens:

### Estrutura do Nome (Hostname)

```text
TIPO-LOCAL-SETOR-ID
```

- **TIPO**: Sigla do tipo de equipamento (2 a 3 letras).
- **LOCAL**: Sigla da fazenda ou unidade (2 a 4 letras).
- **SETOR**: Sigla do departamento (2 a 3 letras).
- **ID**: Número sequencial do equipamento naquele setor (01, 02...).

### Tabelas de Siglas Oficiais

#### A. Tipos de Equipamento
| Equipamento | Sigla |
|---|---|
| Desktop (Computador de Mesa) | `DK` |
| Notebook | `NT` |
| Celular / Smartphone | `CL` |
| Impressora | `IMP` |
| Tablet | `TB` |

#### B. Localidades (Fazendas e Unidades)
| Localidade | Sigla | Localidade | Sigla |
|---|---|---|---|
| Central | `CEN` | Santa Eliza | `SEL` |
| São Manoel | `SMN` | Santa Lucia | `SLU` |
| Tangará | `TNG` | Santa Lucia 2 | `SL2` |
| São Pedro | `SPD` | Caroline | `CLN` |
| São Judas | `SJU` | São João | `SJO` |
| São Francisco | `SFR` | Santa Luzia | `SLZ` |
| Santana | `STN` | Santa Adelina | `SAD` |
| CD | `CD` | | |

#### C. Setores
| Setor | Sigla | Setor | Sigla |
|---|---|---|---|
| Fito | `FT` | Colheita | `COL` |
| Almoxarifado Peças | `ALP` | Ponto | `PTO` |
| Almoxarifado Insumos | `ALI` | Turma | `TRM` |
| Coordenador | `COO` | Abastecimento | `ABS` |
| Administrativo | `ADM` | Irrigação | `IRR` |
| Apoio | `APO` | Agricola | `AGR` |
| Sestr | `STR` | Líderes | `LDR` |
| COA |  `COA` | CD | `CDP` |

### Exemplos Práticos de Aplicação
1. Notebook da Fazenda Tangará do setor de Fito, equipamento número 01: `NT-TNG-FT-01`
2. Impressora da Central do setor ADM, equipamento número 02: `IMP-CEN-ADM-02`
3. Celular da Santa Lucia 2 do Coordenador, equipamento número 04: `CL-SL2-COO-04`
4. Desktop da São Francisco do Almoxarifado Peças, equipamento número 01: `DK-SFR-ALP-01`

### Regras Importantes
- **Sem Acentos**: Nunca utilize acentos ou cedilha (ex: use `SJO` para São João).
- **Maiúsculas**: Todos os nomes devem ser escritos em letras MAIÚSCULAS.
- **Limite NetBIOS**: Tente manter o nome total abaixo de 15 caracteres para garantir compatibilidade com todos os sistemas Windows.
- **Etiquetagem**: Ao configurar o nome no sistema, imprima uma etiqueta física com o mesmo código e cole em local visível no aparelho.

---

## 🧩 Módulos do Sistema

### `app.py` — Backend Principal
O coração da aplicação. Contém rotas da API REST organizadas por módulo, contexto de conexão `get_db()` com PostgreSQL, lógica de negócio e inicialização automática do navegador via `threading`.

### `id_generator.py` — Gerador de IDs
Módulo responsável por aplicar a padronização oficial. Ele consulta o banco de dados para encontrar o próximo sequencial disponível para uma determinada combinação de prefixo e retorna o ID final pronto para uso.

---

## 🌐 API REST — Referência Completa

Base URL: `http://localhost:5000`

### Equipamentos (padrão CRUD)
Todos os módulos de equipamento (`/api/computadores`, `/api/celulares`, `/api/impressoras`, etc.) seguem o mesmo padrão:
- `GET /api/{modulo}?status=Ativo&q=busca` — Lista com filtros
- `POST /api/{modulo}` — Cadastra novo
- `GET /api/{modulo}/{id_ativo}` — Retorna dados
- `PUT /api/{modulo}/{id_ativo}` — Atualiza dados

### Outros Endpoints Importantes
- **Dashboard**: `GET /api/dashboard`
- **Movimentar Estoque**: `POST /api/estoque/{id}/movimentar`
- **Troca de Toner**: `POST /api/toners/{id}/troca`
- **Transferências**: `POST /api/transferencias`
- **Descartes**: `POST /api/descartes`
- **Gerar ID**: `GET /api/utils/gerar-id?tipo=NT&local=CEN&setor=ADM`
- **Upload Termos PDF**: `POST /api/upload_termo/{tipo}/{id_ativo}`

---

## 🤖 Coleta Automática via BAT

O `COLETAR_PC.bat` automatiza a coleta de dados de hardware no Windows via WMI, gerando um arquivo `.txt` estruturado (Processador, RAM, Armazenamento, SO, MAC, etc.).

**Fluxo de importação:**
1. Execute `COLETAR_PC.bat` no PC alvo
2. No sistema: Computadores → Importar Coleta
3. Selecione o `.txt` e informe o novo Hostname ID
4. A API detecta se é uma inserção nova ou atualização via número de série.

---

## 📦 Build para Executável (.exe)

Para distribuir o sistema em máquinas sem Python:

```bash
python build_exe.py
```

O executável gerado estará em `dist/InventarioTI.exe`.
> ⚠️ O arquivo `.env` **não é embutido** no executável por segurança. Ele deve ser distribuído separadamente e colocado na mesma pasta do `.exe`.

---

## 🧪 Testes

Executar suite completa de integração (valida banco, rotas, regras de negócio):
```bash
python -m pytest test_inventario.py -v
```

---

## 🔄 Fluxos de Uso Principais

- **Cadastrar Equipamento**: Sugira o ID oficial automaticamente, preencha os dados e salve. O log será gravado.
- **Registrar Manutenção**: Crie uma OS vinculada ao ID do equipamento, altere status entre "Aberta", "Em Andamento" e "Concluída".
- **Transferências**: Mova ativos entre Fazendas/Setores ou devolva para o Estoque registrando o motivo e gerando rastreabilidade.

---

## 🔒 Segurança e Boas Práticas

- Uso de **Prepared statements** psycopg2 (`%s`) para evitar SQL Injection.
- **Variáveis de ambiente** isoladas em `.env`.
- Validação rígida (`secure_filename`) de uploads para evitar path traversal.

---

## 👨‍💻 Contribuindo

1. Crie uma branch: `git checkout -b feature/minha-feature`
2. Faça suas alterações seguindo o padrão do código existente
3. Execute os testes: `python -m pytest test_inventario.py -v`
4. Abra um Pull Request

---

*Documentação atualizada em Abril/2026 — Inventário TI v3.0*
