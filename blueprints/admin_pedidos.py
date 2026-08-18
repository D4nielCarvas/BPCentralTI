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

from utils.auth_utils import admin_required, get_usuario_id
from utils.db_layer import acquire_conn, fetch_all, fetch_one

admin_pedidos_bp = Blueprint("admin_pedidos", __name__, url_prefix="/admin")

_STATUS_VALIDOS = frozenset({"pendente", "em_analise", "aprovado", "recusado", "concluido"})

import re

def _tentar_baixa_estoque(
    cur, 
    pedido_id: int, 
    descricao: str, 
    localidade_id: int | None, 
    admin_id: int,
    item_direto: str | None = None,
    quantidade_direta: int | None = None,
) -> str:
    """
    Tenta realizar a baixa automática de itens de estoque para um pedido aprovado/concluído.
    Prioriza dados estruturados (item_direto, quantidade_direta) com fallback para regex na descrição.
    Complexidade: O(1) tempo | O(1) espaço.
    """
    # 1. Obtenção dos dados do item
    item_nome = (item_direto or "").strip()
    quantidade = quantidade_direta if (quantidade_direta is not None and quantidade_direta > 0) else None

    if not item_nome or quantidade is None:
        # Regex para extração (limpeza aprimorada do dado recebido na descrição legada)
        match_item = re.search(r'(?i)(?:item do estoque|produto do estoque|item|produto|estoque)\s*:\s*([^\n\r|]+)', descricao or "")
        match_qtd = re.search(r'(?i)(?:quantidade|qtd|quant)\s*:\s*(\d+)', descricao or "")
        
        if match_item:
            item_nome = match_item.group(1).strip()
        if match_qtd:
            quantidade = int(match_qtd.group(1))

    if not item_nome:
        return "Baixa não realizada: Item não identificado no pedido."
        
    quantidade = quantidade if (quantidade and quantidade > 0) else 1

    # 2. Busca e Lock da tabela (Boas Práticas de Transação)
    cur.execute(
        "SELECT id, item, quantidade FROM estoque WHERE item ILIKE %s AND (localidade_id = %s OR localidade_id IS NULL) FOR UPDATE",
        (f"%{item_nome}%", localidade_id)
    )
    itens = cur.fetchall()
    
    if not itens:
        return f"Baixa não realizada: Item '{item_nome}' sem saldo ou inexistente no estoque."
    
    # 3. Resolução Estratégica de Ambiguidade
    estoque_item = None
    exatos = [i for i in itens if i["item"].lower() == item_nome.lower()]
    
    if len(exatos) >= 1:
        estoque_item = exatos[0]
    elif len(itens) == 1:
        if len(item_nome) < 3 and item_nome.lower() not in itens[0]["item"].lower():
             return f"Baixa não realizada: O termo '{item_nome}' é genérico demais. Especifique melhor."
        estoque_item = itens[0]
    else:
        nomes_sugestoes = ", ".join([i["item"] for i in itens[:3]])
        return f"Baixa não realizada: Ambiguidade para '{item_nome}'. Qual deles? (Encontrados: {nomes_sugestoes}...)"
        
    # 4. Checagem de Saldo (Princípio de Early Return)
    nova_qtd = estoque_item["quantidade"] - quantidade
    if nova_qtd < 0:
        return f"Baixa não realizada: Saldo insuficiente do produto '{estoque_item['item']}' (Requerido: {quantidade}, Disponível: {estoque_item['quantidade']})."
        
    # 5. Persistência Atômica
    cur.execute(
        "UPDATE estoque SET quantidade = %s, updated_at = NOW() WHERE id = %s",
        (nova_qtd, estoque_item["id"])
    )
    
    cur.execute(
        """INSERT INTO estoque_movimentacoes (estoque_id, tipo, quantidade, motivo, responsavel)
           VALUES (%s, 'saida', %s, %s, %s)""",
        (estoque_item["id"], quantidade, f"Baixa via Pedido #{pedido_id} (Aprovado)", f"Admin ID {admin_id}")
    )
    
    return f"Baixa automática com sucesso: {quantidade}x '{estoque_item['item']}' (Saldo restante: {nova_qtd})."



