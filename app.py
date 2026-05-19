"""
Inventário TI — Backend Flask v3.0
Banco: Supabase (PostgreSQL) via psycopg2-binary
Autor: Sistema Inventário TI
"""

from __future__ import annotations

import csv
import io
import os
import sys
import threading
import webbrowser
from datetime import date, datetime, timedelta
from typing import Any, Optional

import psycopg2
import psycopg2.extras
from dotenv import load_dotenv
from flask import (Flask, Response, jsonify, redirect, render_template,
                   request, send_from_directory, session, url_for)
from werkzeug.utils import secure_filename

# ── Camada de banco com pooling ───────────────────────────────────────────────
from db_layer import acquire_conn, fetch_all, fetch_one, init_pool, close_pool
# Mantém get_db como alias para rotas ainda não migradas
get_db = acquire_conn
_fetch_all = fetch_all
_fetch_one = fetch_one

# ── Importações dos módulos internos ──────────────────────────────────────────
from id_generator import (
    gerar_id_ativo, proximo_sequencial, sugerir_id,
    gerar_id_turma, proximo_sequencial_turma, sugerir_id_turma,
    SIGLAS_TIPO, SIGLAS_LOCAL, SIGLAS_SETOR,
)

# ── Dicts inversos: nome completo → sigla (para regen de ID após transferência) ─
FAZENDA_PARA_SIGLA: dict[str, str] = {v: k for k, v in SIGLAS_LOCAL.items()}
SETOR_PARA_SIGLA: dict[str, str]   = {v: k for k, v in SIGLAS_SETOR.items()}

# ── Carrega variáveis de ambiente ─────────────────────────────────────────────
load_dotenv()

# ── Utilitário PyInstaller ────────────────────────────────────────────────────

def resource_path(relative_path: str) -> str:
    """
    Retorna o caminho absoluto para um recurso, compatível com PyInstaller.

    Quando empacotado como .exe, o PyInstaller extrai arquivos para uma pasta
    temporária referenciada por sys._MEIPASS. Em desenvolvimento, usa o diretório
    do arquivo atual.

    Args:
        relative_path: Caminho relativo ao recurso desejado.

    Returns:
        Caminho absoluto resolvido para o ambiente de execução atual.
    """
    base_path: str = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_path, relative_path)


# ── Configuração da aplicação ─────────────────────────────────────────────────

app = Flask(__name__, template_folder=resource_path("templates"))

# SECRET_KEY obrigatória para sessões Flask (cookies assinados).
# Deve ser uma string aleatória longa em produção — lida do .env.
# Gere com: python -c "import secrets; print(secrets.token_hex(32))"
app.secret_key = os.environ.get("SECRET_KEY", "dev-inseguro-troque-em-producao")

if getattr(sys, "frozen", False):
    application_path = os.path.dirname(sys.executable)
else:
    application_path = os.path.dirname(os.path.abspath(__file__))

UPLOAD_FOLDER: str = os.path.join(application_path, "database", "termos")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

DATABASE_URL: str = os.environ["SUPABASE_DATABASE_URL"]  # falha rápido se ausente

# ── Inicializar pool e registrar blueprints ───────────────────────────────────
with app.app_context():
    init_pool(minconn=2, maxconn=10)

import atexit
atexit.register(close_pool)

# Blueprints existentes
from blueprints.celulares import celulares_bp
app.register_blueprint(celulares_bp)

# Blueprints do sistema multi-tenant (Tarefas 8-10)
from blueprints.auth import auth_bp
from blueprints.fazenda import fazenda_bp
from blueprints.admin_pedidos import admin_pedidos_bp
from blueprints.admin import admin_bp
from blueprints.chamados import chamados_bp
from blueprints.admin_chamados import admin_chamados_bp
from blueprints.apoio import apoio_bp

app.register_blueprint(auth_bp)
app.register_blueprint(fazenda_bp)
app.register_blueprint(admin_pedidos_bp)
app.register_blueprint(admin_bp)
app.register_blueprint(chamados_bp)
app.register_blueprint(admin_chamados_bp)
app.register_blueprint(apoio_bp)


# ── Filtro Jinja2: formata data em horário de Brasília (UTC-3) ────────────────
@app.template_filter('fdt')
def formata_data_br(dt):
    """Converte datetime UTC → BRT (UTC-3) e formata como dd/mm/aa HH:MM."""
    if not dt:
        return ''
    if isinstance(dt, str):
        try:
            dt = datetime.fromisoformat(dt.replace('Z', '+00:00'))
        except Exception:
            return dt[:16].replace('T', ' ')
    if dt.tzinfo is not None:
        # aware → converte para UTC e subtrai 3h
        import datetime as _dt
        utc = dt.utctimetuple()
        dt = datetime(*utc[:6])
    dt_local = dt - timedelta(hours=3)
    return dt_local.strftime('%d/%m/%y %H:%M')


# ── Conexão com banco de dados (delegado ao db_layer com pool) ───────────────
# get_db, _fetch_all, _fetch_one já importados acima via db_layer aliases.


# ── Helpers de resultado ──────────────────────────────────────────────────────

def row_to_dict(row: Optional[psycopg2.extras.RealDictRow]) -> Optional[dict]:
    """
    Converte uma linha RealDictRow em dicionário Python puro.

    Args:
        row: Linha retornada pelo cursor psycopg2 com RealDictCursor, ou None.

    Returns:
        Dicionário com os dados da linha, ou None se a entrada for None.
    """
    return dict(row) if row else None


def rows_to_list(rows: list[psycopg2.extras.RealDictRow]) -> list[dict]:
    """
    Converte uma lista de RealDictRow em lista de dicionários Python puros.

    Args:
        rows: Lista de linhas retornadas pelo cursor psycopg2.

    Returns:
        Lista de dicionários com os dados de cada linha.
    """
    return [dict(r) for r in rows]


def _fetch_all(cur: psycopg2.extensions.cursor, query: str, params: tuple = ()) -> list[dict]:
    """Executa query e retorna todos os resultados como lista de dicts."""
    cur.execute(query, params)
    return rows_to_list(cur.fetchall())


def _fetch_one(cur: psycopg2.extensions.cursor, query: str, params: tuple = ()) -> Optional[dict]:
    """Executa query e retorna o primeiro resultado como dict ou None."""
    cur.execute(query, params)
    return row_to_dict(cur.fetchone())


# ── Helper: log de histórico ──────────────────────────────────────────────────

def log_historico(
    cur: psycopg2.extensions.cursor,
    id_ativo: str,
    tipo: str,
    acao: str,
    campo: str = None,
    anterior: str = None,
    novo: str = None,
) -> None:
    """
    Registra uma ação no histórico de alterações.

    Args:
        cur: Cursor psycopg2 ativo (dentro de uma transação aberta).
        id_ativo: Identificador único do ativo afetado.
        tipo: Tipo do equipamento (ex.: 'Celular', 'Computador').
        acao: Descrição da ação realizada (ex.: 'Cadastro', 'Edição').
        campo: Campo alterado, se aplicável.
        anterior: Valor anterior do campo, se aplicável.
        novo: Novo valor do campo, se aplicável.
    """
    cur.execute(
        """INSERT INTO historico
           (id_ativo, tipo_equipamento, acao, campo_alterado, valor_anterior, valor_novo)
           VALUES (%s, %s, %s, %s, %s, %s)""",
        (id_ativo, tipo, acao, campo, anterior, novo),
    )


# ── Helper: validação de arquivo ──────────────────────────────────────────────

def allowed_file(filename: str) -> bool:
    """Verifica se o arquivo possui extensão PDF permitida."""
    return "." in filename and filename.rsplit(".", 1)[1].lower() == "pdf"


# ── Helper: listagem genérica ─────────────────────────────────────────────────

def _list_table(tabela: str, colunas_busca: list[str]) -> Response:
    """
    Retorna registros de uma tabela com suporte a filtro de status e busca textual.

    Substitui os placeholders ? (sqlite3) por %s (psycopg2) e usa ILIKE para
    busca case-insensitive no PostgreSQL.

    Args:
        tabela: Nome da tabela a consultar.
        colunas_busca: Lista de colunas onde a busca textual será aplicada.

    Returns:
        Resposta JSON com lista de registros.
    """
    filtro = request.args.get("status", "")
    busca = request.args.get("q", "")
    query = f"SELECT * FROM {tabela} WHERE 1=1"
    params: list[Any] = []

    if filtro:
        query += " AND status=%s"
        params.append(filtro)
    if busca:
        cond = " OR ".join([f"{c} ILIKE %s" for c in colunas_busca])
        query += f" AND ({cond})"
        params += [f"%{busca}%"] * len(colunas_busca)

    query += " ORDER BY id DESC"

    with get_db() as conn:
        with conn.cursor() as cur:
            rows = _fetch_all(cur, query, tuple(params))

    return jsonify(rows)


# ═══════════════════════════════════════════════════════════════════════════════
# FRONTEND
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/")
def index():
    """
    Rota raiz — redireciona com base no estado de autenticação e role.

    - Não autenticado → /login
    - Admin           → renderiza o painel principal (index.html)
    - Viewer          → /fazenda/itens (portal de fazenda)
    """
    if "usuario_id" not in session:
        return redirect(url_for("auth.login"))
    if session.get("role") == "viewer":
        return redirect(url_for("fazenda.listar_itens"))
    return render_template("index.html")


@app.route("/termos/<filename>")
def serve_termo(filename: str) -> tuple[str, int] | Response:
    """Serve arquivos PDF de termos de responsabilidade com tratamento de erro seguro."""
    file_path = os.path.join(UPLOAD_FOLDER, filename)
    if not os.path.exists(file_path):
        return (
            f"<h3>Arquivo não encontrado</h3>"
            f"<p>O PDF do termo de responsabilidade ({filename}) não está disponível no servidor no momento.</p>"
            f"<p>Isso pode ocorrer se o sistema foi reiniciado e o arquivo estava em armazenamento temporário.</p>",
            404,
        )
    try:
        return send_from_directory(UPLOAD_FOLDER, filename)
    except Exception:
        return "<h3>Erro ao acessar o arquivo PDF.</h3>", 404


# ═══════════════════════════════════════════════════════════════════════════════
# UPLOAD PDF
# ═══════════════════════════════════════════════════════════════════════════════

# ═══════════════════════════════════════════════════════════════════════════════
# ITEM 1 — BUSCA UNIFICADA DE ATIVO POR ID
# ═══════════════════════════════════════════════════════════════════════════════

# Tabelas pesquisadas em ordem de prioridade
_TABELAS_ATIVO_BUSCA: list[tuple[str, str]] = [
    ("celulares",          "Celular"),
    ("celulares_ponto",    "Celular Ponto"),
    ("celulares_inspecao", "Celular Inspeção"),
    ("celulares_turma",    "Celular Turma"),
    ("computadores",       "Computador"),
    ("impressoras",        "Impressora"),
    ("estabilizadores",    "Estabilizador"),
    ("starlink",           "Starlink"),
]


