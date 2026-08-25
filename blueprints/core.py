from flask import Blueprint, redirect, url_for, session, render_template, Response, jsonify
from utils.auth_utils import has_permission
from utils.db_layer import acquire_conn, fetch_all, fetch_one

core_bp = Blueprint('core', __name__)

@core_bp.route("/")
def index():
    if "usuario_id" not in session:
        return redirect(url_for("auth.login"))
        
    role = session.get("role", "")
    is_admin = session.get("is_admin_master", False) or role == "admin"

    # Administradores acessam o painel central de TI
    if is_admin:
        return render_template("index.html")

    # Usuários com papel de Apoio vão para o módulo de inspeção
    if role == "apoio":
        return redirect(url_for("apoio.celulares_inspecao"))

    # Usuários com papel de Viewer (e qualquer papel não-admin) vão estritamente para o Portal Fazenda
    return redirect(url_for("fazenda.listar_itens"))


@core_bp.route("/termos/<filename>")
@core_bp.route("/arquivos/<filename>")
def serve_termo(filename: str) -> tuple[str, int] | Response:
    """Serve arquivos (PDF/imagens) diretamente do banco de dados (arquivos_storage)."""
    with acquire_conn() as conn:
        with conn.cursor() as cur:
            row = fetch_one(cur, "SELECT dados, mimetype FROM arquivos_storage WHERE nome_arquivo=%s", (filename,))
    
    if not row:
        return (
            f"<h3>Arquivo não encontrado</h3>"
            f"<p>O arquivo ({filename}) não está disponível no servidor.</p>",
            404,
        )
    
    resp = Response(row["dados"], mimetype=row["mimetype"])
    resp.headers["Cache-Control"] = "public, max-age=86400, immutable"
    return resp


@core_bp.route("/api/health")
def health_check() -> Response:
    """Verifica a conexão com o banco de dados."""
    try:
        with acquire_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
        return jsonify({"ok": True, "msg": "Banco OK"})
    except Exception as e:
        return jsonify({"ok": False, "msg": f"Erro de conexão: {str(e)}"}), 500


@core_bp.route("/api/notificacoes/poll")
def poll_notificacoes() -> Response:
    """
    Retorna as notificações não lidas mais recentes para o usuário logado.
    Identifica flags de urgência para disparo sonoro e push no frontend.
    """
    usuario_id = session.get("usuario_id")
    if not usuario_id:
        return jsonify({"ok": False, "notificacoes": []}), 401

    try:
        with acquire_conn() as conn:
            with conn.cursor() as cur:
                ultimas = []
                try:
                    ultimas = fetch_all(
                        cur,
                        """SELECT id, chamado_id, pedido_id, mensagem, criado_em
                           FROM notificacoes
                           WHERE usuario_id = %s AND lida = FALSE
                           ORDER BY id DESC LIMIT 10""",
                        (usuario_id,)
                    )
                except Exception:
                    conn.rollback()
                    ultimas = fetch_all(
                        cur,
                        """SELECT id, chamado_id, mensagem, criado_em
                           FROM notificacoes
                           WHERE usuario_id = %s AND lida = FALSE
                           ORDER BY id DESC LIMIT 10""",
                        (usuario_id,)
                    )

                for n in ultimas:
                    msg = n.get("mensagem") or ""
                    n["is_urgente"] = "[URGENTE]" in msg or "🚨" in msg

        return jsonify({"ok": True, "notificacoes": ultimas})
    except Exception as e:
        return jsonify({"ok": False, "msg": str(e), "notificacoes": []}), 500

