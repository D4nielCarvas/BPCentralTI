from __future__ import annotations
from flask import Blueprint, Response, jsonify, request
from utils.db_layer import acquire_conn, fetch_all, fetch_one

api_chips_bp = Blueprint("api_chips", __name__, url_prefix="/api/chips")

_STATUS_VALIDOS = {"Disponível", "Em Uso", "Perdido", "Cancelado"}


@api_chips_bp.route("", methods=["GET"])
def listar_chips() -> Response:
    """Lista todas as linhas (chips) e sua alocação atual."""
    busca = request.args.get("q", "").strip()
    status = request.args.get("status", "").strip()

    query = """
        SELECT
            l.id, l.numero, l.status,
            a.id_ativo, f.nome AS responsavel,
            a.data_inicio
        FROM linhas_celular l
        LEFT JOIN atribuicoes_linha a ON l.id = a.linha_id AND a.data_devolucao IS NULL
        LEFT JOIN funcionarios f ON a.funcionario_id = f.id
        WHERE 1=1
    """
    params: list = []

    if status:
        query += " AND l.status = %s"
        params.append(status)

    if busca:
        query += " AND (l.numero ILIKE %s OR f.nome ILIKE %s OR a.id_ativo ILIKE %s)"
        params.extend([f"%{busca}%", f"%{busca}%", f"%{busca}%"])

    query += " ORDER BY l.numero ASC"

    with acquire_conn() as conn:
        with conn.cursor() as cur:
            rows = fetch_all(cur, query, tuple(params))

    return jsonify(rows)


@api_chips_bp.route("/<linha_id>/historico", methods=["GET"])
def historico_chip(linha_id: str) -> Response:
    """Retorna a timeline completa de um chip específico."""
    query = """
        SELECT
            a.id_ativo, f.nome AS responsavel,
            a.data_inicio, a.data_devolucao
        FROM atribuicoes_linha a
        LEFT JOIN funcionarios f ON a.funcionario_id = f.id
        WHERE a.linha_id = %s
        ORDER BY a.data_inicio DESC
    """
    with acquire_conn() as conn:
        with conn.cursor() as cur:
            rows = fetch_all(cur, query, (linha_id,))

    return jsonify(rows)


@api_chips_bp.route("", methods=["POST"])
def criar_chip() -> Response:
    """Cria uma nova linha (chip) no cadastro."""
    body = request.get_json(silent=True) or {}
    numero = (body.get("numero") or "").strip()
    status = (body.get("status") or "Disponível").strip()

    if not numero:
        return jsonify({"ok": False, "msg": "O número da linha é obrigatório."}), 400
    if status not in _STATUS_VALIDOS:
        return jsonify({"ok": False, "msg": f"Status inválido: {status}"}), 400

    try:
        with acquire_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO linhas_celular (numero, status) VALUES (%s, %s)",
                    (numero, status),
                )
        return jsonify({"ok": True, "msg": f"Chip '{numero}' cadastrado com sucesso!"}), 201
    except Exception as exc:
        if "unique" in str(exc).lower() or "duplicat" in str(exc).lower():
            return jsonify({"ok": False, "msg": f"O número '{numero}' já está cadastrado."}), 409
        return jsonify({"ok": False, "msg": f"Erro ao cadastrar: {exc}"}), 500


@api_chips_bp.route("/<linha_id>", methods=["PUT"])
def atualizar_chip(linha_id: str) -> Response:
    """Atualiza o número e/ou status de uma linha existente."""
    body = request.get_json(silent=True) or {}
    numero = (body.get("numero") or "").strip()
    status = (body.get("status") or "").strip()

    if not numero:
        return jsonify({"ok": False, "msg": "O número da linha é obrigatório."}), 400
    if status and status not in _STATUS_VALIDOS:
        return jsonify({"ok": False, "msg": f"Status inválido: {status}"}), 400

    try:
        with acquire_conn() as conn:
            with conn.cursor() as cur:
                existing = fetch_one(cur, "SELECT id FROM linhas_celular WHERE id = %s", (linha_id,))
                if not existing:
                    return jsonify({"ok": False, "msg": "Chip não encontrado."}), 404

                cur.execute(
                    "UPDATE linhas_celular SET numero = %s, status = %s WHERE id = %s",
                    (numero, status or "Disponível", linha_id),
                )
        return jsonify({"ok": True, "msg": "Chip atualizado com sucesso!"})
    except Exception as exc:
        if "unique" in str(exc).lower() or "duplicat" in str(exc).lower():
            return jsonify({"ok": False, "msg": f"O número '{numero}' já pertence a outro chip."}), 409
        return jsonify({"ok": False, "msg": f"Erro ao atualizar: {exc}"}), 500