@app.route("/api/ativos/<id_ativo>")
def get_ativo_universal(id_ativo: str) -> tuple[Response, int] | Response:
    """
    Busca um ativo em todas as tabelas de equipamentos pelo ID.

    Usado pela aba de Manutenção para autopreenchimento de campos.
    Complexidade: O(k) onde k = número de tabelas (~8 queries no pior caso).

    Args:
        id_ativo: ID do ativo no padrão TIPO-LOCAL-SETOR-NN ou CL-TRM-NN.

    Returns:
        JSON com os dados do ativo + campo 'tipo_equipamento', ou 404.
    """
    with get_db() as conn:
        with conn.cursor() as cur:
            for tabela, tipo_nome in _TABELAS_ATIVO_BUSCA:
                row = _fetch_one(
                    cur,
                    f"SELECT * FROM {tabela} WHERE id_ativo=%s",
                    (id_ativo,),
                )
                if row:
                    row["tipo_equipamento"] = tipo_nome
                    return jsonify(row)

    return jsonify({"ok": False, "msg": f"Ativo '{id_ativo}' não encontrado"}), 404


@app.route("/api/upload_termo/<tipo>/<id_ativo>", methods=["POST"])
def upload_termo(tipo: str, id_ativo: str) -> tuple[Response, int] | Response:
    """
    Recebe e salva o PDF do termo de responsabilidade de um ativo.

    Atualiza o campo termo_pdf na tabela correspondente ao tipo informado.

    Args:
        tipo: Tipo do ativo ('celular', 'celular_ponto', 'computador').
        id_ativo: Identificador único do ativo.

    Returns:
        JSON com resultado da operação.
    """
    if "file" not in request.files:
        return jsonify({"ok": False, "msg": "Nenhum arquivo enviado"}), 400

    file = request.files["file"]
    if not file.filename or not allowed_file(file.filename):
        return jsonify({"ok": False, "msg": "Envie um arquivo PDF"}), 400

    safe_name = f"{tipo}_{secure_filename(id_ativo)}.pdf"
    file.save(os.path.join(UPLOAD_FOLDER, safe_name))

    tabela_map = {
        "celular": "celulares",
        "celular_ponto": "celulares_ponto",
        "celular_inspecao": "celulares_inspecao",
        "celular_turma": "celulares_turma",
        "computador": "computadores",
        "starlink": "starlink",
    }
    tabela = tabela_map.get(tipo)

    if tabela:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"UPDATE {tabela} SET termo_pdf=%s WHERE id_ativo=%s",
                    (safe_name, id_ativo),
                )
                log_historico(cur, id_ativo, tipo, "PDF Termo Anexado")
 
    return jsonify({"ok": True, "msg": "PDF anexado!", "filename": safe_name})


# ═══════════════════════════════════════════════════════════════════════════════
# SAUDE / DIAGNOSTICO
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/api/health")
def health_check() -> Response:
    """Verifica a conexão com o banco de dados."""
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
        return jsonify({"ok": True, "msg": "Conexão com Supabase OK", "database": DATABASE_URL.split('@')[-1]})
    except Exception as e:
        return jsonify({"ok": False, "msg": f"Erro de conexão: {str(e)}"}), 500

# ═══════════════════════════════════════════════════════════════════════════════
# DASHBOARD
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/api/dashboard")
def dashboard() -> Response:
    """Retorna estatísticas gerais para o painel principal."""
    with get_db() as conn:
        with conn.cursor() as cur:
            stats: dict[str, dict] = {}
            for tbl in [
                "celulares", "celulares_ponto", "celulares_inspecao",
                "celulares_turma",
                "computadores", "impressoras", "estabilizadores", "starlink",
            ]:
                cur.execute(f"SELECT COUNT(*) AS n FROM {tbl}")
                tot = cur.fetchone()["n"]
                cur.execute(f"SELECT COUNT(*) AS n FROM {tbl} WHERE status='Ativo'")
                atv = cur.fetchone()["n"]
                stats[tbl] = {"total": tot, "ativos": atv}

            cur.execute(
                "SELECT COUNT(*) AS n FROM manutencoes "
                "WHERE status NOT IN ('Concluída','Cancelada')"
            )
            man = cur.fetchone()["n"]

            cur.execute("SELECT COUNT(*) AS n FROM descartes")
            desc = cur.fetchone()["n"]

            cur.execute(
                "SELECT COUNT(*) AS n FROM toners "
                "WHERE quantidade_estoque <= quantidade_minima"
            )
            ton_alerta = cur.fetchone()["n"]

            cur.execute("SELECT COUNT(*) AS n FROM estoque")
            est_itens = cur.fetchone()["n"]

            cur.execute(
                "SELECT COUNT(*) AS n FROM pedidos "
                "WHERE status NOT IN ('Finalizado','Rejeitado')"
            )
            ped_abertos = cur.fetchone()["n"]

            recentes = _fetch_all(
                cur,
                "SELECT id_ativo,tipo_equipamento,acao,data_hora "
                "FROM historico ORDER BY id DESC LIMIT 10",
            )

    return jsonify(
        {
            "equipamentos": stats,
            "manutencoes_abertas": man,
            "descartes": desc,
            "toner_alerta": ton_alerta,
            "estoque_itens": est_itens,
            "pedidos_abertos": ped_abertos,
            "atividade_recente": recentes,
        }
    )


# ═══════════════════════════════════════════════════════════════════════════════
# CELULARES — migrado para blueprints/celulares.py (celulares_bp)
# ═══════════════════════════════════════════════════════════════════════════════


# CELULARES PONTO / INSPEÇÃO — migrados para blueprints/celulares.py


# ═══════════════════════════════════════════════════════════════════════════════
# COMPUTADORES
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/api/computadores", methods=["GET"])
def listar_computadores() -> Response:
    """Lista computadores/notebooks com filtros."""
    return _list_table("computadores", ["id_ativo", "responsavel", "modelo", "marca"])


@app.route("/api/computadores", methods=["POST"])
def criar_computador() -> tuple[Response, int] | Response:
    """Cadastra um novo computador ou notebook."""
    d = request.json
    with get_db() as conn:
        with conn.cursor() as cur:
            try:
                cur.execute(
                    """INSERT INTO computadores
                       (id_ativo,fazenda,setor,responsavel,tipo,modelo,marca,numero_serie,
                        patrimonio,processador,memoria_ram,armazenamento,sistema_operacional,
                        versao_so,status,data_aquisicao,data_entrega,data_devolucao,
                        usuario_windows,senha_windows,usuario_anterior,observacoes,termo_assinado,cargo)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                    (
                        d["id_ativo"], d.get("fazenda"), d.get("setor"), d.get("responsavel"),
                        d.get("tipo"), d.get("modelo"), d.get("marca"), d.get("numero_serie"),
                        d.get("patrimonio"), d.get("processador"), d.get("memoria_ram"),
                        d.get("armazenamento"), d.get("sistema_operacional"), d.get("versao_so"),
                        d.get("status", "Ativo"), d.get("data_aquisicao"), d.get("data_entrega"),
                        d.get("data_devolucao"), d.get("usuario_windows"), d.get("senha_windows"),
                        d.get("usuario_anterior"), d.get("observacoes"), d.get("termo_assinado"), d.get("cargo"),
                    ),
                )
                log_historico(cur, d["id_ativo"], "Computador", "Cadastro")
            except psycopg2.IntegrityError:
                return jsonify({"ok": False, "msg": "ID de ativo já existe!"}), 400
    return jsonify({"ok": True, "msg": "Computador cadastrado!"})


@app.route("/api/computadores/<id_ativo>", methods=["GET"])
def get_computador(id_ativo: str) -> Response:
    """Retorna dados de um computador pelo ID do ativo."""
    with get_db() as conn:
        with conn.cursor() as cur:
            row = _fetch_one(cur, "SELECT * FROM computadores WHERE id_ativo=%s", (id_ativo,))
    return jsonify(row)


@app.route("/api/computadores/<id_ativo>", methods=["PUT"])
def atualizar_computador(id_ativo: str) -> Response:
    """Atualiza dados de um computador existente."""
    d = request.json
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """UPDATE computadores SET
                   fazenda=%s,setor=%s,responsavel=%s,tipo=%s,modelo=%s,marca=%s,
                   numero_serie=%s,patrimonio=%s,processador=%s,memoria_ram=%s,
                   armazenamento=%s,sistema_operacional=%s,versao_so=%s,status=%s,
                   data_aquisicao=%s,data_entrega=%s,data_devolucao=%s,usuario_windows=%s,
                   senha_windows=%s,usuario_anterior=%s,observacoes=%s,termo_assinado=%s,
                   cargo=%s,updated_at=NOW() WHERE id_ativo=%s""",
                (
                    d.get("fazenda"), d.get("setor"), d.get("responsavel"), d.get("tipo"),
                    d.get("modelo"), d.get("marca"), d.get("numero_serie"), d.get("patrimonio"),
                    d.get("processador"), d.get("memoria_ram"), d.get("armazenamento"),
                    d.get("sistema_operacional"), d.get("versao_so"), d.get("status"),
                    d.get("data_aquisicao"), d.get("data_entrega"), d.get("data_devolucao"),
                    d.get("usuario_windows"), d.get("senha_windows"), d.get("usuario_anterior"),
                    d.get("observacoes"), d.get("termo_assinado"), d.get("cargo"), id_ativo,
                ),
            )
            log_historico(cur, id_ativo, "Computador", "Edição")
    return jsonify({"ok": True, "msg": "Computador atualizado!"})


# ═══════════════════════════════════════════════════════════════════════════════
# IMPRESSORAS
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/api/impressoras", methods=["GET"])
def listar_impressoras() -> Response:
    """Lista impressoras com filtros."""
    return _list_table("impressoras", ["id_ativo", "responsavel", "modelo", "marca"])


@app.route("/api/impressoras", methods=["POST"])
def criar_impressora() -> tuple[Response, int] | Response:
    """Cadastra uma nova impressora."""
    d = request.json
    with get_db() as conn:
        with conn.cursor() as cur:
            try:
                cur.execute(
                    """INSERT INTO impressoras
                       (id_ativo,fazenda,setor,responsavel,marca,modelo,tipo,numero_serie,
                        patrimonio,ip_rede,hostname,status,data_aquisicao,data_instalacao,
                        suprimento_atual,observacoes)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                    (
                        d["id_ativo"], d.get("fazenda"), d.get("setor"), d.get("responsavel"),
                        d.get("marca"), d.get("modelo"), d.get("tipo"), d.get("numero_serie"),
                        d.get("patrimonio"), d.get("ip_rede"), d.get("hostname"),
                        d.get("status", "Ativo"), d.get("data_aquisicao"), d.get("data_instalacao"),
                        d.get("suprimento_atual"), d.get("observacoes"),
                    ),
                )
                log_historico(cur, d["id_ativo"], "Impressora", "Cadastro")
            except psycopg2.IntegrityError:
                return jsonify({"ok": False, "msg": "ID de ativo já existe!"}), 400
    return jsonify({"ok": True, "msg": "Impressora cadastrada!"})


@app.route("/api/impressoras/<id_ativo>", methods=["GET"])
def get_impressora(id_ativo: str) -> Response:
    """Retorna dados de uma impressora."""
    with get_db() as conn:
        with conn.cursor() as cur:
            row = _fetch_one(cur, "SELECT * FROM impressoras WHERE id_ativo=%s", (id_ativo,))
    return jsonify(row)


