from flask import Blueprint, request, jsonify, Response
from typing import Any
from datetime import date
import psycopg2

from utils.db_layer import acquire_conn as get_db, fetch_all as _fetch_all, fetch_one as _fetch_one, row_to_dict
from utils.auth_utils import login_required, admin_required, get_fazenda_nome_filter
from utils.crypto_utils import encrypt_field, decrypt_field
from utils.api_utils import _list_table, log_historico

bp = Blueprint('api_estoque', __name__, url_prefix='')

# ESTOQUE
# ═══════════════════════════════════════════════════════════════════════════════

@bp.route("/api/estoque", methods=["GET"])
@login_required
def listar_estoque() -> Response:
    """Lista itens do estoque geral com busca opcional."""
    busca = request.args.get("q", "")
    query = "SELECT * FROM estoque WHERE 1=1"
    params: list[Any] = []
    if busca:
        query += " AND (item ILIKE %s OR cod_pedido ILIKE %s)"
        params += [f"%{busca}%", f"%{busca}%"]
    query += " ORDER BY item ASC"
    with get_db() as conn:
        with conn.cursor() as cur:
            rows = _fetch_all(cur, query, tuple(params))
    return jsonify(rows)


@bp.route("/api/estoque_equipamentos", methods=["GET"])
@login_required
def listar_estoque_equipamentos() -> Response:
    """Lista todos os equipamentos com status 'Em Estoque' de todas as tabelas."""
    tabelas = [
        ("celulares",        "Celular"),
        ("celulares_ponto",  "Celular Ponto"),
        ("celulares_turma",  "Celular Turma"),
        ("computadores",     "Computador"),
        ("impressoras",      "Impressora"),
        ("estabilizadores",  "Estabilizador"),
        ("starlink",         "Starlink"),
    ]
    query_parts = []
    for tbl, label in tabelas:
        query_parts.append(
            f"SELECT id_ativo, modelo, fazenda, '{label}' as tipo_equipamento, status FROM {tbl} WHERE status = 'Estoque'"
        )

    query = " UNION ALL ".join(query_parts) + " ORDER BY id_ativo ASC"

    with get_db() as conn:
        with conn.cursor() as cur:
            rows = _fetch_all(cur, query)
    return jsonify(rows)


@bp.route("/api/localidades", methods=["GET"])
@login_required
def api_listar_localidades() -> Response:
    """Retorna todas as localidades para selects."""
    with get_db() as conn:
        with conn.cursor() as cur:
            rows = _fetch_all(cur, "SELECT id, nome FROM localidades ORDER BY nome ASC")
    return jsonify(rows)


@bp.route("/api/estoque", methods=["POST"])
@admin_required
def criar_estoque() -> Response:
    """Cadastra um novo item no estoque geral."""
    d = request.json
    localidade_id = d.get("localidade_id") or None
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO estoque (item,cod_pedido,quantidade,unidade,localizacao,observacoes,localidade_id) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s)",
                (
                    d["item"], d.get("cod_pedido"), d.get("quantidade", 0),
                    d.get("unidade", "un"), d.get("localizacao"), d.get("observacoes"),
                    localidade_id
                ),
            )
    return jsonify({"ok": True, "msg": "Item cadastrado!"})


@bp.route("/api/estoque/<int:eid>", methods=["GET"])
@admin_required
def get_estoque(eid: int) -> Response:
    """Retorna dados de um item de estoque pelo ID."""
    with get_db() as conn:
        with conn.cursor() as cur:
            row = _fetch_one(cur, "SELECT * FROM estoque WHERE id=%s", (eid,))
    return jsonify(row)


@bp.route("/api/estoque/<int:eid>", methods=["PUT"])
@admin_required
def atualizar_estoque(eid: int) -> Response:
    """Atualiza dados cadastrais de um item de estoque (não altera quantidade)."""
    d = request.json
    localidade_id = d.get("localidade_id") or None
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """UPDATE estoque SET item=%s,cod_pedido=%s,unidade=%s,localizacao=%s,
                   observacoes=%s,localidade_id=%s,updated_at=NOW() WHERE id=%s""",
                (d.get("item"), d.get("cod_pedido"), d.get("unidade"), d.get("localizacao"),
                 d.get("observacoes"), localidade_id, eid),
            )
    return jsonify({"ok": True, "msg": "Item atualizado!"})


