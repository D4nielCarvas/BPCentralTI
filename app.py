"""
BP Central TI — Backend Flask v3.0
Banco: Supabase (PostgreSQL) via psycopg2-binary
Autor: Sistema BP Central TI
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

# ── Autenticação e controle de acesso ────────────────────────────────────────
# P7: importação no topo para uso nos decorators das rotas de API
from api_utils import _list_table, log_historico
from auth_utils import login_required, admin_required, viewer_required, get_usuario_id, get_localidade_filter

# ── Criptografia de campos sensíveis ─────────────────────────────────────────
# P1: Fernet (AES-128-CBC + HMAC-SHA256) para senhas de Starlink e Celulares Turma
from crypto_utils import encrypt_field, decrypt_field

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
# RISCO CRÍTICO: um fallback fixo/previsível permite ao atacante forjar cookies de sessão.
# P3 CORRIGIDO: usa os.environ[] — falha rápido se a variável não estiver configurada.
# Gere com: python -c "import secrets; print(secrets.token_hex(32))"
try:
    app.secret_key = os.environ["SECRET_KEY"]  # P3: sem fallback inseguro
except KeyError:
    raise RuntimeError(
        "\n\nSECRET_KEY não definida no ambiente.\n"
        "Configure no .env antes de iniciar o servidor:\n"
        "  SECRET_KEY=<chave aleatória de 64+ caracteres>\n"
        "Gere com: python -c \"import secrets; print(secrets.token_hex(32))\"\n"
        "RISCO: sem SECRET_KEY forte, cookies de sessão são falsificáveis."
    ) from None

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

# ── Rate limiting (P12) ───────────────────────────────────────────────────────
# Protege rotas de polling e APIs públicas contra abuso/DoS.
# storage_uri="memory://" é adequado para single-process (gunicorn -w 1).
# Em multi-worker, substitua por Redis: storage_uri="redis://localhost:6379"
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=[],   # P12: sem limite global — aplicado rota a rota
    storage_uri="memory://",
)

# Blueprints existentes
from blueprints.celulares import celulares_bp

from blueprints.api_ativos import bp as api_ativos_bp
from blueprints.api_estoque import bp as api_estoque_bp
from blueprints.api_pedidos import bp as api_pedidos_bp
from blueprints.api_manutencoes import bp as api_manutencoes_bp

app.register_blueprint(celulares_bp)

app.register_blueprint(api_ativos_bp)
app.register_blueprint(api_estoque_bp)
app.register_blueprint(api_pedidos_bp)
app.register_blueprint(api_manutencoes_bp)


# Blueprints do sistema multi-tenant (Tarefas 8-10)
from blueprints.auth import auth_bp
from blueprints.fazenda import fazenda_bp
from blueprints.admin_pedidos import admin_pedidos_bp
from blueprints.admin import admin_bp
from blueprints.chamados import chamados_bp
from blueprints.admin_chamados import admin_chamados_bp
from blueprints.apoio import apoio_bp
from blueprints.remessas import remessas_bp

app.register_blueprint(auth_bp)
app.register_blueprint(fazenda_bp)
app.register_blueprint(admin_pedidos_bp)
app.register_blueprint(admin_bp)
app.register_blueprint(chamados_bp)
app.register_blueprint(admin_chamados_bp)
app.register_blueprint(apoio_bp)
app.register_blueprint(remessas_bp)


# ── Filtro Jinja2: formata data em horário de Brasília (UTC-3) ────────────────
@app.template_filter('fdt')
def formata_data_br(dt):
    """Converte datetime UTC → BRT (America/Sao_Paulo) e formata como dd/mm/aa HH:MM."""
    from zoneinfo import ZoneInfo
    BRT = ZoneInfo("America/Sao_Paulo")

    if not dt:
        return ''
    if isinstance(dt, str):
        try:
            dt = datetime.fromisoformat(dt.replace('Z', '+00:00'))
        except Exception:
            return dt[:16].replace('T', ' ')

    # Garante que tem tzinfo; se vier naive, assume UTC
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=ZoneInfo("UTC"))

    # Converte para BRT independente de qual timezone veio
    dt = dt.astimezone(BRT)
    return dt.strftime('%d/%m/%y %H:%M')


@app.context_processor
def inject_permissions():
    from auth_utils import has_permission
    return dict(has_permission=has_permission)

@app.context_processor
def injetar_notificacoes():
    """Injeta notificações não lidas no template global (para usuários autorizados).

    P11 CORRIGIDO: implementa cache de sessão com TTL de 30 segundos.
    Sem cache, esta função executava uma query ao banco em CADA requisição
    (inclusive assets, APIs, etc.), criando carga desnecessária no Supabase.
    Com cache, a query é reexecutada apenas quando o TTL expirar.

    Complexidade: O(1) em cache hit; O(1) na query (índice em usuario_id + lida).
    """
    is_master = session.get("is_admin_master")
    perms = session.get("permissoes") or {}
    pode_ver = is_master or perms.get("responder_chamados") or session.get("role") == "admin"

    if session.get("usuario_id") and pode_ver:
        # P11: verifica cache de sessão — atualiza apenas se TTL de 30s expirou
        agora = datetime.utcnow()
        cache_ts_raw = session.get("_notif_cache_ts")
        cache_valido = (
            cache_ts_raw is not None
            and (agora - datetime.fromisoformat(cache_ts_raw)).total_seconds() < 30
            and "_notif_cache" in session
        )

        if cache_valido:
            cached = session["_notif_cache"]
            return dict(
                qtd_notificacoes=cached["qtd"],
                notificacoes_lista=cached["lista"],
            )

        # Cache expirado ou ausente — executa query e atualiza cache de sessão
        try:
            with get_db() as conn:
                with conn.cursor() as cur:
                    # Contagem de não lidas
                    cur.execute(
                        "SELECT COUNT(*) as qtd FROM notificacoes WHERE usuario_id = %s AND lida = FALSE",
                        (session.get("usuario_id"),)
                    )
                    qtd_notificacoes = cur.fetchone()["qtd"]

                    # Lista das últimas 5 não lidas
                    ultimas = _fetch_all(
                        cur,
                        """SELECT id, chamado_id, mensagem, criado_em
                           FROM notificacoes
                           WHERE usuario_id = %s AND lida = FALSE
                           ORDER BY id DESC LIMIT 5""",
                        (session.get("usuario_id"),)
                    )

            # Armazena resultado no cache de sessão com timestamp
            session["_notif_cache"] = {"qtd": qtd_notificacoes, "lista": ultimas}
            session["_notif_cache_ts"] = agora.isoformat()
            session.modified = True  # Força persistência do cache na sessão

            return dict(qtd_notificacoes=qtd_notificacoes, notificacoes_lista=ultimas)
        except Exception:
            # Banco indisponível — retorna silenciosamente sem quebrar a renderização da página
            return dict(qtd_notificacoes=0, notificacoes_lista=[])
    return dict(qtd_notificacoes=0, notificacoes_lista=[])

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


# P4 CORRIGIDO: redefinições locais de _fetch_all/_fetch_one removidas.
# Os aliases _fetch_all = fetch_all e _fetch_one = fetch_one (definidos acima, linha ~29)
# têm a mesma assinatura (cur, query, params) e são importados de db_layer.
# Manter duas definições causava shadowing silencioso e mascarava divergências futuras.


# ── Helper: log de histórico ──────────────────────────────────────────────────

# ── Helper: validação de arquivo ──────────────────────────────────────────────

import magic

def validate_file_mime(file, allowed_mimes: set) -> bool:
    """Detecta o MIME real baseado na assinatura binária do arquivo."""
    header = file.read(2048)
    file.seek(0)
    mime = magic.from_buffer(header, mime=True)
    return mime in allowed_mimes

def allowed_file(filename: str) -> bool:
    """Verifica se o arquivo possui extensão PDF permitida."""
    return "." in filename and filename.rsplit(".", 1)[1].lower() == "pdf"


# ── Helper: listagem genérica ─────────────────────────────────────────────────

# ═══════════════════════════════════════════════════════════════════════════════
# FRONTEND
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/")
def index():
    """
    Rota raiz — redireciona com base no estado de autenticação e role.

    - Não autenticado → /login
    - Admin ou Viewer com permissões avançadas → renderiza o painel principal (index.html)
    - Viewer restrito → /fazenda/itens (portal de fazenda)
    """
    if "usuario_id" not in session:
        return redirect(url_for("auth.login"))
        
    from auth_utils import has_permission
    if session.get("role") == "viewer":
        # Se for um viewer, mas tiver permissão para ver ou editar o dashboard principal, permite acesso
        if has_permission("ver_equipamentos") or has_permission("editar_equipamentos") or has_permission("ver_dashboard"):
            return render_template("index.html")
        else:
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
    if not file.filename or not validate_file_mime(file, {"application/pdf"}):
        return jsonify({"ok": False, "msg": "Tipo de arquivo não permitido. Envie apenas PDF."}), 400

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
        return jsonify({"ok": True, "msg": "Banco OK"})
    except Exception as e:
        return jsonify({"ok": False, "msg": f"Erro de conexão: {str(e)}"}), 500

# ═══════════════════════════════════════════════════════════════════════════════
# NOTIFICAÇÕES (POLLING PUSH DESKTOP)
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/api/notificacoes/poll")
def poll_notificacoes() -> Response:
    """
    Retorna as notificações não lidas mais recentes.
    Usado pelo frontend para disparar notificações push desktop.
    """
    is_master = session.get("is_admin_master")
    perms = session.get("permissoes") or {}
    pode_ver = is_master or perms.get("responder_chamados") or session.get("role") == "admin"
    
    if not (session.get("usuario_id") and pode_ver):
        return jsonify({"ok": False, "notificacoes": []}), 403

    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                ultimas = _fetch_all(
                    cur,
                    """SELECT id, chamado_id, mensagem, criado_em
                       FROM notificacoes
                       WHERE usuario_id = %s AND lida = FALSE
                       ORDER BY id DESC LIMIT 5""",
                    (session.get("usuario_id"),)
                )
        return jsonify({"ok": True, "notificacoes": ultimas})
    except Exception as e:
        return jsonify({"ok": False, "msg": str(e), "notificacoes": []}), 500

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


# DESCARTES
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/api/descartes", methods=["GET"])
@login_required
def listar_descartes() -> Response:
    """Lista todos os descartes registrados."""
    with get_db() as conn:
        with conn.cursor() as cur:
            rows = _fetch_all(cur, "SELECT * FROM descartes ORDER BY id DESC")
    return jsonify(rows)


@app.route("/api/pedidos/<int:pid>/upload-nota", methods=["POST"])
@admin_required
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
    
    allowed_mimes = {"application/pdf", "image/jpeg", "image/png"}
    if not file.filename or not validate_file_mime(file, allowed_mimes):
        return jsonify({"ok": False, "msg": "Tipo de arquivo não permitido. Envie apenas PDF ou imagens JPG/PNG."}), 400

    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""

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
@admin_required
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
@login_required
def historico_global() -> Response:
    """Retorna o histórico completo (últimos 500 registros) para a aba Histórico."""
    with get_db() as conn:
        with conn.cursor() as cur:
            rows = _fetch_all(cur, "SELECT * FROM historico ORDER BY id DESC LIMIT 500")
    return jsonify(rows)


@app.route("/api/historico/<id_ativo>")
@login_required
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
@login_required
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

# DEPRECATED: A rota /api/gerar_id foi removida (P13). Use /api/utils/gerar-id.


@app.route("/api/siglas")
@login_required
def api_siglas() -> Response:
    """Retorna os dicionários de siglas válidas para geração de IDs."""
    return jsonify({
        "tipos": SIGLAS_TIPO,
        "localidades": SIGLAS_LOCAL,
        "setores": SIGLAS_SETOR,
    })


@app.route("/api/importar_coleta", methods=["POST"])
@admin_required
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
@admin_required
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
    if tipo_transf == "Usuario para Usuario" and not d.get("responsavel_destino"):
        return jsonify({"ok": False, "msg": "responsavel_destino é obrigatório para transferência entre usuários"}), 400

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
                    except ValueError as e:
                        app.logger.warning(f"Regen ID falhou para {id_ativo}: {e}")
                        return jsonify({
                            "ok": True,
                            "msg": "Transferência registrada com sucesso!",
                            "aviso": f"Aviso: Não foi possível gerar novo ID automaticamente. Erro: {e}"
                        })

    return jsonify({"ok": True, "msg": "Transferência registrada com sucesso!"})


@app.route("/api/transferencias", methods=["GET"])
@login_required
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
@login_required
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
@login_required
def ativos_em_estoque() -> Response:
    """
    Lista todos os ativos com status 'Estoque' em todas as tabelas de equipamentos.

    Returns:
        JSON com lista unificada de ativos disponíveis em estoque.
    """
    resultado: list[dict] = []

    with get_db() as conn:
        with conn.cursor() as cur:
            for tipo_nome, nome_tabela in _TABELA_POR_TIPO.items():
                rows = _fetch_all(
                    cur,
                    f"SELECT id_ativo, modelo, fazenda, setor, updated_at "
                    f"FROM {nome_tabela} WHERE status='Estoque' ORDER BY updated_at DESC",
                )
                for r in rows:
                    resultado.append({**r, "tipo_equipamento": tipo_nome})

    return jsonify(resultado)


# ═══════════════════════════════════════════════════════════════════════════════
# BUSCA GLOBAL
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/api/busca")
@login_required
def busca_global() -> Response:
    """Busca global em todas as tabelas principais de equipamentos."""
    q = request.args.get("q", "").strip()
    if not q:
        return jsonify([])

    resultados: list[dict] = []
    
    tabelas_busca = [
        ("Celular",          "celulares",          ["id_ativo", "responsavel", "modelo", "fazenda", "numero", "setor", "cargo", "num_serie", "imei_1"]),
        ("Celular Ponto",    "celulares_ponto",    ["id_ativo", "responsavel", "modelo", "fazenda", "num_turma", "funcao", "num_serie"]),
        ("Celular Inspeção", "celulares_inspecao", ["id_ativo", "responsavel", "modelo", "fazenda", "id_sistema", "num_serie"]),
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
    
    # P2 CORRIGIDO: Retorna traceback apenas se FLASK_ENV=development ou debug=True
    is_dev = app.debug or os.environ.get("FLASK_ENV") == "development"
    if is_dev:
        tb = traceback.format_exc()
        html = f"<h3>Internal Server Error</h3><pre style='background:#f4f4f4;padding:15px;border-radius:8px;overflow-x:auto;'>{tb}</pre>"
        return html, 500
    else:
        return jsonify({"ok": False, "msg": "Erro interno do servidor."}), 500


# ── Polling de mensagens (admin + usuário) ────────────────────────────────────
import traceback as _tb_mod
from auth_utils import viewer_required, admin_required, get_usuario_id

@app.route("/chamados/<int:chamado_id>/poll")
@limiter.limit("60/minute")  # P12: rate limiting
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

    response = jsonify(resultado)
    response.headers["X-Poll-Interval"] = "5"  # P12: informa o intervalo ao client
    return response


if __name__ == "__main__":
    print("\n" + "=" * 55)
    print("  SISTEMA DE BP Central TI.0.1-HOTFIX")
    print("  Banco: Supabase (PostgreSQL)")
    print("  Acesse: http://localhost:5000")
    print("=" * 55 + "\n")

    def _abrir_navegador() -> None:
        import time
        time.sleep(1.2)
        webbrowser.open("http://localhost:5000")

    threading.Thread(target=_abrir_navegador, daemon=True).start()
    app.run(debug=False, port=5000, host="0.0.0.0")
