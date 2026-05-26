from flask import Blueprint, request, jsonify, Response
from typing import Any
from datetime import date
import psycopg2

from db_layer import acquire_conn as get_db, fetch_all as _fetch_all, fetch_one as _fetch_one, row_to_dict
from auth_utils import login_required, admin_required, get_fazenda_nome_filter
from crypto_utils import encrypt_field, decrypt_field
from api_utils import _list_table, log_historico

bp = Blueprint('api_pedidos', __name__, url_prefix='')

# PEDIDOS
# ═══════════════════════════════════════════════════════════════════════════════

@bp.route("/api/pedidos", methods=["GET"])
@admin_required
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


@bp.route("/api/pedidos", methods=["POST"])
@admin_required
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


@bp.route("/api/pedidos/<int:pid>", methods=["GET"])
@admin_required
def get_pedido(pid: int) -> Response:
    """Retorna dados de um pedido."""
    with get_db() as conn:
        with conn.cursor() as cur:
            row = _fetch_one(cur, "SELECT * FROM pedidos WHERE id=%s", (pid,))
    return jsonify(row)


@bp.route("/api/pedidos/<int:pid>", methods=["PUT"])
@admin_required
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
                    cur.execute("SELECT * FROM estoque WHERE id=%s FOR UPDATE", (eid,))
                    item_est = row_to_dict(cur.fetchone())
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