@bp.route("/api/estoque/<int:eid>/movimentar", methods=["POST"])
@admin_required
def movimentar_estoque(eid: int) -> tuple[Response, int] | Response:
    """
    Registra entrada ou saída de um item de estoque.

    Usa SELECT FOR UPDATE para evitar race condition TOCTOU:
    dois requests simultâneos não conseguem ler e modificar o mesmo
    saldo concorrentemente — o segundo aguarda o commit do primeiro.

    Complexidade: O(1) — operação em linha única com lock pessimista.
    """
    d = request.json or {}
    tipo = d.get("tipo")
    if tipo not in ("entrada", "saida"):
        return jsonify({"ok": False, "msg": "tipo deve ser 'entrada' ou 'saida'"}), 400

    try:
        qtd = int(d.get("quantidade", 0))
    except (ValueError, TypeError):
        return jsonify({"ok": False, "msg": "Quantidade inválida"}), 400

    if qtd <= 0:
        return jsonify({"ok": False, "msg": "Quantidade deve ser maior que zero"}), 400

    with get_db() as conn:
        with conn.cursor() as cur:
            # FOR UPDATE: bloqueia a linha até o commit — elimina race condition
            cur.execute("SELECT * FROM estoque WHERE id=%s FOR UPDATE", (eid,))
            item = row_to_dict(cur.fetchone())
            if not item:
                return jsonify({"ok": False, "msg": "Item não encontrado"}), 404

            nova_qtd = item["quantidade"] + qtd if tipo == "entrada" else item["quantidade"] - qtd
            if nova_qtd < 0:
                return jsonify({"ok": False, "msg": "Estoque insuficiente!"}), 400

            cur.execute(
                "UPDATE estoque SET quantidade=%s,updated_at=NOW() WHERE id=%s",
                (nova_qtd, eid),
            )
            cur.execute(
                """INSERT INTO estoque_movimentacoes
                   (estoque_id,tipo,quantidade,motivo,responsavel)
                   VALUES (%s,%s,%s,%s,%s)""",
                (eid, tipo, qtd, d.get("motivo"), d.get("responsavel")),
            )

    label = "Entrada" if tipo == "entrada" else "Saída"
    return jsonify({"ok": True, "msg": f"{label} de {qtd} registrada! Saldo: {nova_qtd}", "nova_quantidade": nova_qtd})


@bp.route("/api/estoque/<int:eid>/movimentacoes", methods=["GET"])
@admin_required
def historico_estoque(eid: int) -> Response:
    """Retorna o histórico de movimentações de um item de estoque."""
    with get_db() as conn:
        with conn.cursor() as cur:
            rows = _fetch_all(
                cur,
                "SELECT * FROM estoque_movimentacoes WHERE estoque_id=%s ORDER BY id DESC",
                (eid,),
            )
    return jsonify(rows)


# ═══════════════════════════════════════════════════════════════════════════════

# IMPRESSORAS POR FAZENDA (para seleção no Toner)
# ═══════════════════════════════════════════════════════════════════════════════

@bp.route("/api/impressoras/por_fazenda")
@login_required
def impressoras_por_fazenda() -> Response:
    """Retorna impressoras filtradas por fazenda para uso no módulo de toners."""
    fazenda = request.args.get("fazenda", "Central")
    with get_db() as conn:
        with conn.cursor() as cur:
            rows = _fetch_all(
                cur,
                "SELECT id_ativo, modelo, ip_rede FROM impressoras WHERE fazenda=%s AND status='Ativo' ORDER BY id_ativo",
                (fazenda,),
            )
    return jsonify(rows)


# ═══════════════════════════════════════════════════════════════════════════════
# TONERS
# ═══════════════════════════════════════════════════════════════════════════════

@bp.route("/api/toners", methods=["GET"])
@login_required
def listar_toners() -> Response:
    """Lista toners cadastrados com busca opcional."""
    busca = request.args.get("q", "")
    query = "SELECT * FROM toners WHERE 1=1"
    params: list[Any] = []
    if busca:
        query += " AND (modelo_impressora ILIKE %s OR modelo_toner ILIKE %s OR cor ILIKE %s)"
        params += [f"%{busca}%"] * 3
    query += " ORDER BY modelo_impressora, cor"
    with get_db() as conn:
        with conn.cursor() as cur:
            rows = _fetch_all(cur, query, tuple(params))
    return jsonify(rows)


