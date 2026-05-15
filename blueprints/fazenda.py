"""
blueprints/fazenda.py — Blueprint de acesso restrito por localidade (viewers).

Fornece visibilidade de ativos, estoque e manutenções filtrados pela localidade
do usuário logado, além do CRUD de pedidos_viewer.

Patterns: Blueprint (Flask) + Filtro de Tenant (get_localidade_filter).
Segurança:
    - Todas as rotas exigem autenticação via @viewer_required.
    - Risco IDOR (Insecure Direct Object Reference) mitigado:
      pedidos são sempre filtrados por usuario_id OU localidade_id da sessão —
      nunca confiar em IDs recebidos sem validação adicional.
    - O campo localidade_id gravado no pedido vem SEMPRE da sessão, nunca do body.
Complexidade: O(n) listagem, O(1) CRUD por id primário.
"""

from __future__ import annotations

from typing import Any

from flask import Blueprint, abort, flash, redirect, render_template, request, session, url_for

from auth_utils import get_localidade_filter, get_usuario_id, viewer_required
from db_layer import acquire_conn, fetch_all, fetch_one

fazenda_bp = Blueprint("fazenda", __name__, url_prefix="/fazenda")

# Statuses válidos para pedidos_viewer
_STATUS_VALIDOS = frozenset({"pendente", "em_analise", "aprovado", "recusado", "concluido"})

# Tabelas de equipamentos para o painel da fazenda
_TABELAS_EQUIPAMENTOS: list[tuple[str, str]] = [
    ("celulares",          "Celular"),
    ("celulares_ponto",    "Celular Ponto"),
    ("celulares_inspecao", "Celular Inspeção"),
    ("celulares_turma",    "Celular Turma"),
    ("computadores",       "Computador"),
    ("impressoras",        "Impressora"),
    ("estabilizadores",    "Estabilizador"),
    ("starlink",           "Starlink"),
]


# ── Helper interno ────────────────────────────────────────────────────────────

def _build_localidade_clause(
    localidade_id: int | None,
    params: list[Any],
    prefix: str = "",
) -> str:
    """
    Adiciona a cláusula AND localidade_id = %s na query se localidade_id for fornecido.

    Args:
        localidade_id: ID da localidade do viewer (None para admin = sem filtro).
        params: Lista de parâmetros da query — modificada in-place.
        prefix: Prefixo de tabela para queries com JOIN (ex: "e." → "e.localidade_id").

    Returns:
        Fragmento SQL a ser concatenado na query (string vazia ou " AND ...").
    """
    if localidade_id is not None:
        params.append(localidade_id)
        col = f"{prefix}localidade_id" if prefix else "localidade_id"
        return f" AND {col} = %s"
    return ""


# ═══════════════════════════════════════════════════════════════════════════════
# ITENS / EQUIPAMENTOS ATIVOS DA FAZENDA
# ═══════════════════════════════════════════════════════════════════════════════