@app.route("/api/impressoras/<id_ativo>", methods=["PUT"])
def atualizar_impressora(id_ativo: str) -> Response:
    """Atualiza dados de uma impressora."""
    d = request.json
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """UPDATE impressoras SET
                   fazenda=%s,setor=%s,responsavel=%s,marca=%s,modelo=%s,tipo=%s,
                   numero_serie=%s,patrimonio=%s,ip_rede=%s,hostname=%s,status=%s,
                   data_aquisicao=%s,data_instalacao=%s,suprimento_atual=%s,
                   observacoes=%s,updated_at=NOW() WHERE id_ativo=%s""",
                (
                    d.get("fazenda"), d.get("setor"), d.get("responsavel"), d.get("marca"),
                    d.get("modelo"), d.get("tipo"), d.get("numero_serie"), d.get("patrimonio"),
                    d.get("ip_rede"), d.get("hostname"), d.get("status"), d.get("data_aquisicao"),
                    d.get("data_instalacao"), d.get("suprimento_atual"), d.get("observacoes"),
                    id_ativo,
                ),
            )
            log_historico(cur, id_ativo, "Impressora", "Edição")
    return jsonify({"ok": True, "msg": "Impressora atualizada!"})


# ═══════════════════════════════════════════════════════════════════════════════
# ESTABILIZADORES
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/api/estabilizadores", methods=["GET"])
def listar_estabilizadores() -> Response:
    """Lista estabilizadores/nobreakes com filtros."""
    return _list_table("estabilizadores", ["id_ativo", "fazenda", "modelo", "setor"])


@app.route("/api/estabilizadores", methods=["POST"])
def criar_estabilizador() -> tuple[Response, int] | Response:
    """Cadastra um novo estabilizador ou nobreak."""
    d = request.json
    with get_db() as conn:
        with conn.cursor() as cur:
            try:
                cur.execute(
                    "INSERT INTO estabilizadores (id_ativo,fazenda,setor,modelo,status,uso,num_serie) "
                    "VALUES (%s,%s,%s,%s,%s,%s,%s)",
                    (
                        d["id_ativo"], d.get("fazenda"), d.get("setor"), d.get("modelo"),
                        d.get("status", "Ativo"), d.get("uso"), d.get("num_serie"),
                    ),
                )
                log_historico(cur, d["id_ativo"], "Estabilizador", "Cadastro")
            except psycopg2.IntegrityError:
                return jsonify({"ok": False, "msg": "ID de ativo já existe!"}), 400
    return jsonify({"ok": True, "msg": "Estabilizador cadastrado!"})


@app.route("/api/estabilizadores/<id_ativo>", methods=["GET"])
def get_estabilizador(id_ativo: str) -> Response:
    """Retorna dados de um estabilizador."""
    with get_db() as conn:
        with conn.cursor() as cur:
            row = _fetch_one(cur, "SELECT * FROM estabilizadores WHERE id_ativo=%s", (id_ativo,))
    return jsonify(row)


@app.route("/api/estabilizadores/<id_ativo>", methods=["PUT"])
def atualizar_estabilizador(id_ativo: str) -> Response:
    """Atualiza dados de um estabilizador."""
    d = request.json
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """UPDATE estabilizadores SET
                   fazenda=%s,setor=%s,modelo=%s,status=%s,uso=%s,num_serie=%s,
                   updated_at=NOW() WHERE id_ativo=%s""",
                (
                    d.get("fazenda"), d.get("setor"), d.get("modelo"), d.get("status"),
                    d.get("uso"), d.get("num_serie"), id_ativo,
                ),
            )
            log_historico(cur, id_ativo, "Estabilizador", "Edição")
    return jsonify({"ok": True, "msg": "Estabilizador atualizado!"})


# ═══════════════════════════════════════════════════════════════════════════════
# STARLINK
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/api/starlink", methods=["GET"])
def listar_starlink() -> Response:
    """Lista antenas Starlink com filtros."""
    return _list_table("starlink", ["id_ativo", "fazenda", "responsavel", "num_serie"])


@app.route("/api/starlink", methods=["POST"])
def criar_starlink() -> tuple[Response, int] | Response:
    """Cadastra uma nova antena Starlink. Item 7: inclui campos de login."""
    d = request.json
    with get_db() as conn:
        with conn.cursor() as cur:
            try:
                cur.execute(
                    """INSERT INTO starlink
                       (id_ativo,fazenda,setor,responsavel,modelo,num_serie,mac_address,
                        ip_rede,status,data_instalacao,data_aquisicao,plano,observacoes,
                        id_starlink,numero_kit,email_login,senha_login)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                    (
                        d["id_ativo"], d.get("fazenda"), d.get("setor"), d.get("responsavel"),
                        d.get("modelo"), d.get("num_serie"), d.get("mac_address"), d.get("ip_rede"),
                        d.get("status", "Ativo"), d.get("data_instalacao"), d.get("data_aquisicao"),
                        d.get("plano"), d.get("observacoes"),
                        d.get("id_starlink"), d.get("numero_kit"),
                        d.get("email_login"), d.get("senha_login"),
                    ),
                )
                log_historico(cur, d["id_ativo"], "Starlink", "Cadastro")
            except psycopg2.IntegrityError:
                return jsonify({"ok": False, "msg": "ID de ativo já existe!"}), 400
    return jsonify({"ok": True, "msg": "Starlink cadastrada!"})


@app.route("/api/starlink/<id_ativo>", methods=["GET"])
def get_starlink(id_ativo: str) -> Response:
    """Retorna dados de uma antena Starlink."""
    with get_db() as conn:
        with conn.cursor() as cur:
            row = _fetch_one(cur, "SELECT * FROM starlink WHERE id_ativo=%s", (id_ativo,))
    return jsonify(row)


@app.route("/api/starlink/<id_ativo>", methods=["PUT"])
def atualizar_starlink(id_ativo: str) -> Response:
    """Atualiza dados de uma antena Starlink. Item 7: inclui campos de login."""
    d = request.json
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """UPDATE starlink SET
                   fazenda=%s,setor=%s,responsavel=%s,modelo=%s,num_serie=%s,mac_address=%s,
                   ip_rede=%s,status=%s,data_instalacao=%s,data_aquisicao=%s,plano=%s,
                   observacoes=%s,id_starlink=%s,numero_kit=%s,email_login=%s,senha_login=%s,
                   updated_at=NOW() WHERE id_ativo=%s""",
                (
                    d.get("fazenda"), d.get("setor"), d.get("responsavel"), d.get("modelo"),
                    d.get("num_serie"), d.get("mac_address"), d.get("ip_rede"), d.get("status"),
                    d.get("data_instalacao"), d.get("data_aquisicao"), d.get("plano"),
                    d.get("observacoes"),
                    d.get("id_starlink"), d.get("numero_kit"),
                    d.get("email_login"), d.get("senha_login"),
                    id_ativo,
                ),
            )
            log_historico(cur, id_ativo, "Starlink", "Edição")
    return jsonify({"ok": True, "msg": "Starlink atualizada!"})


# ═══════════════════════════════════════════════════════════════════════════════
# CELULARES TURMA (Item 4)
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/api/celulares_turma", methods=["GET"])
def listar_celulares_turma() -> Response:
    """Lista celulares de turma com filtros de status e busca textual."""
    return _list_table(
        "celulares_turma",
        ["id_ativo", "responsavel", "modelo", "num_turma", "fazenda", "num_serie"],
    )


@app.route("/api/celulares_turma", methods=["POST"])
def criar_celular_turma() -> tuple[Response, int] | Response:
    """Cadastra um novo celular de turma (ID no formato CL-TRM-NN)."""
    d = request.json
    with get_db() as conn:
        with conn.cursor() as cur:
            try:
                cur.execute(
                    """INSERT INTO celulares_turma
                       (id_ativo,num_turma,responsavel,fazenda,setor,modelo,tipo,status,
                        uso_celular,carregador,termo_assinado,data_entrega,data_devolucao,
                        gmail_clockin,senha,usuario_anterior,imei_1,imei_2,num_serie,
                        armazenamento,observacoes)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                    (
                        d["id_ativo"], d.get("num_turma"), d.get("responsavel"),
                        d.get("fazenda"), d.get("setor"), d.get("modelo"), d.get("tipo"),
                        d.get("status", "Ativo"), d.get("uso_celular"), d.get("carregador"),
                        d.get("termo_assinado"), d.get("data_entrega"), d.get("data_devolucao"),
                        d.get("gmail_clockin"), d.get("senha"), d.get("usuario_anterior"),
                        d.get("imei_1"), d.get("imei_2"), d.get("num_serie"),
                        d.get("armazenamento"), d.get("observacoes"),
                    ),
                )
                log_historico(cur, d["id_ativo"], "Celular Turma", "Cadastro")
            except psycopg2.IntegrityError:
                return jsonify({"ok": False, "msg": "ID de ativo já existe!"}), 400
    return jsonify({"ok": True, "msg": "Celular de turma cadastrado!"})


@app.route("/api/celulares_turma/<id_ativo>", methods=["GET"])
def get_celular_turma(id_ativo: str) -> Response:
    """Retorna dados de um celular de turma."""
    with get_db() as conn:
        with conn.cursor() as cur:
            row = _fetch_one(cur, "SELECT * FROM celulares_turma WHERE id_ativo=%s", (id_ativo,))
    return jsonify(row)


@app.route("/api/celulares_turma/<id_ativo>", methods=["PUT"])
def atualizar_celular_turma(id_ativo: str) -> Response:
    """Atualiza dados de um celular de turma."""
    d = request.json
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """UPDATE celulares_turma SET
                   num_turma=%s,responsavel=%s,fazenda=%s,setor=%s,modelo=%s,tipo=%s,
                   status=%s,uso_celular=%s,carregador=%s,termo_assinado=%s,data_entrega=%s,
                   data_devolucao=%s,gmail_clockin=%s,senha=%s,usuario_anterior=%s,
                   imei_1=%s,imei_2=%s,num_serie=%s,armazenamento=%s,observacoes=%s,
                   updated_at=NOW() WHERE id_ativo=%s""",
                (
                    d.get("num_turma"), d.get("responsavel"), d.get("fazenda"), d.get("setor"),
                    d.get("modelo"), d.get("tipo"), d.get("status"), d.get("uso_celular"),
                    d.get("carregador"), d.get("termo_assinado"), d.get("data_entrega"),
                    d.get("data_devolucao"), d.get("gmail_clockin"), d.get("senha"),
                    d.get("usuario_anterior"), d.get("imei_1"), d.get("imei_2"),
                    d.get("num_serie"), d.get("armazenamento"), d.get("observacoes"),
                    id_ativo,
                ),
            )
            log_historico(cur, id_ativo, "Celular Turma", "Edição")
    return jsonify({"ok": True, "msg": "Celular de turma atualizado!"})


# ═══════════════════════════════════════════════════════════════════════════════
# ESTOQUE
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/api/estoque", methods=["GET"])
def listar_estoque() -> Response:
    """Lista itens do estoque geral com busca opcional."""
    busca = request.args.get("q", "")
    query = "SELECT * FROM estoque WHERE 1=1"
    params: list[Any] = []
    if busca:
        query += " AND (item ILIKE %s OR cod_pedido ILIKE %s)"
        params += [f"%{busca}%", f"%{busca}%"]
    query += " ORDER BY item ASC"
    with get_db() as conn:
        with conn.cursor() as cur:
            rows = _fetch_all(cur, query, tuple(params))
    return jsonify(rows)


