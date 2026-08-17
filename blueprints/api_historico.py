from flask import Blueprint, jsonify, request, Response
from utils.auth_utils import login_required
from utils.db_layer import acquire_conn, fetch_all

api_historico_bp = Blueprint('api_historico', __name__)

# Colunas retornadas — evita overfetch com SELECT *
_COLS = "id, id_ativo, tipo_equipamento, acao, data_hora, usuario"

_LIMIT_MAX = 200  # teto de segurança para evitar dumps acidentais


@api_historico_bp.route("/api/historico")
@login_required
def historico_global() -> Response:
    """Retorna histórico global com paginação cursor-based.

    [FIX-10] Substitui LIMIT 500 hardcoded por paginação real via cursor.
    Parâmetros de query:
        limit  (int, 1-200): quantidade de registros por página. Default: 100.
        before (int):        id do último registro recebido — retorna registros
                             com id < before (página seguinte). Omitir para 1ª página.

    Exemplo:
        GET /api/historico?limit=50
        GET /api/historico?limit=50&before=1200  (próxima página)
    """
    try:
        limit = min(int(request.args.get("limit", 100)), _LIMIT_MAX)
        limit = max(limit, 1)
    except (ValueError, TypeError):
        limit = 100

    before = request.args.get("before")

    with acquire_conn() as conn:
        with conn.cursor() as cur:
            if before:
                try:
                    before_id = int(before)
                except (ValueError, TypeError):
                    return jsonify({"ok": False, "msg": "Parâmetro 'before' deve ser inteiro."}), 400

                rows = fetch_all(
                    cur,
                    f"SELECT {_COLS} FROM historico WHERE id < %s ORDER BY id DESC LIMIT %s",
                    (before_id, limit),
                )
            else:
                rows = fetch_all(
                    cur,
                    f"SELECT {_COLS} FROM historico ORDER BY id DESC LIMIT %s",
                    (limit,),
                )

    # Cursor para a próxima página (id do último item retornado)
    next_cursor = rows[-1]["id"] if rows else None

    return jsonify({
        "rows": rows,
        "next_cursor": next_cursor,
        "count": len(rows),
    })


@api_historico_bp.route("/api/historico/<id_ativo>")
@login_required
def historico_ativo(id_ativo: str) -> Response:
    """Retorna o histórico completo de um ativo específico.

    [FIX-10] Seleciona colunas explícitas em vez de SELECT *.
    """
    with acquire_conn() as conn:
        with conn.cursor() as cur:
            rows = fetch_all(
                cur,
                f"SELECT {_COLS} FROM historico WHERE id_ativo=%s ORDER BY id DESC",
                (id_ativo,),
            )
    return jsonify(rows)
