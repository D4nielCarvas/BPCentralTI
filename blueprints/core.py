from flask import Blueprint, redirect, url_for, session, render_template, Response, jsonify
from utils.auth_utils import has_permission
from utils.db_layer import acquire_conn, fetch_one

core_bp = Blueprint('core', __name__)

@core_bp.route("/")
def index():
    if "usuario_id" not in session:
        return redirect(url_for("auth.login"))
        
    if session.get("role") == "viewer":
        # Se for um viewer, mas tiver permissão para ver ou editar o dashboard principal, permite acesso
        if has_permission("ver_equipamentos") or has_permission("editar_equipamentos") or has_permission("ver_dashboard"):
            return render_template("index.html")
        else:
            return redirect(url_for("fazenda.listar_itens"))
            
    return render_template("index.html")


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
    
    return Response(row["dados"], mimetype=row["mimetype"])


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