@app.route("/api/estoque_equipamentos", methods=["GET"])
def listar_estoque_equipamentos() -> Response:
    """Lista todos os equipamentos com status 'Em Estoque' de todas as tabelas."""
    tabelas = [
        ("celulares",        "Celular"),
        ("celulares_ponto",  "Celular Ponto"),
        ("celulares_turma",  "Celular Turma"),
        ("computadores",     "Computador"),
        ("impressoras",      "Impressora"),
        ("estabilizadores",  "Estabilizador"),
        ("starlink",         "Starlink"),
    ]
    query_parts = []
    for tbl, label in tabelas:
        query_parts.append(
            f"SELECT id_ativo, modelo, fazenda, '{label}' as tipo_equipamento, status FROM {tbl} WHERE status = 'Estoque'"
        )

    query = " UNION ALL ".join(query_parts) + " ORDER BY id_ativo ASC"

    with get_db() as conn:
        with conn.cursor() as cur:
            rows = _fetch_all(cur, query)
    return jsonify(rows)


@app.route("/api/localidades", methods=["GET"])
def api_listar_localidades() -> Response:
    """Retorna todas as localidades para selects."""
    with get_db() as conn:
        with conn.cursor() as cur:
            rows = _fetch_all(cur, "SELECT id, nome FROM localidades ORDER BY nome ASC")
    return jsonify(rows)


@app.route("/api/estoque", methods=["POST"])
def criar_estoque() -> Response:
    """Cadastra um novo item no estoque geral."""
    d = request.json
    localidade_id = d.get("localidade_id") or None
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO estoque (item,cod_pedido,quantidade,unidade,localizacao,observacoes,localidade_id) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s)",
                (
                    d["item"], d.get("cod_pedido"), d.get("quantidade", 0),
                    d.get("unidade", "un"), d.get("localizacao"), d.get("observacoes"),
                    localidade_id
                ),
            )
    return jsonify({"ok": True, "msg": "Item cadastrado!"})


@app.route("/api/estoque/<int:eid>", methods=["GET"])
def get_estoque(eid: int) -> Response:
    """Retorna dados de um item de estoque pelo ID."""
    with get_db() as conn:
        with conn.cursor() as cur:
            row = _fetch_one(cur, "SELECT * FROM estoque WHERE id=%s", (eid,))
    return jsonify(row)


@app.route("/api/estoque/<int:eid>", methods=["PUT"])
def atualizar_estoque(eid: int) -> Response:
    """Atualiza dados cadastrais de um item de estoque (não altera quantidade)."""
    d = request.json
    localidade_id = d.get("localidade_id") or None
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """UPDATE estoque SET item=%s,cod_pedido=%s,unidade=%s,localizacao=%s,
                   observacoes=%s,localidade_id=%s,updated_at=NOW() WHERE id=%s""",
                (d.get("item"), d.get("cod_pedido"), d.get("unidade"), d.get("localizacao"),
                 d.get("observacoes"), localidade_id, eid),
            )
    return jsonify({"ok": True, "msg": "Item atualizado!"})


@app.route("/api/estoque/<int:eid>/movimentar", methods=["POST"])
def movimentar_estoque(eid: int) -> tuple[Response, int] | Response:
    """
    Registra entrada ou saída de um item de estoque.

    Usa SELECT FOR UPDATE para evitar race condition TOCTOU:
    dois requests simultâneos não conseguem ler e modificar o mesmo
    saldo concorrentemente — o segundo aguarda o commit do primeiro.

    Complexidade: O(1) — operação em linha única com lock pessimista.
    """
    d = request.json or {}
    tipo = d.get("tipo")
    if tipo not in ("entrada", "saida"):
        return jsonify({"ok": False, "msg": "tipo deve ser 'entrada' ou 'saida'"}), 400

    try:
        qtd = int(d.get("quantidade", 0))
    except (ValueError, TypeError):
        return jsonify({"ok": False, "msg": "Quantidade inválida"}), 400

    if qtd <= 0:
        return jsonify({"ok": False, "msg": "Quantidade deve ser maior que zero"}), 400

    with get_db() as conn:
        with conn.cursor() as cur:
            # FOR UPDATE: bloqueia a linha até o commit — elimina race condition
            cur.execute("SELECT * FROM estoque WHERE id=%s FOR UPDATE", (eid,))
            item = row_to_dict(cur.fetchone())
            if not item:
                return jsonify({"ok": False, "msg": "Item não encontrado"}), 404

            nova_qtd = item["quantidade"] + qtd if tipo == "entrada" else item["quantidade"] - qtd
            if nova_qtd < 0:
                return jsonify({"ok": False, "msg": "Estoque insuficiente!"}), 400

            cur.execute(
                "UPDATE estoque SET quantidade=%s,updated_at=NOW() WHERE id=%s",
                (nova_qtd, eid),
            )
            cur.execute(
                """INSERT INTO estoque_movimentacoes
                   (estoque_id,tipo,quantidade,motivo,responsavel)
                   VALUES (%s,%s,%s,%s,%s)""",
                (eid, tipo, qtd, d.get("motivo"), d.get("responsavel")),
            )

    label = "Entrada" if tipo == "entrada" else "Saída"
    return jsonify({"ok": True, "msg": f"{label} de {qtd} registrada! Saldo: {nova_qtd}", "nova_quantidade": nova_qtd})


@app.route("/api/estoque/<int:eid>/movimentacoes", methods=["GET"])
def historico_estoque(eid: int) -> Response:
    """Retorna o histórico de movimentações de um item de estoque."""
    with get_db() as conn:
        with conn.cursor() as cur:
            rows = _fetch_all(
                cur,
                "SELECT * FROM estoque_movimentacoes WHERE estoque_id=%s ORDER BY id DESC",
                (eid,),
            )
    return jsonify(rows)


# ═══════════════════════════════════════════════════════════════════════════════
# PEDIDOS
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/api/pedidos", methods=["GET"])
def listar_pedidos() -> Response:
    """Lista pedidos com filtros de status e busca."""
    filtro = request.args.get("status", "")
    busca = request.args.get("q", "")
    query = "SELECT * FROM pedidos WHERE 1=1"
    params: list[Any] = []
    if filtro:
        query += " AND status=%s"
        params.append(filtro)
    if busca:
        query += (
            " AND (item ILIKE %s OR fazenda_solicitante ILIKE %s"
            " OR num_requisicao ILIKE %s OR CAST(id AS TEXT) ILIKE %s)"
        )
        params += [f"%{busca}%"] * 4
    query += " ORDER BY id DESC"
    with get_db() as conn:
        with conn.cursor() as cur:
            rows = _fetch_all(cur, query, tuple(params))
    return jsonify(rows)


@app.route("/api/pedidos", methods=["POST"])
def criar_pedido() -> Response:
    """Cadastra um novo pedido. Item 9: inclui responsavel_envio, retorna id para upload de nota."""
    d = request.json
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO pedidos
                   (fazenda_solicitante,data_pedido,status,quantidade,num_requisicao,
                    item,estoque_id,motivo,forma_envio,responsavel,observacoes,
                    responsavel_envio)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                   RETURNING id""",
                (
                    d["fazenda_solicitante"], d.get("data_pedido") or date.today().isoformat(),
                    d.get("status", "Aberto"), d.get("quantidade", 1), d.get("num_requisicao"),
                    d["item"], d.get("estoque_id"), d.get("motivo"), d.get("forma_envio"),
                    d.get("responsavel"), d.get("observacoes"),
                    d.get("responsavel_envio"),
                ),
            )
            novo_id = cur.fetchone()["id"]
    return jsonify({"ok": True, "msg": "Pedido cadastrado!", "id": novo_id})


@app.route("/api/pedidos/<int:pid>", methods=["GET"])
def get_pedido(pid: int) -> Response:
    """Retorna dados de um pedido."""
    with get_db() as conn:
        with conn.cursor() as cur:
            row = _fetch_one(cur, "SELECT * FROM pedidos WHERE id=%s", (pid,))
    return jsonify(row)


@app.route("/api/pedidos/<int:pid>", methods=["PUT"])
def atualizar_pedido(pid: int) -> tuple[Response, int] | Response:
    """Atualiza status e dados de um pedido. Ao finalizar, desconta do estoque se houver estoque_id."""
    d = request.json
    novo_status = d.get("status", "")
    with get_db() as conn:
        with conn.cursor() as cur:
            pedido = _fetch_one(cur, "SELECT * FROM pedidos WHERE id=%s", (pid,))
            if not pedido:
                return jsonify({"ok": False, "msg": "Pedido não encontrado"}), 404

            cur.execute(
                """UPDATE pedidos SET
                   fazenda_solicitante=%s,status=%s,quantidade=%s,num_requisicao=%s,
                   item=%s,estoque_id=%s,motivo=%s,forma_envio=%s,responsavel=%s,
                   observacoes=%s,responsavel_envio=%s,updated_at=NOW() WHERE id=%s""",
                (
                    d.get("fazenda_solicitante", pedido["fazenda_solicitante"]),
                    novo_status,
                    d.get("quantidade", pedido["quantidade"]),
                    d.get("num_requisicao", pedido["num_requisicao"]),
                    d.get("item", pedido["item"]),
                    d.get("estoque_id", pedido["estoque_id"]),
                    d.get("motivo", pedido["motivo"]),
                    d.get("forma_envio", pedido["forma_envio"]),
                    d.get("responsavel", pedido["responsavel"]),
                    d.get("observacoes", pedido["observacoes"]),
                    d.get("responsavel_envio", pedido.get("responsavel_envio")),
                    pid,
                ),
            )

            # Descontar do estoque ao finalizar
            if novo_status == "Finalizado" and pedido["status"] != "Finalizado":
                eid = d.get("estoque_id") or pedido["estoque_id"]
                qtd = int(d.get("quantidade") or pedido["quantidade"])
                if eid:
                    item_est = _fetch_one(cur, "SELECT * FROM estoque WHERE id=%s", (eid,))
                    if item_est:
                        nova_qtd = item_est["quantidade"] - qtd
                        if nova_qtd < 0:
                            return jsonify({"ok": False, "msg": "Estoque insuficiente para finalizar pedido!"}), 400
                        cur.execute("UPDATE estoque SET quantidade=%s,updated_at=NOW() WHERE id=%s", (nova_qtd, eid))
                        cur.execute(
                            """INSERT INTO estoque_movimentacoes (estoque_id,tipo,quantidade,motivo,responsavel)
                               VALUES (%s,'saida',%s,%s,%s)""",
                            (eid, qtd, f"Pedido #{pid} finalizado", d.get("responsavel") or pedido["responsavel"]),
                        )

    return jsonify({"ok": True, "msg": "Pedido atualizado!"})


# ═══════════════════════════════════════════════════════════════════════════════
# IMPRESSORAS POR FAZENDA (para seleção no Toner)
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/api/impressoras/por_fazenda")
def impressoras_por_fazenda() -> Response:
    """Retorna impressoras filtradas por fazenda para uso no módulo de toners."""
    fazenda = request.args.get("fazenda", "Central")
    with get_db() as conn:
        with conn.cursor() as cur:
            rows = _fetch_all(
                cur,
                "SELECT id_ativo, modelo, ip_rede FROM impressoras WHERE fazenda=%s AND status='Ativo' ORDER BY id_ativo",
                (fazenda,),
            )
    return jsonify(rows)


# ═══════════════════════════════════════════════════════════════════════════════
# TONERS
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/api/toners", methods=["GET"])
def listar_toners() -> Response:
    """Lista toners cadastrados com busca opcional."""
    busca = request.args.get("q", "")
    query = "SELECT * FROM toners WHERE 1=1"
    params: list[Any] = []
    if busca:
        query += " AND (modelo_impressora ILIKE %s OR modelo_toner ILIKE %s OR cor ILIKE %s)"
        params += [f"%{busca}%"] * 3
    query += " ORDER BY modelo_impressora, cor"
    with get_db() as conn:
        with conn.cursor() as cur:
            rows = _fetch_all(cur, query, tuple(params))
    return jsonify(rows)


@app.route("/api/toners", methods=["POST"])
def criar_toner() -> Response:
    """Cadastra um novo toner."""
    d = request.json
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO toners
                   (modelo_impressora,modelo_toner,cor,quantidade_estoque,
                    data_ultima_troca,quantidade_minima,observacoes,tipo_suprimento)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s)""",
                (
                    d["modelo_impressora"], d["modelo_toner"], d.get("cor", "Preto"),
                    d.get("quantidade_estoque", 0), d.get("data_ultima_troca"),
                    d.get("quantidade_minima", 1), d.get("observacoes"),
                    d.get("tipo_suprimento", "Toner"),
                ),
            )
    return jsonify({"ok": True, "msg": "Toner cadastrado!"})