@bp.route("/api/toners", methods=["POST"])
@admin_required
def criar_toner() -> Response:
    """Cadastra um novo toner."""
    d = request.json
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO toners
                   (modelo_impressora,modelo_toner,cor,quantidade_estoque,
                    data_ultima_troca,quantidade_minima,observacoes,tipo_suprimento)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s)""",
                (
                    d["modelo_impressora"], d["modelo_toner"], d.get("cor", "Preto"),
                    d.get("quantidade_estoque", 0), d.get("data_ultima_troca"),
                    d.get("quantidade_minima", 1), d.get("observacoes"),
                    d.get("tipo_suprimento", "Toner"),
                ),
            )
    return jsonify({"ok": True, "msg": "Toner cadastrado!"})


@bp.route("/api/toners/<int:tid>", methods=["GET"])
@admin_required
def get_toner(tid: int) -> Response:
    """Retorna dados de um toner pelo ID."""
    with get_db() as conn:
        with conn.cursor() as cur:
            row = _fetch_one(cur, "SELECT * FROM toners WHERE id=%s", (tid,))
    return jsonify(row)


@bp.route("/api/toners/<int:tid>", methods=["PUT"])
@admin_required
def atualizar_toner(tid: int) -> Response:
    """Atualiza dados de um toner."""
    d = request.json
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """UPDATE toners SET
                   modelo_impressora=%s,modelo_toner=%s,cor=%s,quantidade_estoque=%s,
                   quantidade_minima=%s,observacoes=%s,tipo_suprimento=%s,updated_at=NOW() WHERE id=%s""",
                (
                    d.get("modelo_impressora"), d.get("modelo_toner"), d.get("cor"),
                    d.get("quantidade_estoque"), d.get("quantidade_minima"),
                    d.get("observacoes"), d.get("tipo_suprimento", "Toner"), tid,
                ),
            )
    return jsonify({"ok": True, "msg": "Toner atualizado!"})


@bp.route("/api/toners/<int:tid>/troca", methods=["POST"])
@admin_required
def registrar_troca_toner(tid: int) -> tuple[Response, int] | Response:
    """
    Registra uma troca de toner, debitando o estoque e atualizando data da última troca.

    Valida saldo disponível antes de registrar.
    """
    d = request.json
    with get_db() as conn:
        with conn.cursor() as cur:
            toner = _fetch_one(cur, "SELECT * FROM toners WHERE id=%s", (tid,))
            if not toner:
                return jsonify({"ok": False, "msg": "Toner não encontrado"}), 404

            qtd = int(d.get("quantidade", 1))
            nova_qtd = toner["quantidade_estoque"] - qtd
            if nova_qtd < 0:
                return jsonify({"ok": False, "msg": "Estoque insuficiente!"}), 400

            hoje = date.today().isoformat()
            cur.execute(
                "UPDATE toners SET quantidade_estoque=%s,data_ultima_troca=%s,updated_at=NOW() WHERE id=%s",
                (nova_qtd, hoje, tid),
            )
            cur.execute(
                """INSERT INTO toner_trocas
                   (toner_id,quantidade,responsavel,impressora_id_ativo,data_troca,observacoes,tipo_suprimento)
                   VALUES (%s,%s,%s,%s,%s,%s,%s)""",
                (tid, qtd, d.get("responsavel"), d.get("impressora_id_ativo"), hoje,
                 d.get("observacoes"), d.get("tipo_suprimento", "Toner")),
            )

    return jsonify({"ok": True, "msg": f"Troca registrada! Estoque restante: {nova_qtd}", "nova_quantidade": nova_qtd})


@bp.route("/api/toners/<int:tid>/trocas", methods=["GET"])
@login_required
def historico_trocas(tid: int) -> Response:
    """Retorna o histórico de trocas de um toner."""
    with get_db() as conn:
        with conn.cursor() as cur:
            rows = _fetch_all(
                cur,
                "SELECT * FROM toner_trocas WHERE toner_id=%s ORDER BY id DESC",
                (tid,),
            )
    return jsonify(rows)


# ═══════════════════════════════════════════════════════════════════════════════
