"""
BP Central TI — Backend Flask v3.0
Banco: Supabase (PostgreSQL) via psycopg2-binary
"""

from __future__ import annotations

import os
import sys
import threading
import traceback
import webbrowser
from datetime import date, datetime
from typing import Optional

import psycopg2.extras
from dotenv import load_dotenv
from flask import Flask, jsonify, request, session

from utils.db_layer import acquire_conn, fetch_all, fetch_one, init_pool, close_pool
get_db = acquire_conn
_fetch_all = fetch_all
_fetch_one = fetch_one

from utils.id_generator import SIGLAS_LOCAL, SIGLAS_SETOR

FAZENDA_PARA_SIGLA: dict[str, str] = {v: k for k, v in SIGLAS_LOCAL.items()}
SETOR_PARA_SIGLA: dict[str, str]   = {v: k for k, v in SIGLAS_SETOR.items()}

load_dotenv()


def resource_path(relative_path: str) -> str:
    """Retorna o caminho absoluto para um recurso, compatível com PyInstaller."""
    base_path: str = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_path, relative_path)


app = Flask(__name__, template_folder=resource_path("templates"))

try:
    app.secret_key = os.environ["SECRET_KEY"]
except KeyError:
    raise RuntimeError(
        "SECRET_KEY não definida no ambiente. Configure no .env antes de iniciar o servidor."
    ) from None

if getattr(sys, "frozen", False):
    application_path = os.path.dirname(sys.executable)
else:
    application_path = os.path.dirname(os.path.abspath(__file__))

UPLOAD_FOLDER: str = os.path.join(application_path, "database", "termos")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

DATABASE_URL: str = os.environ["SUPABASE_DATABASE_URL"]

with app.app_context():
    init_pool(minconn=2, maxconn=10)

import atexit
import logging
import logging.handlers
atexit.register(close_pool)

from utils.extensions import limiter
limiter.init_app(app)

from flask.json.provider import DefaultJSONProvider

class CustomJSONProvider(DefaultJSONProvider):
    def default(self, o):
        if isinstance(o, datetime):
            return o.isoformat()
        if isinstance(o, date):
            return o.isoformat()
        return super().default(o)

app.json = CustomJSONProvider(app)

from blueprints.celulares import celulares_bp
from blueprints.api_ativos import bp as api_ativos_bp
from blueprints.api_estoque import bp as api_estoque_bp
from blueprints.api_pedidos import bp as api_pedidos_bp
from blueprints.api_manutencoes import bp as api_manutencoes_bp
from blueprints.api_chips import api_chips_bp

app.register_blueprint(celulares_bp)
app.register_blueprint(api_ativos_bp)
app.register_blueprint(api_estoque_bp)
app.register_blueprint(api_pedidos_bp)
app.register_blueprint(api_manutencoes_bp)
app.register_blueprint(api_chips_bp)

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

from blueprints.api_qrcode import bp as api_qrcode_bp
app.register_blueprint(api_qrcode_bp)


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

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=ZoneInfo("UTC"))

    dt = dt.astimezone(BRT)
    return dt.strftime('%d/%m/%y %H:%M')


@app.context_processor
def inject_permissions():
    from utils.auth_utils import has_permission
    return dict(has_permission=has_permission)


@app.context_processor
def injetar_notificacoes():
    """Injeta notificações não lidas no template global com cache de sessão (TTL de 30s)."""
    usuario_id = session.get("usuario_id")
    if usuario_id:
        from datetime import timezone
        agora = datetime.now(timezone.utc)
        cache_ts_raw = session.get("_notif_cache_ts")
        cache_valido = False
        if cache_ts_raw is not None and "_notif_cache" in session:
            try:
                ts = datetime.fromisoformat(cache_ts_raw)
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=timezone.utc)
                if (agora - ts).total_seconds() < 30:
                    cache_valido = True
            except Exception:
                cache_valido = False

        if cache_valido:
            cached = session["_notif_cache"]
            return dict(
                qtd_notificacoes=cached["qtd"],
                notificacoes_lista=cached["lista"],
            )

        try:
            with get_db() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT COUNT(*) as qtd FROM notificacoes WHERE usuario_id = %s AND lida = FALSE",
                        (usuario_id,)
                    )
                    qtd_notificacoes = cur.fetchone()["qtd"]

                    ultimas = []
                    try:
                        ultimas = _fetch_all(
                            cur,
                            """SELECT id, chamado_id, pedido_id, mensagem, criado_em
                               FROM notificacoes
                               WHERE usuario_id = %s AND lida = FALSE
                               ORDER BY id DESC LIMIT 5""",
                            (usuario_id,)
                        )
                    except Exception:
                        conn.rollback()
                        ultimas = _fetch_all(
                            cur,
                            """SELECT id, chamado_id, mensagem, criado_em
                               FROM notificacoes
                               WHERE usuario_id = %s AND lida = FALSE
                               ORDER BY id DESC LIMIT 5""",
                            (usuario_id,)
                        )

            session["_notif_cache"] = {"qtd": qtd_notificacoes, "lista": ultimas}
            session["_notif_cache_ts"] = agora.isoformat()
            session.modified = True

            return dict(qtd_notificacoes=qtd_notificacoes, notificacoes_lista=ultimas)
        except Exception:
            return dict(qtd_notificacoes=0, notificacoes_lista=[])
    return dict(qtd_notificacoes=0, notificacoes_lista=[])


def row_to_dict(row: Optional[psycopg2.extras.RealDictRow]) -> Optional[dict]:
    """Converte uma linha RealDictRow em dicionário Python puro."""
    return dict(row) if row else None


def rows_to_list(rows: list[psycopg2.extras.RealDictRow]) -> list[dict]:
    """Converte uma lista de RealDictRow em lista de dicionários Python puros."""
    return [dict(r) for r in rows]


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


_crash_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "inventario_crash.log")
_crash_handler = logging.handlers.RotatingFileHandler(
    _crash_file,
    maxBytes=5 * 1024 * 1024,
    backupCount=3,
    encoding="utf-8",
)
_crash_handler.setFormatter(logging.Formatter("%(message)s"))
_crash_logger = logging.getLogger("inventario.crash")
_crash_logger.setLevel(logging.ERROR)
_crash_logger.addHandler(_crash_handler)
_crash_logger.propagate = False


@app.errorhandler(Exception)
def handle_exception(e):
    from werkzeug.exceptions import HTTPException

    if isinstance(e, HTTPException):
        return e

    try:
        _crash_logger.error(
            "\n--- %s ---\n%s\nURL: %s",
            datetime.now().isoformat(),
            traceback.format_exc(),
            request.url,
        )
    except Exception as log_err:
        print(f"Failed to write crash log: {log_err}")

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