@app.route("/api/toners/<int:tid>", methods=["GET"])
def get_toner(tid: int) -> Response:
    """Retorna dados de um toner pelo ID."""
    with get_db() as conn:
        with conn.cursor() as cur:
            row = _fetch_one(cur, "SELECT * FROM toners WHERE id=%s", (tid,))
    return jsonify(row)


@app.route("/api/toners/<int:tid>", methods=["PUT"])
def atualizar_toner(tid: int) -> Response:
    """Atualiza dados de um toner."""
    d = request.json
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """UPDATE toners SET
                   modelo_impressora=%s,modelo_toner=%s,cor=%s,quantidade_estoque=%s,
                   quantidade_minima=%s,observacoes=%s,tipo_suprimento=%s,updated_at=NOW() WHERE id=%s""",
                (
                    d.get("modelo_impressora"), d.get("modelo_toner"), d.get("cor"),
                    d.get("quantidade_estoque"), d.get("quantidade_minima"),
                    d.get("observacoes"), d.get("tipo_suprimento", "Toner"), tid,
                ),
            )
    return jsonify({"ok": True, "msg": "Toner atualizado!"})


@app.route("/api/toners/<int:tid>/troca", methods=["POST"])
def registrar_troca_toner(tid: int) -> tuple[Response, int] | Response:
    """
    Registra uma troca de toner, debitando o estoque e atualizando data da última troca.

    Valida saldo disponível antes de registrar.
    """
    d = request.json
    with get_db() as conn:
        with conn.cursor() as cur:
            toner = _fetch_one(cur, "SELECT * FROM toners WHERE id=%s", (tid,))
            if not toner:
                return jsonify({"ok": False, "msg": "Toner não encontrado"}), 404

            qtd = int(d.get("quantidade", 1))
            nova_qtd = toner["quantidade_estoque"] - qtd
            if nova_qtd < 0:
                return jsonify({"ok": False, "msg": "Estoque insuficiente!"}), 400

            hoje = date.today().isoformat()
            cur.execute(
                "UPDATE toners SET quantidade_estoque=%s,data_ultima_troca=%s,updated_at=NOW() WHERE id=%s",
                (nova_qtd, hoje, tid),
            )
            cur.execute(
                """INSERT INTO toner_trocas
                   (toner_id,quantidade,responsavel,impressora_id_ativo,data_troca,observacoes,tipo_suprimento)
                   VALUES (%s,%s,%s,%s,%s,%s,%s)""",
                (tid, qtd, d.get("responsavel"), d.get("impressora_id_ativo"), hoje,
                 d.get("observacoes"), d.get("tipo_suprimento", "Toner")),
            )

    return jsonify({"ok": True, "msg": f"Troca registrada! Estoque restante: {nova_qtd}", "nova_quantidade": nova_qtd})


@app.route("/api/toners/<int:tid>/trocas", methods=["GET"])
def historico_trocas(tid: int) -> Response:
    """Retorna o histórico de trocas de um toner."""
    with get_db() as conn:
        with conn.cursor() as cur:
            rows = _fetch_all(
                cur,
                "SELECT * FROM toner_trocas WHERE toner_id=%s ORDER BY id DESC",
                (tid,),
            )
    return jsonify(rows)


# ═══════════════════════════════════════════════════════════════════════════════
# MANUTENÇÕES
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/api/manutencoes", methods=["GET"])
def listar_manutencoes() -> Response:
    """Lista manutenções com filtros de status, tipo e busca textual."""
    filtro = request.args.get("status", "")
    tipo = request.args.get("tipo", "")
    busca = request.args.get("q", "")
    query = "SELECT * FROM manutencoes WHERE 1=1"
    params: list[Any] = []

    if filtro:
        query += " AND status=%s"
        params.append(filtro)
    if tipo:
        query += " AND tipo_equipamento=%s"
        params.append(tipo)
    if busca:
        query += " AND (id_ativo ILIKE %s OR modelo ILIKE %s OR problema_relatado ILIKE %s)"
        params += [f"%{busca}%"] * 3

    query += " ORDER BY id DESC"

    with get_db() as conn:
        with conn.cursor() as cur:
            rows = _fetch_all(cur, query, tuple(params))
    return jsonify(rows)


@app.route("/api/manutencoes", methods=["POST"])
def criar_manutencao() -> Response:
    """Registra uma nova ocorrência de manutenção."""
    d = request.json
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO manutencoes
                   (id_ativo,tipo_equipamento,modelo,local_atual,data_recebimento,
                    pessoa_recebimento,problema_relatado,data_manutencao,os_manutencao,
                    orcamento,status,data_envio,forma_envio,data_retorno,
                    solucao_aplicada,tecnico,observacoes,
                    tipo_manutencao,pecas_utilizadas,subtipo)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (
                    d["id_ativo"], d["tipo_equipamento"], d.get("modelo"), d.get("local_atual"),
                    d.get("data_recebimento"), d.get("pessoa_recebimento"), d.get("problema_relatado"),
                    d.get("data_manutencao"), d.get("os_manutencao"), d.get("orcamento"),
                    d.get("status", "Aberta"), d.get("data_envio"), d.get("forma_envio"),
                    d.get("data_retorno"), d.get("solucao_aplicada"), d.get("tecnico"),
                    d.get("observacoes"), d.get("tipo_manutencao"),
                    d.get("pecas_utilizadas"), d.get("subtipo"),
                ),
            )
            log_historico(cur, d["id_ativo"], d["tipo_equipamento"], "Manutenção Aberta")
    return jsonify({"ok": True, "msg": "Manutenção registrada!"})


@app.route("/api/manutencoes/<int:mid>", methods=["GET"])
def get_manutencao(mid: int) -> Response:
    """Retorna dados de uma manutenção pelo ID."""
    with get_db() as conn:
        with conn.cursor() as cur:
            row = _fetch_one(cur, "SELECT * FROM manutencoes WHERE id=%s", (mid,))
    return jsonify(row)


@app.route("/api/manutencoes/<int:mid>", methods=["PUT"])
def atualizar_manutencao(mid: int) -> Response:
    """Atualiza dados de uma manutenção existente."""
    d = request.json
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """UPDATE manutencoes SET
                   local_atual=%s,data_recebimento=%s,pessoa_recebimento=%s,
                   problema_relatado=%s,data_manutencao=%s,os_manutencao=%s,orcamento=%s,
                   status=%s,data_envio=%s,forma_envio=%s,data_retorno=%s,
                   solucao_aplicada=%s,tecnico=%s,observacoes=%s,
                   tipo_manutencao=%s,pecas_utilizadas=%s,subtipo=%s,updated_at=NOW()
                   WHERE id=%s""",
                (
                    d.get("local_atual"), d.get("data_recebimento"), d.get("pessoa_recebimento"),
                    d.get("problema_relatado"), d.get("data_manutencao"), d.get("os_manutencao"),
                    d.get("orcamento"), d.get("status"), d.get("data_envio"), d.get("forma_envio"),
                    d.get("data_retorno"), d.get("solucao_aplicada"), d.get("tecnico"),
                    d.get("observacoes"), d.get("tipo_manutencao"),
                    d.get("pecas_utilizadas"), d.get("subtipo"), mid,
                ),
            )
    return jsonify({"ok": True, "msg": "Manutenção atualizada!"})


# ═══════════════════════════════════════════════════════════════════════════════
# DESCARTES
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/api/descartes", methods=["GET"])
def listar_descartes() -> Response:
    """Lista todos os descartes registrados."""
    with get_db() as conn:
        with conn.cursor() as cur:
            rows = _fetch_all(cur, "SELECT * FROM descartes ORDER BY id DESC")
    return jsonify(rows)


@app.route("/api/pedidos/<int:pid>/upload-nota", methods=["POST"])
def upload_nota_pedido(pid: int) -> tuple[Response, int] | Response:
    """
    Item 9: Recebe e salva o PDF/imagem de nota fiscal de um pedido.

    Aceita: .pdf, .jpg, .jpeg, .png
    Salva em: database/termos/pedido_{id}_nota.{ext}
    Atualiza: campo nota_fiscal_pdf na tabela pedidos.
    """
    if "file" not in request.files:
        return jsonify({"ok": False, "msg": "Nenhum arquivo enviado"}), 400

    file = request.files["file"]
    if not file.filename:
        return jsonify({"ok": False, "msg": "Arquivo vazio"}), 400

    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if ext not in {"pdf", "jpg", "jpeg", "png"}:
        return jsonify({"ok": False, "msg": "Extensão não permitida. Use PDF, JPG ou PNG"}), 400

    safe_name = f"pedido_{pid}_nota.{ext}"
    file.save(os.path.join(UPLOAD_FOLDER, safe_name))

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE pedidos SET nota_fiscal_pdf=%s,updated_at=NOW() WHERE id=%s",
                (safe_name, pid),
            )

    return jsonify({"ok": True, "msg": "Nota fiscal anexada!", "filename": safe_name})


@app.route("/api/descartes", methods=["POST"])
def criar_descarte() -> Response:
    """Registra o descarte de um ativo e atualiza seu status na tabela de origem."""
    d = request.json
    tabela_map = {
        "Celular":          "celulares",
        "Celular Ponto":    "celulares_ponto",
        "Celular Turma":    "celulares_turma",
        "Computador":       "computadores",
        "Impressora":       "impressoras",
        "Estabilizador":    "estabilizadores",
        "Starlink":         "starlink",
    }
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO descartes
                   (id_ativo,tipo_equipamento,modelo,motivo,data_descarte,
                    responsavel_descarte,forma_descarte,destinatario,
                    documento_referencia,observacoes)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (
                    d["id_ativo"], d["tipo_equipamento"], d.get("modelo"), d.get("motivo"),
                    d.get("data_descarte"), d.get("responsavel_descarte"), d.get("forma_descarte"),
                    d.get("destinatario"), d.get("documento_referencia"), d.get("observacoes"),
                ),
            )
            tabela = tabela_map.get(d["tipo_equipamento"])
            if tabela:
                cur.execute(
                    f"UPDATE {tabela} SET status='Descartado' WHERE id_ativo=%s",
                    (d["id_ativo"],),
                )
            log_historico(cur, d["id_ativo"], d["tipo_equipamento"], "Descarte")
    return jsonify({"ok": True, "msg": "Descarte registrado!"})


