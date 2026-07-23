"""
blueprints/api_transferencias.py — Thin Controller HTTP para transferências.

Responsabilidade única: receber requests HTTP, delegar ao TransferenciaService
e serializar a resposta. Zero lógica de negócio aqui.

Rotas:
    POST  /api/transferencias                       → criar_transferencia
    GET   /api/transferencias                       → listar_transferencias
    GET   /api/transferencias/<id_ativo>/historico  → historico_transferencias
    GET   /api/transferencias/estoque               → ativos_em_estoque
"""

from flask import Blueprint, Response, jsonify, request, session

from services.transferencia_service import (
    AtivoNaoEncontradoError,
    StatusBloqueadoError,
    TransferenciaError,
    TransferenciaService,
)
from utils.auth_utils import admin_required, login_required
from utils.db_layer import acquire_conn, fetch_all

api_transferencias_bp = Blueprint("api_transferencias", __name__)

_service = TransferenciaService()

# ── UNION ALL estático para ativos em estoque (Sprint 2.2) ────────────────────
# Substitui 8 queries separadas por 1 round-trip — O(k) onde k = ativos em estoque.
_UNION_ESTOQUE_SQL = """
    SELECT id_ativo, modelo, fazenda, setor,   updated_at, 'Celular'          AS tipo_equipamento FROM celulares         WHERE status='Estoque'
    UNION ALL
    SELECT id_ativo, modelo, fazenda, NULL,    updated_at, 'Celular Ponto'    AS tipo_equipamento FROM celulares_ponto    WHERE status='Estoque'
    UNION ALL
    SELECT id_ativo, modelo, fazenda, setor,   updated_at, 'Celular Inspeção' AS tipo_equipamento FROM celulares_inspecao WHERE status='Estoque'
    UNION ALL
    SELECT id_ativo, modelo, fazenda, setor,   updated_at, 'Celular Turma'    AS tipo_equipamento FROM celulares_turma    WHERE status='Estoque'
    UNION ALL
    SELECT id_ativo, modelo, fazenda, setor,   updated_at, 'Computador'       AS tipo_equipamento FROM computadores       WHERE status='Estoque'
    UNION ALL
    SELECT id_ativo, modelo, fazenda, setor,   updated_at, 'Impressora'       AS tipo_equipamento FROM impressoras        WHERE status='Estoque'
    UNION ALL
    SELECT id_ativo, modelo, fazenda, setor,   updated_at, 'Estabilizador'    AS tipo_equipamento FROM estabilizadores    WHERE status='Estoque'
    UNION ALL
    SELECT id_ativo, modelo, fazenda, setor,   updated_at, 'Starlink'         AS tipo_equipamento FROM starlink           WHERE status='Estoque'
    ORDER BY updated_at DESC
"""


# ── Rotas ──────────────────────────────────────────────────────────────────────

@api_transferencias_bp.route("/api/transferencias", methods=["POST"])
@admin_required
def criar_transferencia() -> Response:
    """Registra uma transferência de ativo entre responsáveis/fazendas/setores."""
    registrado_por = (
        session.get("usuario")
        or session.get("email")
        or "Sistema"
    )
    try:
        resultado = _service.criar(
            payload=request.json or {},
            registrado_por=registrado_por,
        )
        return jsonify(resultado)

    except TransferenciaError as exc:
        return jsonify({"ok": False, "msg": str(exc)}), 400

    except AtivoNaoEncontradoError as exc:
        return jsonify({"ok": False, "msg": str(exc)}), 404

    except StatusBloqueadoError as exc:
        return jsonify({"ok": False, "msg": str(exc)}), 409


@api_transferencias_bp.route("/api/transferencias", methods=["GET"])
@login_required
def listar_transferencias() -> Response:
    """Lista transferências com filtros opcionais e paginação.

    Query params:
        id_ativo, tipo_equipamento, data_inicio, data_fim (filtros)
        page (int, default=1), per_page (int, default=50, max=200)
    """
    id_ativo = request.args.get("id_ativo", "")
    tipo_eq  = request.args.get("tipo_equipamento", "")
    data_ini = request.args.get("data_inicio", "")
    data_fim = request.args.get("data_fim", "")

    page     = max(1, int(request.args.get("page", 1)))
    per_page = min(200, max(1, int(request.args.get("per_page", 50))))
    offset   = (page - 1) * per_page

    query  = "SELECT * FROM transferencias WHERE 1=1"
    params: list = []

    if id_ativo:
        query += " AND id_ativo=%s"
        params.append(id_ativo)
    if tipo_eq:
        query += " AND tipo_equipamento=%s"
        params.append(tipo_eq)
    if data_ini:
        query += " AND data_transferencia >= %s"
        params.append(data_ini)
    if data_fim:
        query += " AND data_transferencia <= %s"
        params.append(data_fim)

    query += " ORDER BY id DESC LIMIT %s OFFSET %s"
    params.extend([per_page, offset])

    with acquire_conn() as conn:
        with conn.cursor() as cur:
            rows = fetch_all(cur, query, tuple(params))

    return jsonify(rows)


@api_transferencias_bp.route("/api/transferencias/<id_ativo>/historico")
@login_required
def historico_transferencias(id_ativo: str) -> Response:
    """Retorna o histórico paginado de transferências de um ativo."""
    page     = max(1, int(request.args.get("page", 1)))
    per_page = min(100, max(1, int(request.args.get("per_page", 20))))
    offset   = (page - 1) * per_page

    with acquire_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) AS total FROM transferencias WHERE id_ativo=%s",
                (id_ativo,),
            )
            total = cur.fetchone()["total"]
            rows  = fetch_all(
                cur,
                "SELECT * FROM transferencias WHERE id_ativo=%s ORDER BY id DESC LIMIT %s OFFSET %s",
                (id_ativo, per_page, offset),
            )

    return jsonify({
        "total":    total,
        "page":     page,
        "per_page": per_page,
        "pages":    (total + per_page - 1) // per_page,
        "items":    rows,
    })


@api_transferencias_bp.route("/api/transferencias/estoque")
@login_required
def ativos_em_estoque() -> Response:
    """Lista todos os ativos com status 'Estoque' em uma única query UNION ALL.

    Sprint 2.2 — substitui loop de N queries por 1 UNION ALL,
    reduzindo de 8 round-trips para 1.
    FIX: corrige typo 'Celular Inspecão' → 'Celular Inspeção'.
    """
    with acquire_conn() as conn:
        with conn.cursor() as cur:
            resultado = fetch_all(cur, _UNION_ESTOQUE_SQL)
    return jsonify(resultado)