# ═══════════════════════════════════════════════════════════════════════════════
# LISTAGEM GERAL DE PEDIDOS
# ═══════════════════════════════════════════════════════════════════════════════

_URGENCIAS_VALIDAS = ["baixa", "media", "alta", "urgente"]

@admin_pedidos_bp.route("/pedidos")
@admin_required
def listar_pedidos_admin():
    """
    Lista todos os pedidos de todas as localidades.

    Query params:
        status      — Filtra por status do pedido.
        localidade  — Filtra por localidade_id.
        urgencia    — Filtra por nível de urgência.
        q           — Busca textual no item, motivo ou descrição.
    """
    filtro_status = request.args.get("status", "").strip()
    filtro_local = request.args.get("localidade", "").strip()
    filtro_urgencia = request.args.get("urgencia", "").strip().lower()
    busca = request.args.get("q", "").strip()

    params: list = []
    query = """
        SELECT
            pv.*,
            COALESCE(l.nome, 'Fazenda')  AS localidade_nome,
            COALESCE(u.nome, 'Usuário')  AS usuario_nome
        FROM pedidos_viewer pv
        LEFT JOIN localidades l ON l.id = pv.localidade_id
        LEFT JOIN usuarios    u ON u.id = pv.usuario_id
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
            # Total de pedidos urgentes/críticos pendentes de atendimento (com resiliência)
            qtd_pedidos_urgentes = 0
            try:
                alertas_urgentes = fetch_one(
                    cur,
                    """
                    SELECT COUNT(*) as qtd
                    FROM pedidos_viewer
                    WHERE status IN ('pendente', 'em_analise')
                      AND urgencia IN ('alta', 'urgente', 'critica')
                    """
                )
                qtd_pedidos_urgentes = alertas_urgentes["qtd"] if alertas_urgentes else 0
            except Exception:
                conn.rollback()
                qtd_pedidos_urgentes = 0

    return render_template(
        "admin/pedidos.html",
        pedidos=pedidos,
        localidades=localidades,
        filtro_status=filtro_status,
        filtro_local=filtro_local,
        filtro_urgencia=filtro_urgencia,
        qtd_pedidos_urgentes=qtd_pedidos_urgentes,
        busca=busca,
        status_validos=sorted(_STATUS_VALIDOS),
        urgencias=_URGENCIAS_VALIDAS,
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
                SELECT pv.*, 
                       COALESCE(l.nome, 'Fazenda') AS localidade_nome, 
                       COALESCE(u.nome, 'Usuário') AS usuario_nome
                FROM pedidos_viewer pv
                LEFT JOIN localidades l ON l.id = pv.localidade_id
                LEFT JOIN usuarios    u ON u.id = pv.usuario_id
                WHERE pv.id = %s
                """,
                (pedido_id,),
            )
            if not pedido:
                flash(f"Pedido #{pedido_id} não encontrado.", "warning")
                return redirect(url_for("admin_pedidos.listar_pedidos_admin"))

            historico = []
            try:
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
            except Exception:
                pass

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
                "SELECT id, status, item, quantidade, descricao, localidade_id FROM pedidos_viewer WHERE id = %s",
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

            # Baixa no estoque ocorre no status 'aprovado' (ou 'concluido' se aprovação for ignorada)
            observacao_final = observacao or ""
            if novo_status in ("aprovado", "concluido"):
                # Verifica se já houve baixa com sucesso no histórico deste pedido
                ja_baixou = fetch_one(
                    cur,
                    """
                    SELECT id FROM pedido_viewer_historico 
                    WHERE pedido_id = %s AND observacao ILIKE %s
                    """,
                    (pedido_id, "%[Estoque] Baixa automática com sucesso%"),
                )
                if not ja_baixou:
                    msg_baixa = _tentar_baixa_estoque(
                        cur,
                        pedido_id,
                        pedido.get("descricao") or "",
                        pedido.get("localidade_id"),
                        admin_id,
                        item_direto=pedido.get("item"),
                        quantidade_direta=pedido.get("quantidade"),
                    )
                    observacao_final += f"\n[Estoque] {msg_baixa}"
                    observacao_final = observacao_final.strip()
            else:
                observacao_final = observacao_final.strip() or observacao

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

