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
import traceback
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
from utils.db_layer import acquire_conn, fetch_all, fetch_one, init_pool, close_pool
# Mantém get_db como alias para rotas ainda não migradas
get_db = acquire_conn
_fetch_all = fetch_all
_fetch_one = fetch_one

# ── Autenticação e controle de acesso ────────────────────────────────────────
# P7: importação no topo para uso nos decorators das rotas de API
from utils.api_utils import _list_table, log_historico
from utils.auth_utils import login_required, admin_required, viewer_required, get_usuario_id, get_localidade_filter

# ── Criptografia de campos sensíveis ─────────────────────────────────────────
# P1: Fernet (AES-128-CBC + HMAC-SHA256) para senhas de Starlink e Celulares Turma
from utils.crypto_utils import encrypt_field, decrypt_field

# ── Importações dos módulos internos ──────────────────────────────────────────
from utils.id_generator import (
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

from blueprints.core import core_bp
from blueprints.api_dashboard import api_dashboard_bp
from blueprints.api_descartes import api_descartes_bp
from blueprints.api_transferencias import api_transferencias_bp
from blueprints.api_historico import api_historico_bp
from blueprints.api_import_export import api_import_export_bp
from blueprints.api_busca import api_busca_bp
from blueprints.api_tutoriais import bp as api_tutoriais_bp


app.register_blueprint(core_bp)
app.register_blueprint(api_dashboard_bp)
app.register_blueprint(api_descartes_bp)
app.register_blueprint(api_transferencias_bp)
app.register_blueprint(api_historico_bp)
app.register_blueprint(api_import_export_bp)
app.register_blueprint(api_busca_bp)
app.register_blueprint(api_tutoriais_bp)



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
    from utils.auth_utils import has_permission
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


if __name__ == "__main__":
    def _abrir_navegador() -> None:
        import time
        time.sleep(1.2)
        webbrowser.open("http://localhost:5000")

    threading.Thread(target=_abrir_navegador, daemon=True).start()
    app.run(debug=False, port=5000, host="0.0.0.0")