# ═══════════════════════════════════════════════════════════════════════════════
# HISTÓRICO / BUSCA / EXPORTAR
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/api/historico")
def historico_global() -> Response:
    """Retorna o histórico completo (últimos 500 registros) para a aba Histórico."""
    with get_db() as conn:
        with conn.cursor() as cur:
            rows = _fetch_all(cur, "SELECT * FROM historico ORDER BY id DESC LIMIT 500")
    return jsonify(rows)


@app.route("/api/historico/<id_ativo>")
def historico_ativo(id_ativo: str) -> Response:
    """Retorna o histórico de alterações de um ativo específico."""
    with get_db() as conn:
        with conn.cursor() as cur:
            rows = _fetch_all(
                cur,
                "SELECT * FROM historico WHERE id_ativo=%s ORDER BY id DESC",
                (id_ativo,),
            )
    return jsonify(rows)


@app.route("/api/exportar/<tabela>")
def exportar(tabela: str) -> tuple[Response, int] | Response:
    """Exporta todos os dados de uma tabela em formato CSV. Datas em DD/MM/AAAA."""
    tabelas_validas = {
        "celulares", "celulares_ponto", "celulares_inspecao", "celulares_turma",
        "computadores", "impressoras",
        "estabilizadores", "starlink", "manutencoes", "descartes", "estoque", "toners",
        "transferencias", "historico", "estoque_equipamentos", "pedidos",
    }
    if tabela not in tabelas_validas:
        return jsonify({"ok": False, "msg": "Tabela inválida"}), 400

    # Campos de data para converter para DD/MM/AAAA na exportação
    _DATE_FIELDS = {
        "data_entrega", "data_devolucao", "data_transferencia", "data_recebimento",
        "data_descarte", "data_pedido", "data_instalacao", "data_aquisicao",
        "data_manutencao", "data_envio", "data_retorno", "data_ultima_troca",
    }

    def _fmt_date(val: Any) -> Any:
        """Converte date/datetime para string DD/MM/AAAA, mantém outros tipos."""
        if val is None:
            return ""
        if hasattr(val, "strftime"):
            return val.strftime("%d/%m/%Y")
        if isinstance(val, str) and len(val) >= 10 and val[4] == "-":
            try:
                parts = val[:10].split("-")
                return f"{parts[2]}/{parts[1]}/{parts[0]}"
            except (IndexError, ValueError):
                return val
        return val

    with get_db() as conn:
        with conn.cursor() as cur:
            if tabela == "estoque_equipamentos":
                tabelas = [
                    ("celulares",       "Celular"),
                    ("celulares_ponto", "Celular Ponto"),
                    ("celulares_inspecao", "Celular Inspeção"),
                    ("celulares_turma", "Celular Turma"),
                    ("computadores",    "Computador"),
                    ("impressoras",     "Impressora"),
                    ("estabilizadores", "Estabilizador"),
                    ("starlink",        "Starlink"),
                ]
                query_parts = []
                for tbl, label in tabelas:
                    query_parts.append(
                        f"SELECT id_ativo, modelo, fazenda, '{label}' as tipo_equipamento, status "
                        f"FROM {tbl} WHERE status = 'Estoque'"
                    )
                rows = _fetch_all(cur, " UNION ALL ".join(query_parts) + " ORDER BY id_ativo ASC")
            else:
                rows = _fetch_all(cur, f"SELECT * FROM {tabela}")

    if not rows:
        return jsonify({"ok": False, "msg": "Sem dados para exportar"}), 404

    # Converte campos de data para o formato brasileiro
    rows_export = []
    for row in rows:
        row_conv = dict(row)
        for field in _DATE_FIELDS:
            if field in row_conv:
                row_conv[field] = _fmt_date(row_conv[field])
        rows_export.append(row_conv)

    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=rows_export[0].keys())
    writer.writeheader()
    writer.writerows(rows_export)

    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={tabela}.csv"},
    )


# ═══════════════════════════════════════════════════════════════════════════════
# ITEM 3 — GERADOR DE ID / IMPORTAÇÃO DE COLETA
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/api/gerar_id")
def api_gerar_id() -> tuple[Response, int] | Response:
    """
    Sugere o próximo ID disponível para um ativo no padrão TIPO-LOCAL-SETOR-NN.

    Query params:
        tipo: Sigla do tipo (ex.: NT, DK, CL)
        localidade: Sigla da localidade (ex.: CEN, SMN)
        setor: Sigla do setor (ex.: ADM, TI)

    Returns:
        JSON com o ID sugerido e o próximo sequencial.
    """
    tipo = request.args.get("tipo", "").upper()
    localidade = request.args.get("localidade", "").upper()
    setor = request.args.get("setor", "").upper()

    if tipo not in SIGLAS_TIPO:
        return jsonify({"ok": False, "msg": f"Tipo inválido. Válidos: {list(SIGLAS_TIPO)}"}), 400
    if localidade not in SIGLAS_LOCAL:
        return jsonify({"ok": False, "msg": f"Localidade inválida. Válidas: {list(SIGLAS_LOCAL)}"}), 400
    if setor not in SIGLAS_SETOR:
        return jsonify({"ok": False, "msg": f"Setor inválido. Válidos: {list(SIGLAS_SETOR)}"}), 400

    with get_db() as conn:
        with conn.cursor() as cur:
            id_sugerido = sugerir_id(cur, tipo, localidade, setor)
            seq = proximo_sequencial(cur, tipo, localidade, setor)

    return jsonify({"ok": True, "id_sugerido": id_sugerido, "sequencial": seq})


@app.route("/api/siglas")
def api_siglas() -> Response:
    """Retorna os dicionários de siglas válidas para geração de IDs."""
    return jsonify({
        "tipos": SIGLAS_TIPO,
        "localidades": SIGLAS_LOCAL,
        "setores": SIGLAS_SETOR,
    })


@app.route("/api/importar_coleta", methods=["POST"])
def importar_coleta() -> tuple[Response, int] | Response:
    """
    Importa dados coletados automaticamente pelo COLETAR_PC.bat.

    Recebe multipart/form-data com:
        file: Arquivo .txt no formato INI (chave=valor) gerado pelo script.
        id_ativo: ID no padrão TIPO-LOCAL-SETOR-NN.
        fazenda: Nome da fazenda de destino.
        setor: Nome do setor de destino.

    Comportamento:
        - Se numero_serie não existe: insere novo registro completo.
        - Se numero_serie já existe: atualiza apenas campos técnicos.
        - Retorna 409 se id_ativo já existe com numero_serie diferente.

    Returns:
        JSON com resultado da operação, ação executada e dados processados.
    """
    if "file" not in request.files:
        return jsonify({"ok": False, "msg": "Arquivo .txt não enviado"}), 400

    id_ativo = request.form.get("id_ativo", "").strip()
    fazenda = request.form.get("fazenda", "").strip()
    setor_form = request.form.get("setor", "").strip()

    if not id_ativo:
        return jsonify({"ok": False, "msg": "Campo id_ativo é obrigatório"}), 400

    # Parse do arquivo INI
    file = request.files["file"]
    try:
        conteudo = file.read().decode("utf-8", errors="replace")
        dados_coleta: dict[str, str] = {}
        for linha in conteudo.splitlines():
            linha = linha.strip()
            if "=" in linha and not linha.startswith("#"):
                chave, _, valor = linha.partition("=")
                dados_coleta[chave.strip().lower()] = valor.strip()
    except Exception as exc:
        return jsonify({"ok": False, "msg": f"Erro ao processar arquivo: {exc}"}), 400

    # Campos obrigatórios
    campos_obrigatorios = ["num_serie", "modelo", "marca"]
    ausentes = [c for c in campos_obrigatorios if not dados_coleta.get(c)]
    if ausentes:
        return jsonify({"ok": False, "msg": f"Campos obrigatórios ausentes no .txt: {ausentes}"}), 400

    # Mapeamento de campos
    mapa: dict[str, str] = {
        "num_serie": dados_coleta.get("num_serie"),
        "marca": dados_coleta.get("marca"),
        "modelo": dados_coleta.get("modelo"),
        "processador": dados_coleta.get("processador"),
        "memoria_ram": dados_coleta.get("memoria_ram"),
        "armazenamento": dados_coleta.get("armazenamento"),
        "sistema_operacional": dados_coleta.get("sistema_operacional"),
        "versao_so": dados_coleta.get("versao_so"),
        "usuario_windows": dados_coleta.get("usuario"),
        "ip_rede": dados_coleta.get("ip"),  # apenas para histórico
    }

    hoje = date.today().isoformat()

    with get_db() as conn:
        with conn.cursor() as cur:
            # Verifica se numero_serie já existe
            existente_por_serie = _fetch_one(
                cur,
                "SELECT id_ativo FROM computadores WHERE numero_serie=%s",
                (mapa["num_serie"],),
            )

            if existente_por_serie:
                # Atualiza campos técnicos
                id_existente = existente_por_serie["id_ativo"]
                cur.execute(
                    """UPDATE computadores SET
                       processador=%s,memoria_ram=%s,armazenamento=%s,
                       sistema_operacional=%s,versao_so=%s,usuario_windows=%s,
                       updated_at=NOW() WHERE numero_serie=%s""",
                    (
                        mapa["processador"], mapa["memoria_ram"], mapa["armazenamento"],
                        mapa["sistema_operacional"], mapa["versao_so"], mapa["usuario_windows"],
                        mapa["num_serie"],
                    ),
                )
                log_historico(
                    cur, id_existente, "Computador",
                    f"Atualização via Coleta Automática | IP: {mapa.get('ip_rede', '-')}",
                )
                acao = "atualizado"
                id_retorno = id_existente

            else:
                # Verifica conflito de id_ativo com outro serie
                conflito = _fetch_one(
                    cur,
                    "SELECT numero_serie FROM computadores WHERE id_ativo=%s",
                    (id_ativo,),
                )
                if conflito and conflito["numero_serie"] != mapa["num_serie"]:
                    return jsonify({
                        "ok": False,
                        "msg": f"ID {id_ativo} já existe com número de série diferente ({conflito['numero_serie']})",
                    }), 409

                cur.execute(
                    """INSERT INTO computadores
                       (id_ativo,fazenda,setor,marca,modelo,numero_serie,processador,
                        memoria_ram,armazenamento,sistema_operacional,versao_so,
                        usuario_windows,status,data_entrega)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'Ativo',%s)""",
                    (
                        id_ativo, fazenda, setor_form, mapa["marca"], mapa["modelo"],
                        mapa["num_serie"], mapa["processador"], mapa["memoria_ram"],
                        mapa["armazenamento"], mapa["sistema_operacional"], mapa["versao_so"],
                        mapa["usuario_windows"], hoje,
                    ),
                )
                log_historico(
                    cur, id_ativo, "Computador",
                    f"Cadastro via Coleta Automática | IP: {mapa.get('ip_rede', '-')}",
                )
                acao = "criado"
                id_retorno = id_ativo

    return jsonify({"ok": True, "acao": acao, "id_ativo": id_retorno, "dados": mapa})


