"""
blueprints/admin_pedidos.py — Rotas admin para gestão dos pedidos_viewer.

Protegidas por @admin_required: apenas usuários com role='admin' acessam.

Fluxo de atualização de status:
    1. Valida que novo_status é um valor permitido.
    2. Lê o status anterior diretamente do banco (nunca do body).
    3. Insere registro em pedido_viewer_historico.
    4. Atualiza pedidos_viewer.atualizado_em via trigger (ou explicitamente).

Complexidade: O(1) update + insert (operações por chave primária).
Segurança: admin_required rejeita com 403 qualquer usuário não-admin.
"""

from __future__ import annotations

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for

from auth_utils import admin_required, get_usuario_id
from db_layer import acquire_conn, fetch_all, fetch_one

admin_pedidos_bp = Blueprint("admin_pedidos", __name__, url_prefix="/admin")

_STATUS_VALIDOS = frozenset({"pendente", "em_analise", "aprovado", "recusado", "concluido"})


# ═══════════════════════════════════════════════════════════════════════════════
# LISTAGEM GERAL DE PEDIDOS
# ═══════════════════════════════════════════════════════════════════════════════

@admin_pedidos_bp.route("/pedidos")
@admin_required
def listar_pedidos_admin():
    """
    Lista todos os pedidos de todas as localidades.

    Query params:
        status      — Filtra por status do pedido.
        localidade  — Filtra por localidade_id.
        q           — Busca textual na descrição.
    """
    filtro_status = request.args.get("status", "").strip()
    filtro_local = request.args.get("localidade", "").strip()
    busca = request.args.get("q", "").strip()

    params: list = []
    query = """
        SELECT
            pv.id,
            pv.descricao,
            pv.status,
            pv.criado_em,
            pv.atualizado_em,
            l.nome  AS localidade_nome,
            u.nome  AS usuario_nome
        FROM pedidos_viewer pv
        JOIN localidades l ON l.id = pv.localidade_id
        JOIN usuarios    u ON u.id = pv.usuario_id
        WHERE 1=1
    """

    if filtro_status and filtro_status in _STATUS_VALIDOS:
        query += " AND pv.status = %s"
        params.append(filtro_status)

    if filtro_local:
        query += " AND pv.localidade_id = %s"
        params.append(filtro_local)

    if busca:
        query += " AND pv.descricao ILIKE %s"
        params.append(f"%{busca}%")

    query += " ORDER BY pv.id DESC"

    with acquire_conn() as conn:
        with conn.cursor() as cur:
            pedidos = fetch_all(cur, query, tuple(params))
            localidades = fetch_all(
                cur, "SELECT id, nome FROM localidades ORDER BY nome ASC"
            )

    return render_template(
        "admin/pedidos.html",
        pedidos=pedidos,
        localidades=localidades,
        filtro_status=filtro_status,
        filtro_local=filtro_local,
        busca=busca,
        status_validos=sorted(_STATUS_VALIDOS),
    )


# ═══════════════════════════════════════════════════════════════════════════════
# DETALHE E ATUALIZAÇÃO DE STATUS
# ═══════════════════════════════════════════════════════════════════════════════

@admin_pedidos_bp.route("/pedidos/<int:pedido_id>")
@admin_required
def detalhe_pedido_admin(pedido_id: int):
    """Exibe o detalhe de um pedido com histórico completo e formulário de status."""
    with acquire_conn() as conn:
        with conn.cursor() as cur:
            pedido = fetch_one(
                cur,
                """
                SELECT pv.*, l.nome AS localidade_nome, u.nome AS usuario_nome
                FROM pedidos_viewer pv
                JOIN localidades l ON l.id = pv.localidade_id
                JOIN usuarios    u ON u.id = pv.usuario_id
                WHERE pv.id = %s
                """,
                (pedido_id,),
            )
            if not pedido:
                abort(404)

            historico = fetch_all(
                cur,
                """
                SELECT pvh.*, u.nome AS alterado_por_nome
                FROM pedido_viewer_historico pvh
                LEFT JOIN usuarios u ON u.id = pvh.alterado_por
                WHERE pvh.pedido_id = %s
                ORDER BY pvh.alterado_em ASC
                """,
                (pedido_id,),
            )

    return render_template(
        "admin/detalhe_pedido.html",
        pedido=pedido,
        historico=historico,
        status_validos=sorted(_STATUS_VALIDOS),
    )


@admin_pedidos_bp.route("/pedidos/<int:pedido_id>/status", methods=["POST"])
@admin_required
def atualizar_status_pedido(pedido_id: int):
    """
    Atualiza o status de um pedido e registra em pedido_viewer_historico.

    POST form:
        novo_status — Um dos valores em _STATUS_VALIDOS.
        observacao  — Comentário opcional do admin.

    Passos executados em transação única:
        1. Valida novo_status.
        2. Lê status_anterior do banco.
        3. Insere em pedido_viewer_historico.
        4. Atualiza pedidos_viewer (trigger cuida do atualizado_em).
    """
    novo_status = (request.form.get("novo_status") or "").strip()
    observacao = (request.form.get("observacao") or "").strip() or None
    admin_id = get_usuario_id()

    if novo_status not in _STATUS_VALIDOS:
        flash(f"Status inválido: '{novo_status}'.", "danger")
        return redirect(url_for("admin_pedidos.detalhe_pedido_admin", pedido_id=pedido_id))

    with acquire_conn() as conn:
        with conn.cursor() as cur:
            # 2. Lê status anterior (do banco — nunca do body)
            pedido = fetch_one(
                cur,
                "SELECT id, status FROM pedidos_viewer WHERE id = %s",
                (pedido_id,),
            )
            if not pedido:
                abort(404)

            status_anterior = pedido["status"]

            # Sem mudança real — evita registro inútil no histórico
            if status_anterior == novo_status:
                flash("O status selecionado é igual ao atual.", "info")
                return redirect(
                    url_for("admin_pedidos.detalhe_pedido_admin", pedido_id=pedido_id)
                )

            # 3. Insere histórico
            cur.execute(
                """
                INSERT INTO pedido_viewer_historico
                    (pedido_id, status_anterior, status_novo, observacao, alterado_por)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (pedido_id, status_anterior, novo_status, observacao, admin_id),
            )

            # 4. Atualiza o pedido (trigger atualiza atualizado_em automaticamente)
            cur.execute(
                "UPDATE pedidos_viewer SET status = %s WHERE id = %s",
                (novo_status, pedido_id),
            )

    flash(f"Status atualizado para '{novo_status}' com sucesso.", "success")
    return redirect(url_for("admin_pedidos.detalhe_pedido_admin", pedido_id=pedido_id))
