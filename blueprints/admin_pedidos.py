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

import re

def _tentar_baixa_estoque(cur, pedido_id: int, descricao: str, localidade_id: int, admin_id: int) -> str:
    """
    Complexidade: O(1) de tempo (considerando índice em item/localidade) e O(1) espaço.
    """
    # Exige `:` como separador obrigatório para evitar captura parcial (ex: "item do estoque")
    match_item = re.search(r'(?i)(?:item do estoque|produto do estoque|item|produto|estoque)\s*:\s*([^\n\r]+)', descricao)
    match_qtd = re.search(r'(?i)(?:quantidade|qtd|quant)\s*:\s*(\d+)', descricao)
    
    if not match_item:
        return "Baixa não realizada: Item não identificado (Use o padrão 'Item: nome')."
        
    item_nome = match_item.group(1).strip().rstrip('\r')
    quantidade = int(match_qtd.group(1)) if match_qtd else 1
    
    if quantidade <= 0:
        return "Baixa não realizada: Quantidade inválida."

    cur.execute(
        "SELECT id, item, quantidade FROM estoque WHERE item ILIKE %s AND (localidade_id = %s OR localidade_id IS NULL) FOR UPDATE",
        (f"%{item_nome}%", localidade_id)
    )
    itens = cur.fetchall()
    
    if not itens:
        return f"Baixa não realizada: Item '{item_nome}' não encontrado nesta localidade."
    
    estoque_item = None
    if len(itens) > 1:
        exatos = [i for i in itens if i["item"].lower() == item_nome.lower()]
        if len(exatos) == 1:
            estoque_item = exatos[0]
        else:
            return f"Baixa não realizada: Ambiguidade para '{item_nome}'."
    else:
        estoque_item = itens[0]
        
    nova_qtd = estoque_item["quantidade"] - quantidade
    if nova_qtd < 0:
        return f"Baixa não realizada: Saldo insuficiente de '{estoque_item['item']}' (Req: {quantidade}, Disp: {estoque_item['quantidade']})."
        
    cur.execute(
        "UPDATE estoque SET quantidade = %s, updated_at = NOW() WHERE id = %s",
        (nova_qtd, estoque_item["id"])
    )
    
    cur.execute(
        """INSERT INTO estoque_movimentacoes (estoque_id, tipo, quantidade, motivo, responsavel)
           VALUES (%s, 'saida', %s, %s, %s)""",
        (estoque_item["id"], quantidade, f"Baixa auto - Pedido #{pedido_id}", f"Admin ID {admin_id}")
    )
    return f"Baixa automática realizada: {quantidade}x '{estoque_item['item']}'. Saldo atual: {nova_qtd}."



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
        etiqueta    — Filtra por etiqueta_id.
        q           — Busca textual na descrição.
    """
    filtro_status = request.args.get("status", "").strip()
    filtro_local = request.args.get("localidade", "").strip()
    filtro_etiqueta = request.args.get("etiqueta", "").strip()
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
    """Exibe o detalhe de um pedido com histórico completo, etiquetas e formulário de status."""
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
                "SELECT id, status, descricao, localidade_id FROM pedidos_viewer WHERE id = %s",
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

            if status_anterior != "concluido" and novo_status == "concluido":
                msg_baixa = _tentar_baixa_estoque(cur, pedido_id, pedido["descricao"], pedido["localidade_id"], admin_id)
                observacao_final = observacao or ""
                observacao_final += f"\n[Estoque] {msg_baixa}"
                observacao_final = observacao_final.strip()
            else:
                observacao_final = observacao

            # 3. Insere histórico
            cur.execute(
                """
                INSERT INTO pedido_viewer_historico
                    (pedido_id, status_anterior, status_novo, observacao, alterado_por)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (pedido_id, status_anterior, novo_status, observacao_final, admin_id),
            )

            # 4. Atualiza o pedido (trigger atualiza atualizado_em automaticamente)
            cur.execute(
                "UPDATE pedidos_viewer SET status = %s WHERE id = %s",
                (novo_status, pedido_id),
            )

    flash(f"Status atualizado para '{novo_status}' com sucesso.", "success")
    return redirect(url_for("admin_pedidos.detalhe_pedido_admin", pedido_id=pedido_id))