# ═══════════════════════════════════════════════════════════════════════════════
# ITEM 4 — TRANSFERÊNCIAS DE ATIVOS
# ═══════════════════════════════════════════════════════════════════════════════

# Mapeamento tipo_equipamento → nome da tabela
_TABELA_POR_TIPO: dict[str, str] = {
    "Celular":          "celulares",
    "Celular Ponto":    "celulares_ponto",
    "Celular Inspeção": "celulares_inspecao",
    "Celular Turma":    "celulares_turma",
    "Computador":       "computadores",
    "Impressora":       "impressoras",
    "Estabilizador":    "estabilizadores",
    "Starlink":         "starlink",
}

# Mapeamento tipo_equipamento → sigla para id_generator
_SIGLA_TIPO_MAP: dict[str, str] = {
    "Celular":          "CL",
    "Celular Ponto":    "CL",
    "Celular Inspeção": "CL",
    "Celular Turma":    "CL",  # Não remapeado — usa CL-TRM-NN
    "Impressora":       "IMP",
    "Estabilizador":    "EST",
    "Starlink":         "STL",
    # Computador: DK ou NT — determinado dinamicamente pelo campo 'tipo'
}

_STATUS_BLOQUEADOS = {"Manutenção", "Descartado"}


@app.route("/api/transferencias", methods=["POST"])
def criar_transferencia() -> tuple[Response, int] | Response:
    """
    Registra uma transferência de ativo entre responsáveis/fazendas/setores.

    Executa atomicamente (mesma transação):
        1. Insere registro na tabela transferencias.
        2. Atualiza responsavel, fazenda, setor, data_entrega, usuario_anterior no ativo.
        3. Aplica lógica especial para 'Usuario para Estoque' e 'Estoque para Usuario'.
        4. Registra no histórico.

    Validações:
        - id_ativo deve existir.
        - Status não pode ser 'Manutenção' ou 'Descartado'.
        - data_transferencia não pode ser futura.
        - responsavel_destino obrigatório para 'Estoque para Usuario'.
        - data_devolucao obrigatório para 'Usuario para Estoque'.

    Returns:
        JSON com resultado da operação.
    """
    d = request.json
    tipo_eq = d.get("tipo_equipamento", "")
    tabela = _TABELA_POR_TIPO.get(tipo_eq)

    if not tabela:
        return jsonify({"ok": False, "msg": f"Tipo de equipamento inválido: {tipo_eq}"}), 400

    id_ativo = d.get("id_ativo", "")
    tipo_transf = d.get("tipo_transferencia", "")
    data_transf = d.get("data_transferencia") or date.today().isoformat()

    # Valida data futura
    try:
        if date.fromisoformat(data_transf) > date.today():
            return jsonify({"ok": False, "msg": "Data de transferência não pode ser futura"}), 400
    except ValueError:
        return jsonify({"ok": False, "msg": "Data de transferência inválida"}), 400

    # Validações específicas por tipo
    if tipo_transf == "Estoque para Usuario" and not d.get("responsavel_destino"):
        return jsonify({"ok": False, "msg": "responsavel_destino é obrigatório para 'Estoque para Usuario'"}), 400
    if tipo_transf == "Usuario para Estoque" and not d.get("data_devolucao"):
        return jsonify({"ok": False, "msg": "data_devolucao é obrigatório para 'Usuario para Estoque'"}), 400

    hoje = date.today().isoformat()

    with get_db() as conn:
        with conn.cursor() as cur:
            # Verifica existência e status do ativo
            ativo = _fetch_one(
                cur, f"SELECT id_ativo,status,responsavel FROM {tabela} WHERE id_ativo=%s", (id_ativo,)
            )
            if not ativo:
                return jsonify({"ok": False, "msg": f"Ativo '{id_ativo}' não encontrado em {tipo_eq}"}), 404

            if ativo["status"] in _STATUS_BLOQUEADOS:
                return jsonify({
                    "ok": False,
                    "msg": f"Ativo com status '{ativo['status']}' não pode ser transferido",
                }), 409

            # 1. Inserir transferência
            cur.execute(
                """INSERT INTO transferencias
                   (id_ativo,tipo_equipamento,responsavel_origem,fazenda_origem,setor_origem,
                    responsavel_destino,fazenda_destino,setor_destino,tipo_transferencia,
                    motivo,data_transferencia,registrado_por,observacoes,termo_pdf)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (
                    id_ativo, tipo_eq,
                    d.get("responsavel_origem"), d.get("fazenda_origem"), d.get("setor_origem"),
                    d.get("responsavel_destino"), d.get("fazenda_destino"), d.get("setor_destino"),
                    tipo_transf, d.get("motivo"), data_transf,
                    d.get("registrado_por"), d.get("observacoes"), d.get("termo_pdf"),
                ),
            )

            # 2 & 3. Atualizar ativo conforme tipo de transferência
            if tipo_transf == "Usuario para Estoque":
                cur.execute(
                    f"""UPDATE {tabela} SET
                        status='Estoque', responsavel=NULL,
                        data_devolucao=%s, usuario_anterior=%s,
                        updated_at=NOW() WHERE id_ativo=%s""",
                    (d.get("data_devolucao"), ativo["responsavel"], id_ativo),
                )
            elif tipo_transf == "Estoque para Usuario":
                cur.execute(
                    f"""UPDATE {tabela} SET
                        status='Ativo', responsavel=%s, fazenda=%s, setor=%s,
                        data_entrega=%s, data_devolucao=NULL,
                        usuario_anterior=%s, updated_at=NOW() WHERE id_ativo=%s""",
                    (
                        d.get("responsavel_destino"), d.get("fazenda_destino"),
                        d.get("setor_destino"), hoje,
                        ativo["responsavel"], id_ativo,
                    ),
                )
            else:
                # Transferência entre usuários/fazendas
                cur.execute(
                    f"""UPDATE {tabela} SET
                        responsavel=%s, fazenda=%s, setor=%s,
                        data_entrega=%s, usuario_anterior=%s,
                        updated_at=NOW() WHERE id_ativo=%s""",
                    (
                        d.get("responsavel_destino"), d.get("fazenda_destino"),
                        d.get("setor_destino"), hoje,
                        ativo["responsavel"], id_ativo,
                    ),
                )

            # 4. Histórico
            log_historico(
                cur, id_ativo, tipo_eq,
                f"Transferência: {tipo_transf} → {d.get('responsavel_destino') or 'Estoque'}",
            )

            # 5. Regen de ID após transferência (Item 6)
            # Apenas para transferências entre usuário/fazendas (não para Estoque)
            fazenda_dest = d.get("fazenda_destino", "")
            setor_dest   = d.get("setor_destino", "")
            if (
                tipo_transf not in ("Usuario para Estoque",)
                and fazenda_dest
                and setor_dest
                and not id_ativo.startswith("CL-TRM-")  # Turma: sem regen
            ):
                tipo_sigla = _SIGLA_TIPO_MAP.get(tipo_eq)
                # Para Computador, busca o campo 'tipo' do ativo para determinar DK ou NT
                if tipo_eq == "Computador" and not tipo_sigla:
                    ativo_full = _fetch_one(cur, "SELECT tipo FROM computadores WHERE id_ativo=%s", (id_ativo,))
                    tipo_sigla = "DK" if (ativo_full or {}).get("tipo", "").lower() == "desktop" else "NT"

                if tipo_sigla:
                    local_sigla = FAZENDA_PARA_SIGLA.get(fazenda_dest, fazenda_dest.upper()[:3])
                    setor_sigla = SETOR_PARA_SIGLA.get(setor_dest, setor_dest.upper()[:3])
                    try:
                        seq = proximo_sequencial(cur, tipo_sigla, local_sigla, setor_sigla)
                        novo_id = gerar_id_ativo(tipo_sigla, local_sigla, setor_sigla, seq)
                        # Registra ID anterior em observacoes da transferência
                        cur.execute(
                            "UPDATE transferencias SET observacoes = CASE "
                            "WHEN observacoes IS NULL OR observacoes = '' THEN %s "
                            "ELSE observacoes || ' | ' || %s END "
                            "WHERE id_ativo=%s AND id=(SELECT MAX(id) FROM transferencias WHERE id_ativo=%s)",
                            (
                                f"ID anterior: {id_ativo}", f"ID anterior: {id_ativo}",
                                id_ativo, id_ativo,
                            ),
                        )
                        # Atualiza id_ativo na tabela de origem
                        cur.execute(
                            f"UPDATE {tabela} SET id_ativo=%s WHERE id_ativo=%s",
                            (novo_id, id_ativo),
                        )
                        # Atualiza histórico e transferências para rastreabilidade
                        cur.execute(
                            "UPDATE historico SET id_ativo=%s WHERE id_ativo=%s",
                            (novo_id, id_ativo),
                        )
                        cur.execute(
                            "UPDATE transferencias SET id_ativo=%s WHERE id_ativo=%s",
                            (novo_id, id_ativo),
                        )
                        id_ativo = novo_id  # Atualiza variável local
                    except ValueError:
                        pass  # Sigla inválida — mantém ID original

    return jsonify({"ok": True, "msg": "Transferência registrada com sucesso!"})


@app.route("/api/transferencias", methods=["GET"])
def listar_transferencias() -> Response:
    """
    Lista transferências com filtros opcionais.

    Query params:
        id_ativo: Filtrar por ID do ativo.
        tipo_equipamento: Filtrar por tipo.
        data_inicio: Data inicial (YYYY-MM-DD).
        data_fim: Data final (YYYY-MM-DD).
    """
    id_ativo = request.args.get("id_ativo", "")
    tipo_eq = request.args.get("tipo_equipamento", "")
    data_ini = request.args.get("data_inicio", "")
    data_fim = request.args.get("data_fim", "")

    query = "SELECT * FROM transferencias WHERE 1=1"
    params: list[Any] = []

    if id_ativo:
        query += " AND id_ativo=%s"
        params.append(id_ativo)
    if tipo_eq:
        query += " AND tipo_equipamento=%s"
        params.append(tipo_eq)
    if data_ini:
        query += " AND data_transferencia >= %s"
        params.append(data_ini)
    if data_fim:
        query += " AND data_transferencia <= %s"
        params.append(data_fim)

    query += " ORDER BY id DESC"

    with get_db() as conn:
        with conn.cursor() as cur:
            rows = _fetch_all(cur, query, tuple(params))

    return jsonify(rows)


@app.route("/api/transferencias/<id_ativo>/historico")
def historico_transferencias(id_ativo: str) -> Response:
    """
    Retorna o histórico paginado de transferências de um ativo.

    Query params:
        page: Número da página (padrão: 1).
        per_page: Itens por página (padrão: 20, máximo: 100).
    """
    page = max(1, int(request.args.get("page", 1)))
    per_page = min(100, max(1, int(request.args.get("per_page", 20))))
    offset = (page - 1) * per_page

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) AS total FROM transferencias WHERE id_ativo=%s",
                (id_ativo,),
            )
            total = cur.fetchone()["total"]

            rows = _fetch_all(
                cur,
                "SELECT * FROM transferencias WHERE id_ativo=%s ORDER BY id DESC LIMIT %s OFFSET %s",
                (id_ativo, per_page, offset),
            )

    return jsonify({
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": (total + per_page - 1) // per_page,
        "items": rows,
    })


@app.route("/api/transferencias/estoque")
def ativos_em_estoque() -> Response:
    """
    Lista todos os ativos com status 'Estoque' em todas as tabelas de equipamentos.

    Returns:
        JSON com lista unificada de ativos disponíveis em estoque.
    """
    resultado: list[dict] = []

    with get_db() as conn:
        with conn.cursor() as cur:
            for tbl, tipo in _TABELA_POR_TIPO.items():
                rows = _fetch_all(
                    cur,
                    f"SELECT id_ativo, modelo, fazenda, setor, updated_at "
                    f"FROM {tipo} WHERE status='Estoque' ORDER BY updated_at DESC",
                )
                for r in rows:
                    resultado.append({**r, "tipo_equipamento": tbl})

    return jsonify(resultado)


# ═══════════════════════════════════════════════════════════════════════════════
# BUSCA GLOBAL
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/api/busca")
def busca_global() -> Response:
    """Busca global em todas as tabelas principais de equipamentos."""
    q = request.args.get("q", "").strip()
    if not q:
        return jsonify([])

    resultados: list[dict] = []
    
    tabelas_busca = [
        ("Celular",          "celulares",          ["id_ativo", "responsavel", "modelo", "fazenda", "numero", "setor", "cargo", "num_serie", "imei_1"]),
        ("Celular Ponto",    "celulares_ponto",    ["id_ativo", "responsavel", "modelo", "fazenda", "num_turma", "funcao", "num_serie"]),
        ("Celular Inspeção", "celulares_inspecao", ["id_ativo", "responsavel", "modelo", "fazenda", "numero", "id_sistema", "num_serie"]),
        ("Celular Turma",    "celulares_turma",    ["id_ativo", "responsavel", "modelo", "fazenda", "num_turma", "num_serie", "imei_1"]),
        ("Computador",       "computadores",       ["id_ativo", "responsavel", "modelo", "fazenda", "marca", "numero_serie", "setor", "cargo"]),
        ("Impressora",       "impressoras",        ["id_ativo", "responsavel", "modelo", "fazenda", "marca", "ip_rede", "setor", "numero_serie"]),
        ("Estabilizador",    "estabilizadores",    ["id_ativo", "modelo", "fazenda", "setor", "num_serie", "uso"]),
        ("Starlink",         "starlink",           ["id_ativo", "responsavel", "modelo", "fazenda", "setor", "num_serie", "ip_rede"]),
    ]

    with get_db() as conn:
        with conn.cursor() as cur:
            for tipo_nome, tabela, colunas in tabelas_busca:
                condicoes = " OR ".join([f"{col} ILIKE %s" for col in colunas])
                sel_responsavel = "responsavel" if "responsavel" in colunas else "fazenda as responsavel"
                query = f"SELECT id_ativo, status, modelo, {sel_responsavel} FROM {tabela} WHERE {condicoes} ORDER BY id_ativo LIMIT 10"
                params = [f"%{q}%"] * len(colunas)
                
                rows = _fetch_all(cur, query, tuple(params))
                for r in rows:
                    resultados.append({
                        "tipo": tipo_nome,
                        "id_ativo": r["id_ativo"],
                        "responsavel": r.get("responsavel", ""),
                        "modelo": r.get("modelo", ""),
                        "status": r.get("status", "")
                    })

    return jsonify(resultados[:30])


# ═══════════════════════════════════════════════════════════════════════════════
# UTILITÁRIOS / GERADOR DE ID
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/api/utils/siglas")
def get_siglas() -> Response:
    """Exporta as tabelas de siglas do id_generator para o frontend."""
    return jsonify({
        "tipo": SIGLAS_TIPO,
        "local": SIGLAS_LOCAL,
        "setor": SIGLAS_SETOR,
    })


@app.route("/api/utils/gerar-id")
def api_sugerir_id() -> Response:
    """Retorna uma sugestão de ID baseada em tipo, fazenda (local) e setor."""
    tipo = request.args.get("tipo")
    local = request.args.get("local")
    setor = request.args.get("setor")

    if not all([tipo, local, setor]):
        return jsonify({"ok": False, "msg": "Parâmetros 'tipo', 'local' e 'setor' são obrigatórios"}), 400

    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                novo_id = sugerir_id(cur, tipo, local, setor)
        return jsonify({"ok": True, "id_sugerido": novo_id})
    except Exception as e:
        return jsonify({"ok": False, "msg": f"Erro ao gerar ID: {str(e)}"}), 500


@app.route("/api/utils/gerar-id-turma")
def api_sugerir_id_turma() -> Response:
    """
    Retorna o próximo ID disponível para Celular Turma no formato CL-TRM-NN.

    Celulares de turma são itinerantes e não possuem fazenda/localidade fixa.
    """
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                novo_id = sugerir_id_turma(cur)
        return jsonify({"ok": True, "id_sugerido": novo_id})
    except Exception as e:
        return jsonify({"ok": False, "msg": f"Erro ao gerar ID Turma: {str(e)}"}), 500


@app.route("/api/utils/parse-coleta", methods=["POST"])
def parse_coleta() -> Response:
    """
    Recebe um arquivo .txt gerado pelo COLETAR_PC.bat e retorna os campos
    mapeados corretamente para os campos do formulário de Computadores.

    O arquivo segue o formato INI simplificado (chave=valor, seção [hardware]).
    Suporta codificações UTF-8 com e sem BOM.

    Returns:
        JSON com {ok: True, data: {...}} ou {ok: False, msg: ...}.
    """
    if 'file' not in request.files:
        return jsonify({"ok": False, "msg": "Nenhum arquivo enviado"}), 400

    file = request.files['file']
    if not file.filename:
        return jsonify({"ok": False, "msg": "Arquivo vazio"}), 400

    try:
        content_bytes = file.read()
        # Trata UTF-8 com BOM (gerado pelo PowerShell 5.x) e sem BOM
        try:
            content = content_bytes.decode("utf-8-sig")
        except UnicodeDecodeError:
            content = content_bytes.decode("utf-8", errors="replace")

        # Mapeamento: chave no .txt -> campo no formulário/banco
        # Alinhado com os campos gerados pelo COLETAR_PC.bat
        mapping: dict[str, str] = {
            "tipo":                "tipo",
            "marca":               "marca",
            "modelo":              "modelo",
            "num_serie":           "numero_serie",
            "processador":         "processador",
            "memoria_ram":         "memoria_ram",
            "armazenamento":       "armazenamento",
            "sistema_operacional": "sistema_operacional",
            "versao_so":           "versao_so",
            "ip_rede":             "ip_rede",
            "mac_address":         "mac_address",
            "usuario":             "usuario_windows",
        }

        data: dict[str, Any] = {}
        for raw_line in content.splitlines():
            line = raw_line.strip()
            # Ignora linhas vazias e cabeçalhos de seção INI (ex: [hardware])
            if not line or line.startswith("["):
                continue
            if "=" not in line:
                continue
            key, _, val = line.partition("=")
            key = key.strip().lower()
            val = val.strip()
            if key in mapping and val:
                data[mapping[key]] = val

        if not data:
            return jsonify({"ok": False, "msg": "Arquivo inválido ou sem dados reconhecíveis"}), 422

        return jsonify({"ok": True, "data": data})

    except Exception as e:
        return jsonify({"ok": False, "msg": f"Erro ao processar arquivo: {str(e)}"}), 500


# ═══════════════════════════════════════════════════════════════════════════════
# INICIALIZAÇÃO
# ═══════════════════════════════════════════════════════════════════════════════

import traceback

@app.errorhandler(Exception)
def handle_exception(e):
    # Log safely to the current application directory
    crash_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "inventario_crash.log")
    try:
        with open(crash_file, "a", encoding="utf-8") as f:
            f.write(f"\n--- {datetime.now().isoformat()} ---\n")
            f.write(traceback.format_exc())
            f.write(f"\nURL: {request.url}\n")
    except Exception as log_err:
        print(f"Failed to write crash log: {log_err}")
    
    # RETURN TRACEBACK DIRECTLY FOR DEBUGGING ON RENDER
    tb = traceback.format_exc()
    html = f"<h3>Internal Server Error</h3><pre style='background:#f4f4f4;padding:15px;border-radius:8px;overflow-x:auto;'>{tb}</pre>"
    return html, 500


# ── Polling de mensagens (admin + usuário) ────────────────────────────────────
import traceback as _tb_mod
from auth_utils import viewer_required, admin_required, get_usuario_id

@app.route("/chamados/<int:chamado_id>/poll")
def poll_chamado(chamado_id: int):
    """Retorna as mensagens do chamado como JSON para o cliente fazer polling."""
    if not session.get("usuario_id"):
        return jsonify({"error": "auth"}), 401

    usuario_id = get_usuario_id()
    role = session.get("role", "")

    with acquire_conn() as conn:
        with conn.cursor() as cur:
            chamado = fetch_one(cur, "SELECT localidade_id, criado_por FROM chamados WHERE id = %s", (chamado_id,))
            if not chamado:
                return jsonify({"error": "not_found"}), 404
            # Viewer só acessa o próprio chamado da sua localidade
            if role == "viewer":
                if chamado["localidade_id"] != session.get("localidade_id") and chamado["criado_por"] != usuario_id:
                    return jsonify({"error": "forbidden"}), 403

            msgs = fetch_all(
                cur,
                """
                SELECT cm.id, cm.mensagem, cm.is_sistema,
                       u.nome AS autor_nome, u.role AS autor_role, u.id AS autor_id,
                       cm.criado_em,
                       ca.caminho_arquivo, ca.nome_arquivo
                FROM chamado_mensagens cm
                JOIN usuarios u ON u.id = cm.usuario_id
                LEFT JOIN chamado_anexos ca ON ca.mensagem_id = cm.id
                WHERE cm.chamado_id = %s
                ORDER BY cm.criado_em ASC
                """,
                (chamado_id,),
            )

    resultado = []
    for m in msgs:
        dt = m["criado_em"]
        if dt and hasattr(dt, "strftime"):
            if dt.tzinfo is not None:
                utc = dt.utctimetuple()
                dt = datetime(*utc[:6])
            dt = dt - timedelta(hours=3)
            dt_str = dt.strftime("%d/%m/%y %H:%M")
        elif isinstance(dt, str):
            dt_str = dt[:16].replace("T", " ")
        else:
            dt_str = ""

        resultado.append({
            "id": m["id"],
            "mensagem": m["mensagem"],
            "is_sistema": m["is_sistema"],
            "autor_nome": m["autor_nome"],
            "autor_role": m["autor_role"],
            "autor_id": m["autor_id"],
            "criado_em": dt_str,
            "caminho_arquivo": m["caminho_arquivo"],
            "nome_arquivo": m["nome_arquivo"],
        })

    return jsonify(resultado)


if __name__ == "__main__":
    print("\n" + "=" * 55)
    print("  SISTEMA DE INVENTARIO TI  v3.0.1-HOTFIX")
    print("  Banco: Supabase (PostgreSQL)")
    print("  Acesse: http://localhost:5000")
    print("=" * 55 + "\n")

    def _abrir_navegador() -> None:
        import time
        time.sleep(1.2)
        webbrowser.open("http://localhost:5000")

    threading.Thread(target=_abrir_navegador, daemon=True).start()
    app.run(debug=False, port=5000, host="0.0.0.0")