@fazenda_bp.route("/itens")
@viewer_required
def listar_itens():
    """
    Lista todos os equipamentos ativos vinculados à localidade do viewer.

    Para admins (localidade_id = None), retorna equipamentos de todas as localidades.
    Query params: q (busca textual), tipo (filtrar por tipo de equipamento).
    """
    localidade_id = get_localidade_filter()
    busca = request.args.get("q", "").strip()
    tipo_filtro = request.args.get("tipo", "").strip()

    todos_itens: list[dict] = []

    with acquire_conn() as conn:
        with conn.cursor() as cur:
            for tabela, tipo_nome in _TABELAS_EQUIPAMENTOS:
                if tipo_filtro and tipo_filtro != tipo_nome:
                    continue

                params: list[Any] = ["Ativo"]
                col_setor = "setor"
                col_responsavel = "responsavel"

                if tabela == "celulares_ponto":
                    col_setor = "funcao AS setor"
                elif tabela == "estabilizadores":
                    col_responsavel = "NULL AS responsavel"

                query = f"SELECT id_ativo, fazenda, {col_setor}, {col_responsavel}, modelo, status FROM {tabela} WHERE status = %s"
                query += _build_localidade_clause(localidade_id, params)

                if busca:
                    busca_conds = ["id_ativo ILIKE %s", "modelo ILIKE %s"]
                    params_busca = [f"%{busca}%"] * 2

                    if tabela != "estabilizadores":
                        busca_conds.append("responsavel ILIKE %s")
                        params_busca.append(f"%{busca}%")

                    query += " AND (" + " OR ".join(busca_conds) + ")"
                    params += params_busca

                query += " ORDER BY id_ativo LIMIT 200"
                rows = fetch_all(cur, query, tuple(params))
                for r in rows:
                    todos_itens.append({**r, "tipo": tipo_nome})

    tipos_disponiveis = [t for _, t in _TABELAS_EQUIPAMENTOS]

    return render_template(
        "fazenda/itens.html",
        itens=todos_itens,
        busca=busca,
        tipo_filtro=tipo_filtro,
        tipos=tipos_disponiveis,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# ESTOQUE DA FAZENDA
# ═══════════════════════════════════════════════════════════════════════════════

@fazenda_bp.route("/estoque")
@viewer_required
def listar_estoque():
    """
    Lista itens de estoque vinculados à localidade do viewer.

    Exibe apenas itens com quantidade > 0 por padrão.
    Query params: q (busca textual), mostrar_zerado (bool).
    """
    localidade_id = get_localidade_filter()
    busca = request.args.get("q", "").strip()
    mostrar_zerado = request.args.get("mostrar_zerado", "0") == "1"

    params: list[Any] = []
    query = "SELECT * FROM estoque WHERE 1=1"

    if localidade_id:
        query += " AND (localidade_id IS NULL OR localidade_id = %s)"
        params.append(localidade_id)

    if not mostrar_zerado:
        query += " AND quantidade > 0"

    if busca:
        query += " AND (item ILIKE %s OR cod_pedido ILIKE %s OR localizacao ILIKE %s)"
        params += [f"%{busca}%"] * 3

    query += " ORDER BY item ASC"

    with acquire_conn() as conn:
        with conn.cursor() as cur:
            itens = fetch_all(cur, query, tuple(params))

    return render_template(
        "fazenda/estoque.html",
        itens=itens,
        busca=busca,
        mostrar_zerado=mostrar_zerado,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# MANUTENÇÕES DA FAZENDA
# ═══════════════════════════════════════════════════════════════════════════════

@fazenda_bp.route("/manutencoes")
@viewer_required
def listar_manutencoes():
    """
    Lista manutenções vinculadas à localidade do viewer.

    Query params: status (filtro de status), q (busca textual).
    """
    localidade_id = get_localidade_filter()
    filtro_status = request.args.get("status", "").strip()
    busca = request.args.get("q", "").strip()

    params: list[Any] = []
    query = "SELECT * FROM manutencoes WHERE 1=1"
    query += _build_localidade_clause(localidade_id, params)

    if filtro_status:
        query += " AND status = %s"
        params.append(filtro_status)

    if busca:
        query += " AND (id_ativo ILIKE %s OR modelo ILIKE %s OR problema_relatado ILIKE %s)"
        params += [f"%{busca}%"] * 3

    query += " ORDER BY id DESC"

    with acquire_conn() as conn:
        with conn.cursor() as cur:
            manutencoes = fetch_all(cur, query, tuple(params))

    return render_template(
        "fazenda/manutencoes.html",
        manutencoes=manutencoes,
        filtro_status=filtro_status,
        busca=busca,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# PEDIDOS DO VIEWER
# ═══════════════════════════════════════════════════════════════════════════════

@fazenda_bp.route("/pedidos")
@viewer_required
def listar_pedidos():
    """
    Lista pedidos criados pelo usuário logado.

    Viewers veem apenas seus próprios pedidos.
    Admins veem todos os pedidos de sua localidade (ou de todas, se admin global).
    Query params: status (filtro).
    """
    usuario_id = get_usuario_id()
    localidade_id = get_localidade_filter()
    filtro_status = request.args.get("status", "").strip()

    params: list[Any] = []

    # Viewer: filtra pelos pedidos da sua própria localidade (fazenda)
    # Admin: filtra por localidade (ou tudo, se sem localidade_id)
    if session.get("role") == "viewer":
        query = """
            SELECT pv.*, l.nome AS localidade_nome
            FROM pedidos_viewer pv
            JOIN localidades l ON l.id = pv.localidade_id
            WHERE pv.localidade_id = %s
        """
        params.append(localidade_id)
    else:
        query = """
            SELECT pv.*, l.nome AS localidade_nome
            FROM pedidos_viewer pv
            JOIN localidades l ON l.id = pv.localidade_id
            WHERE 1=1
        """
        if localidade_id:
            query += " AND pv.localidade_id = %s"
            params.append(localidade_id)

    if filtro_status and filtro_status in _STATUS_VALIDOS:
        query += " AND pv.status = %s"
        params.append(filtro_status)

    query += " ORDER BY pv.id DESC"

    with acquire_conn() as conn:
        with conn.cursor() as cur:
            pedidos = fetch_all(cur, query, tuple(params))

    return render_template(
        "fazenda/pedidos.html",
        pedidos=pedidos,
        filtro_status=filtro_status,
        status_validos=sorted(_STATUS_VALIDOS),
    )


@fazenda_bp.route("/pedidos/novo", methods=["GET", "POST"])
@viewer_required
def novo_pedido():
    """
    Formulário para criar um novo pedido (GET) e processar o envio (POST).

    Segurança: localidade_id e usuario_id são lidos da sessão — nunca do body.
    Validação: descrição é obrigatória e limitada a 2000 caracteres.
    """
    localidade_id = get_localidade_filter()
    usuario_id = get_usuario_id()

    # Viewers sem localidade configurada não podem abrir pedidos
    if session.get("role") == "viewer" and not localidade_id:
        flash("Sua conta não está vinculada a uma localidade. Contate o administrador.", "danger")
        return redirect(url_for("fazenda.listar_pedidos"))

    if request.method == "POST":
        descricao = (request.form.get("descricao") or "").strip()
        etiqueta_ids = request.form.getlist("etiqueta_ids")  # lista de IDs selecionados

        if not descricao:
            flash("A descrição do pedido é obrigatória.", "warning")
            return render_template("fazenda/novo_pedido.html")

        if len(descricao) > 2000:
            flash("A descrição não pode ultrapassar 2000 caracteres.", "warning")
            return render_template("fazenda/novo_pedido.html", descricao=descricao)

        # Para admins sem localidade_id de sessão, usa a localidade do form
        loc_id = localidade_id or request.form.get("localidade_id")
        if not loc_id:
            flash("Localidade não identificada.", "danger")
            return render_template("fazenda/novo_pedido.html", descricao=descricao)

        with acquire_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO pedidos_viewer (localidade_id, usuario_id, descricao, status)
                    VALUES (%s, %s, %s, 'pendente')
                    RETURNING id
                    """,
                    (loc_id, usuario_id, descricao),
                )
                novo_id = cur.fetchone()["id"]

        flash("Pedido enviado com sucesso!", "success")
        return redirect(url_for("fazenda.detalhe_pedido", pedido_id=novo_id))

    etiquetas: list[dict] = []
    localidades: list[dict] = []
    with acquire_conn() as conn:
        with conn.cursor() as cur:
            etiquetas = fetch_all(cur, "SELECT id, nome, cor_hex FROM chamado_etiquetas ORDER BY nome ASC")
            if session.get("role") == "admin":
                localidades = fetch_all(
                    cur, "SELECT id, nome, tipo FROM localidades ORDER BY nome ASC"
                )

    item_pre_selecionado = request.args.get("item", "").strip()
    descricao_inicial = f"Solicito o item do estoque: {item_pre_selecionado}\nQuantidade: " if item_pre_selecionado else ""

    return render_template(
        "fazenda/novo_pedido.html",
        localidades=localidades,
        localidade_id_sessao=localidade_id,
        etiquetas=etiquetas,
        descricao=descricao_inicial,
    )


@fazenda_bp.route("/pedidos/<int:pedido_id>")
@viewer_required
def detalhe_pedido(pedido_id: int):
    """
    Exibe o detalhe de um pedido e seu histórico de status.

    Segurança (anti-IDOR):
        - Viewer: valida que o pedido pertence ao usuario_id da sessão.
        - Admin: acesso irrestrito.
    """
    usuario_id = get_usuario_id()
    role = session.get("role")

    with acquire_conn() as conn:
        with conn.cursor() as cur:
            pedido = fetch_one(
                cur,
                """
                SELECT pv.*, l.nome AS localidade_nome, u.nome AS usuario_nome
                FROM pedidos_viewer pv
                JOIN localidades l ON l.id = pv.localidade_id
                JOIN usuarios u ON u.id = pv.usuario_id
                WHERE pv.id = %s
                """,
                (pedido_id,),
            )

            if not pedido:
                abort(404)

            # Anti-IDOR: viewer só acessa seus próprios pedidos
            if role == "viewer" and pedido["usuario_id"] != usuario_id:
                abort(403)

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
        "fazenda/detalhe_pedido.html",
        pedido=pedido,
        historico=historico,
        status_validos=sorted(_STATUS_VALIDOS),
        role=role,
    )
