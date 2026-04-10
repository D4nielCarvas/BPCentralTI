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
- [Módulos do Sistema](#-módulos-do-sistema)
- [API REST — Referência Completa](#-api-rest--referência-completa)
- [Gerador de IDs de Ativos](#-gerador-de-ids-de-ativos)
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
| **Histórico** | Auditoria de todas as operações realizadas |
| **Dashboard** | Painel com estatísticas gerais e atividade recente |
| **Coleta Automática** | Importação de dados de hardware via script `.bat` |

---

## 🏗️ Arquitetura do Sistema

```
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

```
inventario-ti-v3/
│
├── app.py                  # Backend Flask — toda a lógica de negócio e API REST
├── id_generator.py         # Módulo de geração de IDs padronizados (TIPO-LOCAL-SETOR-NN)
├── build_exe.py            # Script de empacotamento com PyInstaller
├── check_db.py             # Utilitário de diagnóstico de conexão com banco
├── debug_schema.py         # Utilitário para inspecionar schema do banco
├── test.py                 # Testes unitários básicos
├── test_inventario.py      # Suite completa de testes de integração
│
├── supabase_migration.sql  # Script SQL para criação de todas as tabelas no Supabase
├── requirements.txt        # Dependências Python
├── .env.example            # Modelo de variáveis de ambiente
├── .gitignore              # Arquivos ignorados pelo Git
├── InventarioTI.spec       # Spec do PyInstaller para geração do .exe
├── COLETAR_PC.bat          # Script Windows para coleta automática de dados de hardware
│
└── templates/
    └── index.html          # Interface web completa (frontend single-page)
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

> Veja a seção [Variáveis de Ambiente](#-variáveis-de-ambiente) para detalhes.

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

**Como obter a URL:**
1. Acesse seu projeto no [Supabase Dashboard](https://app.supabase.com)
2. Vá em **Settings → Database**
3. Copie a **Connection String** (modo `URI`)
4. Substitua `[YOUR-PASSWORD]` pela senha do banco

---

## 🗄️ Banco de Dados

O arquivo `supabase_migration.sql` contém o schema completo. As tabelas criadas são:

| Tabela | Descrição |
|---|---|
| `celulares` | Smartphones corporativos |
| `celulares_ponto` | Celulares de registro de ponto |
| `computadores` | Desktops e notebooks |
| `impressoras` | Impressoras de rede e locais |
| `estabilizadores` | Estabilizadores e nobreaks |
| `starlink` | Antenas Starlink |
| `estoque` | Itens de estoque geral |
| `estoque_movimentacoes` | Entradas e saídas do estoque |
| `toners` | Toners de impressoras |
| `toner_trocas` | Histórico de trocas de toner |
| `manutencoes` | Ordens de serviço / manutenções |
| `descartes` | Baixas patrimoniais |
| `transferencias` | Movimentações de ativos |
| `historico` | Log de auditoria de todas as ações |

### Exemplo de estrutura — tabela `computadores`

```sql
id_ativo          VARCHAR  PRIMARY KEY   -- ex.: NT-CEN-ADM-01
fazenda           VARCHAR
setor             VARCHAR
responsavel       VARCHAR
tipo              VARCHAR               -- 'Notebook' ou 'Desktop'
modelo            VARCHAR
marca             VARCHAR
numero_serie      VARCHAR  UNIQUE
patrimonio        VARCHAR
processador       VARCHAR
memoria_ram       VARCHAR
armazenamento     VARCHAR
sistema_operacional VARCHAR
versao_so         VARCHAR
status            VARCHAR               -- 'Ativo', 'Estoque', 'Manutenção', 'Descartado'
data_aquisicao    DATE
data_entrega      DATE
data_devolucao    DATE
usuario_windows   VARCHAR
senha_windows     VARCHAR
usuario_anterior  VARCHAR
observacoes       TEXT
termo_assinado    BOOLEAN
termo_pdf         VARCHAR
created_at        TIMESTAMPTZ  DEFAULT NOW()
updated_at        TIMESTAMPTZ  DEFAULT NOW()
```

---

## 🧩 Módulos do Sistema

### `app.py` — Backend Principal

O coração da aplicação. Contém:

- **Configuração Flask** com suporte a PyInstaller (`resource_path`)
- **Context Manager `get_db()`** — gerencia conexões PostgreSQL com commit/rollback automático
- **Helpers internos** — `_fetch_all`, `_fetch_one`, `_list_table`, `log_historico`, `allowed_file`
- **Todas as rotas da API REST** organizadas por módulo de equipamento
- **Lógica de negócio** para transferências, descartes e coleta automática
- **Inicialização** com abertura automática do navegador via `threading`

**Padrão de conexão com o banco:**

```python
# Sempre use o context manager — nunca abra conexões manualmente
with get_db() as conn:
    with conn.cursor() as cur:
        cur.execute("SELECT * FROM computadores WHERE id_ativo = %s", (id_ativo,))
        resultado = cur.fetchone()
```

---

### `id_generator.py` — Gerador de IDs

Módulo responsável pela geração de identificadores únicos de ativos no padrão:

```
TIPO - LOCAL - SETOR - NN
 NT  -  CEN  -  ADM  - 01
```

#### Siglas disponíveis

**Tipos de equipamento (`SIGLAS_TIPO`):**

| Sigla | Equipamento |
|---|---|
| `DK` | Desktop |
| `NT` | Notebook |
| `CL` | Celular |
| `IMP` | Impressora |
| `TB` | Tablet |
| `EST` | Estabilizador |
| `STL` | Starlink |

**Localidades (`SIGLAS_LOCAL`):**

| Sigla | Local |
|---|---|
| `CEN` | Central |
| `SMN` | Simão Neto |
| `TNG` | Tangará |
| `SPD` | São Pedro |
| `SJU` | São Julião |
| `SFR` | São Francisco |
| `STN` | Santana |
| `CD` | Colônia Dom |
| `SEL` | Selva |
| `SLU` | São Luís |
| `SL2` | São Luís 2 |
| `CLN` | Colina |
| `SJO` | São José |
| `SLZ` | São Lazaro |
| `SAD` | Santo André |

**Setores (`SIGLAS_SETOR`):**

| Sigla | Setor |
|---|---|
| `FT` | Faturamento |
| `ALP` | Almoxarifado de Peças |
| `ALI` | Almoxarifado de Insumos |
| `COO` | Coordenação |
| `ADM` | Administrativo |
| `APO` | Apoio |
| `COL` | Colheita |
| `PTO` | Ponto |
| `TRM` | Transporte e Maquinário |
| `ABS` | Abastecimento |
| `IRR` | Irrigação |

#### Funções exportadas

```python
from id_generator import gerar_id_ativo, proximo_sequencial, sugerir_id

# Gera ID com sequencial informado manualmente
gerar_id_ativo("NT", "CEN", "ADM", 3)  # → "NT-CEN-ADM-03"

# Consulta o banco e retorna o próximo número disponível
seq = proximo_sequencial(cur, "NT", "CEN", "ADM")  # → 4 (se já existem 01, 02, 03)

# Combina as duas funções acima — use isso no dia a dia
sugerir_id(cur, "NT", "CEN", "ADM")  # → "NT-CEN-ADM-04"
```

---

### `COLETAR_PC.bat` — Coleta Automática de Hardware

Script Windows (`.bat`) que coleta automaticamente as especificações de hardware de um computador e gera um arquivo `.txt` no formato `chave=valor`. O arquivo gerado é então enviado para a API via `/api/importar_coleta`.

**Dados coletados:**
- Tipo (Desktop/Notebook)
- Marca e Modelo
- Número de série
- Processador
- Memória RAM
- Armazenamento
- Sistema Operacional e versão
- Usuário Windows logado
- IP de rede

**Uso:**
1. Execute `COLETAR_PC.bat` no computador alvo (Windows)
2. Um arquivo `.txt` será gerado
3. No sistema, vá em **Computadores → Importar Coleta**
4. Selecione o `.txt` gerado, informe o ID, fazenda e setor
5. O sistema cadastra ou atualiza automaticamente o registro

---

### `build_exe.py` — Build para Distribuição

Gera um executável `.exe` standalone usando PyInstaller para distribuição interna (sem necessidade de Python instalado nas máquinas).

```bash
python build_exe.py
```

O executável gerado estará em `dist/InventarioTI.exe`. Ao ser executado, inicia o servidor Flask e abre o navegador automaticamente.

> O arquivo `InventarioTI.spec` contém a configuração detalhada do PyInstaller, incluindo os arquivos de dados (templates) que precisam ser empacotados junto.

---

### `check_db.py` e `debug_schema.py` — Utilitários de Diagnóstico

Use esses scripts para verificar o estado da conexão e do schema do banco:

```bash
# Verifica se a conexão com o Supabase está funcionando
python check_db.py

# Exibe as tabelas e colunas existentes no banco
python debug_schema.py
```

---

## 🌐 API REST — Referência Completa

Base URL: `http://localhost:5000`

Todas as respostas seguem o padrão JSON. Endpoints de escrita retornam `{"ok": true, "msg": "..."}` ou `{"ok": false, "msg": "..."}` com o HTTP status adequado.

---

### Sistema

| Método | Endpoint | Descrição |
|---|---|---|
| `GET` | `/api/health` | Verifica conexão com o banco |
| `GET` | `/api/dashboard` | Estatísticas gerais e atividade recente |
| `GET` | `/api/busca?q={termo}` | Busca global em todos os equipamentos |
| `GET` | `/api/historico` | Últimas 500 entradas do log de auditoria |
| `GET` | `/api/historico/{id_ativo}` | Histórico de um ativo específico |
| `GET` | `/api/exportar/{tabela}` | Exporta tabela completa em CSV |

**Tabelas válidas para exportação:** `celulares`, `celulares_ponto`, `computadores`, `impressoras`, `estabilizadores`, `starlink`, `manutencoes`, `descartes`, `estoque`, `toners`, `transferencias`, `historico`

---

### Equipamentos (padrão CRUD)

Todos os módulos de equipamento seguem o mesmo padrão de rotas:

#### Exemplo: Computadores

```
GET    /api/computadores              → Lista com filtros (?status=Ativo&q=termo)
POST   /api/computadores              → Cadastra novo computador
GET    /api/computadores/{id_ativo}   → Retorna dados de um computador
PUT    /api/computadores/{id_ativo}   → Atualiza dados de um computador
```

O mesmo padrão se aplica a:
- `/api/celulares`
- `/api/celulares_ponto`
- `/api/impressoras`
- `/api/estabilizadores`
- `/api/starlink`

**Parâmetros de filtro (GET lista):**
- `?status=Ativo` — filtra por status (`Ativo`, `Estoque`, `Manutenção`, `Descartado`)
- `?q=termo` — busca textual por ID, responsável, modelo, etc.

**Exemplo de cadastro de computador (POST):**

```json
{
  "id_ativo": "NT-CEN-ADM-01",
  "fazenda": "Central",
  "setor": "Administrativo",
  "responsavel": "João Silva",
  "tipo": "Notebook",
  "modelo": "Inspiron 15",
  "marca": "Dell",
  "numero_serie": "ABC123XYZ",
  "processador": "Intel Core i5-11ª Geração",
  "memoria_ram": "8 GB",
  "armazenamento": "256 GB SSD",
  "sistema_operacional": "Windows",
  "versao_so": "Windows 11",
  "status": "Ativo"
}
```

---

### Estoque

```
GET  /api/estoque                          → Lista itens (?q=busca)
POST /api/estoque                          → Cadastra item
GET  /api/estoque/{id}                     → Retorna item
PUT  /api/estoque/{id}                     → Atualiza dados do item
POST /api/estoque/{id}/movimentar          → Entrada ou saída de quantidade
GET  /api/estoque/{id}/movimentacoes       → Histórico de movimentações
```

**Exemplo de movimentação:**

```json
// POST /api/estoque/5/movimentar
{
  "tipo": "entrada",         // ou "saida"
  "quantidade": 10,
  "motivo": "Compra NF 1234",
  "responsavel": "Daniel"
}
```

---

### Toners

```
GET  /api/toners                  → Lista toners (?q=busca)
POST /api/toners                  → Cadastra toner
GET  /api/toners/{id}             → Retorna toner
PUT  /api/toners/{id}             → Atualiza toner
POST /api/toners/{id}/troca       → Registra troca (debita estoque)
GET  /api/toners/{id}/trocas      → Histórico de trocas
```

> O Dashboard exibe automaticamente alertas quando `quantidade_estoque <= quantidade_minima`.

---

### Manutenções

```
GET  /api/manutencoes             → Lista (?status=Aberta&tipo=Computador&q=busca)
POST /api/manutencoes             → Registra nova manutenção
GET  /api/manutencoes/{id}        → Retorna manutenção
PUT  /api/manutencoes/{id}        → Atualiza manutenção
```

**Status possíveis:** `Aberta`, `Em Andamento`, `Aguardando Peça`, `Concluída`, `Cancelada`

---

### Descartes

```
GET  /api/descartes               → Lista todos os descartes
POST /api/descartes               → Registra descarte (atualiza status do ativo para 'Descartado')
```

---

### Transferências

```
POST /api/transferencias                          → Registra transferência
GET  /api/transferencias                          → Lista (?id_ativo=&tipo_equipamento=&data_inicio=&data_fim=)
GET  /api/transferencias/{id_ativo}/historico     → Histórico paginado (?page=1&per_page=20)
GET  /api/transferencias/estoque                  → Lista todos ativos com status 'Estoque'
```

**Tipos de transferência disponíveis:**
- `Usuario para Estoque` — devolução ao estoque (requer `data_devolucao`)
- `Estoque para Usuario` — entrega ao usuário (requer `responsavel_destino`)
- `Transferência entre Usuarios` — troca direta de responsável

**Exemplo de transferência para estoque:**

```json
// POST /api/transferencias
{
  "id_ativo": "NT-CEN-ADM-01",
  "tipo_equipamento": "Computador",
  "tipo_transferencia": "Usuario para Estoque",
  "responsavel_origem": "João Silva",
  "fazenda_origem": "Central",
  "setor_origem": "Administrativo",
  "data_devolucao": "2026-04-10",
  "motivo": "Funcionário desligado",
  "registrado_por": "Daniel TI"
}
```

---

### Upload de Termos PDF

```
POST /api/upload_termo/{tipo}/{id_ativo}   → Salva PDF de termo de responsabilidade
GET  /termos/{filename}                    → Serve o arquivo PDF
```

**Tipos válidos:** `celular`, `celular_ponto`, `computador`

O PDF é salvo em `database/termos/` com nome padronizado `{tipo}_{id_ativo}.pdf`.

---

### Gerador de ID e Utilitários

```
GET /api/utils/siglas              → Retorna dicionários de siglas válidas
GET /api/utils/gerar-id?tipo=NT&local=CEN&setor=ADM   → Sugere próximo ID disponível
POST /api/utils/parse-coleta       → Processa arquivo .txt da coleta e retorna campos mapeados
POST /api/importar_coleta          → Importa coleta completa e insere/atualiza computador no banco
GET  /api/siglas                   → Alias para /api/utils/siglas
GET  /api/gerar_id?tipo=NT&localidade=CEN&setor=ADM   → Alias para /api/utils/gerar-id
```

---

## 🖥️ Exemplo de Uso — Dashboard

Resposta de `GET /api/dashboard`:

```json
{
  "equipamentos": {
    "celulares":      { "total": 45, "ativos": 38 },
    "celulares_ponto":{ "total": 12, "ativos": 10 },
    "computadores":   { "total": 30, "ativos": 27 },
    "impressoras":    { "total": 8,  "ativos": 7  },
    "estabilizadores":{ "total": 15, "ativos": 14 },
    "starlink":       { "total": 5,  "ativos": 5  }
  },
  "manutencoes_abertas": 3,
  "descartes": 12,
  "toner_alerta": 2,
  "estoque_itens": 47,
  "atividade_recente": [
    {
      "id_ativo": "NT-CEN-ADM-05",
      "tipo_equipamento": "Computador",
      "acao": "Transferência: Estoque para Usuario → Maria Souza",
      "data_hora": "2026-04-10T14:30:00"
    }
  ]
}
```

---

## 🔢 Gerador de IDs de Ativos

O sistema utiliza IDs semânticos que codificam tipo, localização e setor diretamente no identificador, facilitando rastreamento visual.

### Lógica de geração

```
NT  -  CEN  -  ADM  -  03
│      │        │       └── Sequencial (auto-incremento por prefixo)
│      │        └────────── Setor (ADM = Administrativo)
│      └─────────────────── Localidade (CEN = Central)
└────────────────────────── Tipo (NT = Notebook)
```

O sequencial é calculado consultando o banco e encontrando o maior número existente para aquele prefixo `TIPO-LOCAL-SETOR-`, incrementando em 1. Se não houver registros, começa em `01`.

### Exemplo via API

```http
GET /api/utils/gerar-id?tipo=NT&local=CEN&setor=ADM
```

```json
{
  "ok": true,
  "id_sugerido": "NT-CEN-ADM-04"
}
```

---

## 🤖 Coleta Automática via BAT

O `COLETAR_PC.bat` automatiza a coleta de dados de hardware no Windows via WMI, gerando um arquivo `.txt` estruturado:

```ini
tipo=Notebook
marca=Dell
modelo=Inspiron 15 3501
num_serie=ABC123XYZ456
processador=Intel(R) Core(TM) i5-1135G7 @ 2.40GHz
memoria_ram=8192 MB
armazenamento=256 GB SSD
sistema_operacional=Windows 10 Pro
versao_so=10.0.19045
usuario=joao.silva
ip=192.168.1.105
```

### Fluxo de importação

```
Executar COLETAR_PC.bat no PC alvo
            ↓
    Arquivo .txt gerado
            ↓
  Sistema: Computadores → Importar Coleta
            ↓
  Selecionar .txt + informar ID + Fazenda + Setor
            ↓
  POST /api/importar_coleta
            ↓
  ┌─ Número de série já existe? ──► Atualiza specs técnicos
  └─ Novo equipamento? ──────────► Cadastro completo
```

> A API detecta automaticamente se é uma inserção nova ou atualização, baseando-se no `numero_serie` do equipamento.

---

## 📦 Build para Executável (.exe)

Para distribuir o sistema em máquinas sem Python:

```bash
python build_exe.py
```

Isso executa o PyInstaller com as configurações do `InventarioTI.spec`, gerando `dist/InventarioTI.exe`.

**O executável:**
- Inicia o servidor Flask automaticamente
- Abre o navegador em `http://localhost:5000`
- Inclui todos os templates e arquivos estáticos embutidos
- Requer apenas o arquivo `.env` na mesma pasta com as credenciais do banco

> ⚠️ O arquivo `.env` **não é embutido** no executável por segurança. Ele deve ser distribuído separadamente e colocado na mesma pasta do `.exe`.

---

## 🧪 Testes

### Executar suite completa

```bash
python -m pytest test_inventario.py -v
```

### Executar teste básico de conexão

```bash
python test.py
```

### O que é testado (`test_inventario.py`)

- Conexão com o banco (`/api/health`)
- CRUD completo de cada módulo (celulares, computadores, impressoras, etc.)
- Geração e validação de IDs
- Movimentação de estoque (entrada/saída com validação de saldo)
- Fluxo completo de transferências
- Registro e consulta de manutenções
- Exportação CSV
- Busca global

---

## 🔄 Fluxos de Uso Principais

### Cadastrar novo notebook

1. Acesse o sistema em `http://localhost:5000`
2. Menu → **Computadores** → **+ Novo**
3. Clique em **Sugerir ID** para gerar automaticamente
4. Preencha: Fazenda, Setor, Responsável, Modelo, Marca, etc.
5. Salvar → registro criado e log de auditoria gerado

### Registrar manutenção

1. Menu → **Manutenções** → **+ Nova Manutenção**
2. Informe o ID do ativo e tipo do equipamento
3. Descreva o problema relatado
4. Status inicial: `Aberta`
5. Quando resolvido, edite e mude para `Concluída` com solução aplicada

### Transferir ativo entre fazendas

1. Menu → **Transferências** → **+ Nova Transferência**
2. Selecione o tipo: `Transferência entre Usuarios`
3. Informe: ativo, origem (responsável/fazenda/setor), destino
4. Confirmar → ativo atualizado e histórico registrado

### Controle de toners

1. Menu → **Toners** → configure `quantidade_minima` por toner
2. O Dashboard exibe alertas quando o estoque atinge o mínimo
3. Ao trocar um toner: **Registrar Troca** debita do estoque automaticamente

---

## 🔒 Segurança e Boas Práticas

### Pontos implementados
- **Variáveis de ambiente** para credenciais (nunca hardcoded)
- **`secure_filename`** no upload de PDFs (previne path traversal)
- **Validação de extensão** — somente `.pdf` aceito no upload
- **Prepared statements** via psycopg2 (`%s`) — prevenção de SQL Injection
- **Validação de tabelas** no endpoint de exportação (whitelist)
- **Rollback automático** em caso de exceção nas transações
- **Falha rápida** — `app.py` aborta na inicialização se `SUPABASE_DATABASE_URL` não estiver definido

### Pontos de atenção para produção

> ⚠️ O sistema foi projetado para uso em **rede local interna**. Para exposição externa, considere:

- Adicionar autenticação (ex.: Flask-Login ou token JWT)
- Habilitar HTTPS (certificado SSL)
- Remover `debug=False` já está correto — manter assim
- Restringir `host="0.0.0.0"` para `host="127.0.0.1"` se não precisar de acesso por rede local
- Revisar permissões de usuário no Supabase (Row Level Security)
- Os campos `senha_windows` e `senha` são armazenados em texto puro — considere criptografia para ambientes sensíveis

---

## 👨‍💻 Contribuindo

1. Crie uma branch: `git checkout -b feature/minha-feature`
2. Faça suas alterações seguindo o padrão do código existente
3. Execute os testes: `python -m pytest test_inventario.py -v`
4. Abra um Pull Request com descrição clara da mudança

---

## 📄 Licença

Projeto de uso interno. Entre em contato com o autor para informações sobre licenciamento.

---

*Documentação gerada em Abril/2026 — Inventário TI v3.0*
