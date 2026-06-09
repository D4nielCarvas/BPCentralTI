from flask import Blueprint, jsonify, Response
from utils.auth_utils import login_required
from utils.db_layer import acquire_conn, fetch_all

api_historico_bp = Blueprint('api_historico', __name__)

@api_historico_bp.route("/api/historico")
@login_required
def historico_global() -> Response:
    """Retorna o histórico completo (últimos 500 registros) para a aba Histórico."""
    with acquire_conn() as conn:
        with conn.cursor() as cur:
            rows = fetch_all(cur, "SELECT * FROM historico ORDER BY id DESC LIMIT 500")
    return jsonify(rows)

@api_historico_bp.route("/api/historico/<id_ativo>")
@login_required
def historico_ativo(id_ativo: str) -> Response:
    """Retorna o histórico de alterações de um ativo específico."""
    with acquire_conn() as conn:
        with conn.cursor() as cur:
            rows = fetch_all(
                cur,
                "SELECT * FROM historico WHERE id_ativo=%s ORDER BY id DESC",
                (id_ativo,),
            )
    return jsonify(rows)
