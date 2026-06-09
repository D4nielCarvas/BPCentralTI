"""
blueprints/celulares.py — Blueprint para todas as rotas de celulares.

Cobre 4 entidades: celulares, celulares_ponto, celulares_inspecao, celulares_turma.
Mantém compatibilidade total com os endpoints existentes.

Patterns: Blueprint (Flask), Repository (acesso via db_layer).
Complexidade: O(n) listagem com paginação, O(1) CRUD por id_ativo.
"""

from __future__ import annotations

from typing import Any

import psycopg2
from flask import Blueprint, Response, jsonify, request, session

from utils.db_layer import acquire_conn, fetch_all, fetch_one

celulares_bp = Blueprint("celulares", __name__, url_prefix="/api")

# ── Helper: log de histórico (compartilhado via import do app) ────────────────
# Importado do app.py para evitar duplicação — será centralizado na Fase 6.
def _log(cur, id_ativo: str, tipo: str, acao: str) -> None:
    cur.execute(
        "INSERT INTO historico (id_ativo,tipo_equipamento,acao,campo_alterado,valor_anterior,valor_novo)"
        " VALUES (%s,%s,%s,NULL,NULL,NULL)",
        (id_ativo, tipo, acao),
    )

def _mask_telefones(rows: list[dict]) -> list[dict]:
    """Mascarar telefones caso o usuário não tenha a permissão 'ver_telefones'."""
    is_master = session.get("is_admin_master")
    pode_ver = session.get("permissoes", {}).get("ver_telefones")
    
    if is_master or pode_ver:
        return rows
        
    for r in rows:
        if "numero" in r and r["numero"]:
            num = str(r["numero"])
            if len(num) > 4:
                r["numero"] = "*" * (len(num) - 4) + num[-4:]
            else:
                r["numero"] = "***"
    return rows


def _list_paginado(tabela: str, colunas_busca: list[str]) -> Response:
    """
    Lista registros com suporte a filtro de status, busca textual e paginação.

    Query params:
        status: Filtro exato de status.
        q: Busca textual (ILIKE) nas colunas especificadas.
        page: Número da página (padrão=1).
        per_page: Itens por página (padrão=100, máx=500).

    Complexidade: O(n) onde n = registros retornados após filtros.
    Big-O espaço: O(k) onde k = per_page.
    """
    filtro = request.args.get("status", "")
    busca = request.args.get("q", "")
    page = max(1, int(request.args.get("page", 1)))
    per_page = min(500, max(1, int(request.args.get("per_page", 100))))
    offset = (page - 1) * per_page

    query = f"SELECT * FROM {tabela} WHERE 1=1"
    params: list[Any] = []

    if filtro:
        query += " AND status=%s"
        params.append(filtro)
    if busca:
        cond = " OR ".join([f"{c} ILIKE %s" for c in colunas_busca])
        query += f" AND ({cond})"
        params += [f"%{busca}%"] * len(colunas_busca)

    query += f" ORDER BY id DESC LIMIT %s OFFSET %s"
    params += [per_page, offset]

    with acquire_conn() as conn:
        with conn.cursor() as cur:
            rows = fetch_all(cur, query, tuple(params))

    return jsonify(_mask_telefones(rows))


# ═══════════════════════════════════════════════════════════════════════════════
# CELULARES
# ═══════════════════════════════════════════════════════════════════════════════

@celulares_bp.route("/celulares", methods=["GET"])
def listar_celulares() -> Response:
    """Lista celulares com suporte a filtro de status, busca e paginação."""
    return _list_paginado("celulares", ["id_ativo", "responsavel", "modelo", "numero"])


@celulares_bp.route("/celulares", methods=["POST"])
def criar_celular() -> tuple[Response, int] | Response:
    """
    Cadastra um novo celular.

    Body JSON obrigatório: id_ativo.
    Retorna 400 se id_ativo ausente ou já existente.
    """
    d = request.get_json(silent=True) or {}

    if not d.get("id_ativo"):
        return jsonify({"ok": False, "msg": "Campo 'id_ativo' é obrigatório"}), 400

    with acquire_conn() as conn:
        with conn.cursor() as cur:
            try:
                cur.execute(
                    """INSERT INTO celulares
                       (id_ativo,fazenda,setor,responsavel,tipo,modelo,numero,status,
                        uso_celular,carregador,termo_assinado,data_entrega,data_devolucao,
                        gmail,senha,usuario_anterior,imei_1,imei_2,num_serie,armazenamento,cargo)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                    (
                        d["id_ativo"], d.get("fazenda"), d.get("setor"), d.get("responsavel"),
                        d.get("tipo"), d.get("modelo"), d.get("numero"), d.get("status", "Ativo"),
                        d.get("uso_celular"), d.get("carregador"), d.get("termo_assinado"),
                        d.get("data_entrega"), d.get("data_devolucao"), d.get("gmail"),
                        d.get("senha"), d.get("usuario_anterior"), d.get("imei_1"),
                        d.get("imei_2"), d.get("num_serie"), d.get("armazenamento"), d.get("cargo"),
                    ),
                )
                _log(cur, d["id_ativo"], "Celular", "Cadastro")
            except psycopg2.IntegrityError:
                return jsonify({"ok": False, "msg": "ID de ativo já existe!"}), 400

    return jsonify({"ok": True, "msg": "Celular cadastrado!"})


@celulares_bp.route("/celulares/<id_ativo>", methods=["GET"])
def get_celular(id_ativo: str) -> tuple[Response, int] | Response:
    """Retorna os dados de um celular pelo ID do ativo."""
    with acquire_conn() as conn:
        with conn.cursor() as cur:
            from auth_utils import get_fazenda_nome_filter
            fazenda_nome = get_fazenda_nome_filter()
            if fazenda_nome:
                row = fetch_one(cur, "SELECT * FROM celulares WHERE id_ativo=%s AND fazenda=%s", (id_ativo, fazenda_nome))
            else:
                row = fetch_one(cur, "SELECT * FROM celulares WHERE id_ativo=%s", (id_ativo,))
    if row is None:
        return jsonify({"ok": False, "msg": "Celular não encontrado"}), 404
    return jsonify(_mask_telefones([row])[0])


@celulares_bp.route("/celulares/<id_ativo>", methods=["PUT"])
def atualizar_celular(id_ativo: str) -> tuple[Response, int] | Response:
    """Atualiza os dados de um celular existente."""
    d = request.get_json(silent=True) or {}
    with acquire_conn() as conn:
        with conn.cursor() as cur:
            existe = fetch_one(cur, "SELECT id_ativo, numero FROM celulares WHERE id_ativo=%s", (id_ativo,))
            if not existe:
                return jsonify({"ok": False, "msg": "Celular não encontrado"}), 404
                
            # Preserva o telefone original se o usuário não tiver permissão
            is_master = session.get("is_admin_master")
            pode_ver = session.get("permissoes", {}).get("ver_telefones")
            if not (is_master or pode_ver):
                d["numero"] = existe["numero"]
                
            cur.execute(
                """UPDATE celulares SET
                   fazenda=%s,setor=%s,responsavel=%s,tipo=%s,modelo=%s,numero=%s,status=%s,
                   uso_celular=%s,carregador=%s,termo_assinado=%s,data_entrega=%s,
                   data_devolucao=%s,gmail=%s,senha=%s,usuario_anterior=%s,imei_1=%s,
                   imei_2=%s,num_serie=%s,armazenamento=%s,cargo=%s,updated_at=NOW()
                   WHERE id_ativo=%s""",
                (
                    d.get("fazenda"), d.get("setor"), d.get("responsavel"), d.get("tipo"),
                    d.get("modelo"), d.get("numero"), d.get("status"), d.get("uso_celular"),
                    d.get("carregador"), d.get("termo_assinado"), d.get("data_entrega"),
                    d.get("data_devolucao"), d.get("gmail"), d.get("senha"),
                    d.get("usuario_anterior"), d.get("imei_1"), d.get("imei_2"),
                    d.get("num_serie"), d.get("armazenamento"), d.get("cargo"), id_ativo,
                ),
            )
            _log(cur, id_ativo, "Celular", "Edição")
    return jsonify({"ok": True, "msg": "Celular atualizado!"})


# ═══════════════════════════════════════════════════════════════════════════════
# CELULARES PONTO
# ═══════════════════════════════════════════════════════════════════════════════

@celulares_bp.route("/celulares_ponto", methods=["GET"])
def listar_celulares_ponto() -> Response:
    """Lista celulares de ponto com filtros e paginação."""
    return _list_paginado(
        "celulares_ponto",
        ["id_ativo", "responsavel", "modelo", "num_turma", "funcao"],
    )


@celulares_bp.route("/celulares_ponto", methods=["POST"])
def criar_celular_ponto() -> tuple[Response, int] | Response:
    """Cadastra um novo celular de ponto."""
    d = request.get_json(silent=True) or {}
    if not d.get("id_ativo"):
        return jsonify({"ok": False, "msg": "Campo 'id_ativo' é obrigatório"}), 400

    with acquire_conn() as conn:
        with conn.cursor() as cur:
            try:
                cur.execute(
                    """INSERT INTO celulares_ponto
                       (id_ativo,fazenda,funcao,responsavel,num_turma,tipo,modelo,status,
                        uso_celular,carregador,termo_assinado,data_entrega,data_devolucao,
                        gmail_clockin,senha,usuario_anterior,imei_1,imei_2,num_serie,armazenamento)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                    (
                        d["id_ativo"], d.get("fazenda"), d.get("funcao"), d.get("responsavel"),
                        d.get("num_turma"), d.get("tipo"), d.get("modelo"), d.get("status", "Ativo"),
                        d.get("uso_celular"), d.get("carregador"), d.get("termo_assinado"),
                        d.get("data_entrega"), d.get("data_devolucao"), d.get("gmail_clockin"),
                        d.get("senha"), d.get("usuario_anterior"), d.get("imei_1"),
                        d.get("imei_2"), d.get("num_serie"), d.get("armazenamento"),
                    ),
                )
                _log(cur, d["id_ativo"], "Celular Ponto", "Cadastro")
            except psycopg2.IntegrityError:
                return jsonify({"ok": False, "msg": "ID de ativo já existe!"}), 400
    return jsonify({"ok": True, "msg": "Celular de ponto cadastrado!"})


@celulares_bp.route("/celulares_ponto/<id_ativo>", methods=["GET"])
def get_celular_ponto(id_ativo: str) -> tuple[Response, int] | Response:
    """Retorna dados de um celular de ponto."""
    with acquire_conn() as conn:
        with conn.cursor() as cur:
            from auth_utils import get_fazenda_nome_filter
            fazenda_nome = get_fazenda_nome_filter()
            if fazenda_nome:
                row = fetch_one(cur, "SELECT * FROM celulares_ponto WHERE id_ativo=%s AND fazenda=%s", (id_ativo, fazenda_nome))
            else:
                row = fetch_one(cur, "SELECT * FROM celulares_ponto WHERE id_ativo=%s", (id_ativo,))
    if row is None:
        return jsonify({"ok": False, "msg": "Celular Ponto não encontrado"}), 404
    return jsonify(row)


@celulares_bp.route("/celulares_ponto/<id_ativo>", methods=["PUT"])
def atualizar_celular_ponto(id_ativo: str) -> tuple[Response, int] | Response:
    """Atualiza dados de um celular de ponto."""
    d = request.get_json(silent=True) or {}
    with acquire_conn() as conn:
        with conn.cursor() as cur:
            existe = fetch_one(cur, "SELECT id_ativo FROM celulares_ponto WHERE id_ativo=%s", (id_ativo,))
            if not existe:
                return jsonify({"ok": False, "msg": "Celular Ponto não encontrado"}), 404
            cur.execute(
                """UPDATE celulares_ponto SET
                   fazenda=%s,funcao=%s,responsavel=%s,num_turma=%s,tipo=%s,modelo=%s,status=%s,
                   uso_celular=%s,carregador=%s,termo_assinado=%s,data_entrega=%s,
                   data_devolucao=%s,gmail_clockin=%s,senha=%s,usuario_anterior=%s,
                   imei_1=%s,imei_2=%s,num_serie=%s,armazenamento=%s,updated_at=NOW()
                   WHERE id_ativo=%s""",
                (
                    d.get("fazenda"), d.get("funcao"), d.get("responsavel"), d.get("num_turma"),
                    d.get("tipo"), d.get("modelo"), d.get("status"), d.get("uso_celular"),
                    d.get("carregador"), d.get("termo_assinado"), d.get("data_entrega"),
                    d.get("data_devolucao"), d.get("gmail_clockin"), d.get("senha"),
                    d.get("usuario_anterior"), d.get("imei_1"), d.get("imei_2"),
                    d.get("num_serie"), d.get("armazenamento"), id_ativo,
                ),
            )
            _log(cur, id_ativo, "Celular Ponto", "Edição")
    return jsonify({"ok": True, "msg": "Celular de ponto atualizado!"})


# ═══════════════════════════════════════════════════════════════════════════════
# CELULARES INSPEÇÃO
# ═══════════════════════════════════════════════════════════════════════════════

@celulares_bp.route("/celulares_inspecao", methods=["GET"])
def listar_celulares_inspecao() -> Response:
    """Lista celulares de inspeção com filtros e paginação."""
    return _list_paginado(
        "celulares_inspecao",
        ["id_ativo", "responsavel", "modelo", "usuario_mip", "id_sistema"],
    )


@celulares_bp.route("/celulares_inspecao", methods=["POST"])
def criar_celular_inspecao() -> tuple[Response, int] | Response:
    """Cadastra um novo celular de inspeção."""
    d = request.get_json(silent=True) or {}
    if not d.get("id_ativo"):
        return jsonify({"ok": False, "msg": "Campo 'id_ativo' é obrigatório"}), 400

    with acquire_conn() as conn:
        with conn.cursor() as cur:
            try:
                cur.execute(
                    """INSERT INTO celulares_inspecao
                       (id_ativo,id_sistema,fazenda,setor,responsavel,cargo,tipo,modelo,
                        status,uso_celular,carregador,termo_assinado,data_entrega,data_devolucao,
                        gmail,senha,usuario_anterior,imei_1,imei_2,num_serie,armazenamento,observacoes,
                        usuario_mip,senha_mip)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                    (
                        d["id_ativo"], d.get("id_sistema"), d.get("fazenda"), d.get("setor"),
                        d.get("responsavel"), d.get("cargo"), d.get("tipo"), d.get("modelo"),
                        d.get("status", "Ativo"), d.get("uso_celular"), d.get("carregador"),
                        d.get("termo_assinado"), d.get("data_entrega"), d.get("data_devolucao"),
                        d.get("gmail"), d.get("senha"), d.get("usuario_anterior"),
                        d.get("imei_1"), d.get("imei_2"), d.get("num_serie"),
                        d.get("armazenamento"), d.get("observacoes"),
                        d.get("usuario_mip"), d.get("senha_mip"),
                    ),
                )
                _log(cur, d["id_ativo"], "Celular Inspeção", "Cadastro")
            except psycopg2.IntegrityError:
                return jsonify({"ok": False, "msg": "ID de ativo já existe!"}), 400
    return jsonify({"ok": True, "msg": "Celular de inspeção cadastrado!"})


@celulares_bp.route("/celulares_inspecao/<id_ativo>", methods=["GET"])
def get_celular_inspecao(id_ativo: str) -> tuple[Response, int] | Response:
    """Retorna dados de um celular de inspeção."""
    with acquire_conn() as conn:
        with conn.cursor() as cur:
            from auth_utils import get_fazenda_nome_filter
            fazenda_nome = get_fazenda_nome_filter()
            if fazenda_nome:
                row = fetch_one(cur, "SELECT * FROM celulares_inspecao WHERE id_ativo=%s AND fazenda=%s", (id_ativo, fazenda_nome))
            else:
                row = fetch_one(cur, "SELECT * FROM celulares_inspecao WHERE id_ativo=%s", (id_ativo,))
    if row is None:
        return jsonify({"ok": False, "msg": "Celular Inspeção não encontrado"}), 404
    return jsonify(row)


@celulares_bp.route("/celulares_inspecao/<id_ativo>", methods=["PUT"])
def atualizar_celular_inspecao(id_ativo: str) -> tuple[Response, int] | Response:
    """Atualiza dados de um celular de inspeção."""
    d = request.get_json(silent=True) or {}
    with acquire_conn() as conn:
        with conn.cursor() as cur:
            existe = fetch_one(cur, "SELECT id_ativo FROM celulares_inspecao WHERE id_ativo=%s", (id_ativo,))
            if not existe:
                return jsonify({"ok": False, "msg": "Celular Inspeção não encontrado"}), 404
            cur.execute(
                """UPDATE celulares_inspecao SET
                   id_sistema=%s,fazenda=%s,setor=%s,responsavel=%s,cargo=%s,tipo=%s,modelo=%s,
                   status=%s,uso_celular=%s,carregador=%s,termo_assinado=%s,
                   data_entrega=%s,data_devolucao=%s,gmail=%s,senha=%s,usuario_anterior=%s,
                   imei_1=%s,imei_2=%s,num_serie=%s,armazenamento=%s,observacoes=%s,
                   usuario_mip=%s,senha_mip=%s,updated_at=NOW()
                   WHERE id_ativo=%s""",
                (
                    d.get("id_sistema"), d.get("fazenda"), d.get("setor"), d.get("responsavel"),
                    d.get("cargo"), d.get("tipo"), d.get("modelo"),
                    d.get("status"), d.get("uso_celular"), d.get("carregador"),
                    d.get("termo_assinado"), d.get("data_entrega"), d.get("data_devolucao"),
                    d.get("gmail"), d.get("senha"), d.get("usuario_anterior"),
                    d.get("imei_1"), d.get("imei_2"), d.get("num_serie"),
                    d.get("armazenamento"), d.get("observacoes"),
                    d.get("usuario_mip"), d.get("senha_mip"), id_ativo,
                ),
            )
            _log(cur, id_ativo, "Celular Inspeção", "Edição")
    return jsonify({"ok": True, "msg": "Celular de inspeção atualizado!"})


# ═══════════════════════════════════════════════════════════════════════════════
# CELULARES TURMA
# ═══════════════════════════════════════════════════════════════════════════════

@celulares_bp.route("/celulares_turma", methods=["GET"])
def listar_celulares_turma() -> Response:
    """Lista celulares de turma com filtros e paginação."""
    return _list_paginado(
        "celulares_turma",
        ["id_ativo", "responsavel", "modelo", "num_turma", "fazenda", "num_serie"],
    )


@celulares_bp.route("/celulares_turma", methods=["POST"])
def criar_celular_turma() -> tuple[Response, int] | Response:
    """Cadastra um novo celular de turma (ID no formato CL-TRM-NN)."""
    d = request.get_json(silent=True) or {}
    if not d.get("id_ativo"):
        return jsonify({"ok": False, "msg": "Campo 'id_ativo' é obrigatório"}), 400

    with acquire_conn() as conn:
        with conn.cursor() as cur:
            try:
                cur.execute(
                    """INSERT INTO celulares_turma
                       (id_ativo,num_turma,responsavel,fazenda,setor,modelo,tipo,status,
                        uso_celular,carregador,termo_assinado,data_entrega,data_devolucao,
                        gmail_clockin,senha,usuario_anterior,imei_1,imei_2,num_serie,
                        armazenamento,observacoes)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                    (
                        d["id_ativo"], d.get("num_turma"), d.get("responsavel"),
                        d.get("fazenda"), d.get("setor"), d.get("modelo"), d.get("tipo"),
                        d.get("status", "Ativo"), d.get("uso_celular"), d.get("carregador"),
                        d.get("termo_assinado"), d.get("data_entrega"), d.get("data_devolucao"),
                        d.get("gmail_clockin"), d.get("senha"), d.get("usuario_anterior"),
                        d.get("imei_1"), d.get("imei_2"), d.get("num_serie"),
                        d.get("armazenamento"), d.get("observacoes"),
                    ),
                )
                _log(cur, d["id_ativo"], "Celular Turma", "Cadastro")
            except psycopg2.IntegrityError:
                return jsonify({"ok": False, "msg": "ID de ativo já existe!"}), 400
    return jsonify({"ok": True, "msg": "Celular de turma cadastrado!"})


@celulares_bp.route("/celulares_turma/<id_ativo>", methods=["GET"])
def get_celular_turma(id_ativo: str) -> tuple[Response, int] | Response:
    """Retorna dados de um celular de turma."""
    with acquire_conn() as conn:
        with conn.cursor() as cur:
            from auth_utils import get_fazenda_nome_filter
            fazenda_nome = get_fazenda_nome_filter()
            if fazenda_nome:
                row = fetch_one(cur, "SELECT * FROM celulares_turma WHERE id_ativo=%s AND fazenda=%s", (id_ativo, fazenda_nome))
            else:
                row = fetch_one(cur, "SELECT * FROM celulares_turma WHERE id_ativo=%s", (id_ativo,))
    if row is None:
        return jsonify({"ok": False, "msg": "Celular Turma não encontrado"}), 404
    return jsonify(row)


@celulares_bp.route("/celulares_turma/<id_ativo>", methods=["PUT"])
def atualizar_celular_turma(id_ativo: str) -> tuple[Response, int] | Response:
    """Atualiza dados de um celular de turma."""
    d = request.get_json(silent=True) or {}
    with acquire_conn() as conn:
        with conn.cursor() as cur:
            existe = fetch_one(cur, "SELECT id_ativo FROM celulares_turma WHERE id_ativo=%s", (id_ativo,))
            if not existe:
                return jsonify({"ok": False, "msg": "Celular Turma não encontrado"}), 404
            cur.execute(
                """UPDATE celulares_turma SET
                   num_turma=%s,responsavel=%s,fazenda=%s,setor=%s,modelo=%s,tipo=%s,
                   status=%s,uso_celular=%s,carregador=%s,termo_assinado=%s,data_entrega=%s,
                   data_devolucao=%s,gmail_clockin=%s,senha=%s,usuario_anterior=%s,
                   imei_1=%s,imei_2=%s,num_serie=%s,armazenamento=%s,observacoes=%s,
                   updated_at=NOW() WHERE id_ativo=%s""",
                (
                    d.get("num_turma"), d.get("responsavel"), d.get("fazenda"), d.get("setor"),
                    d.get("modelo"), d.get("tipo"), d.get("status"), d.get("uso_celular"),
                    d.get("carregador"), d.get("termo_assinado"), d.get("data_entrega"),
                    d.get("data_devolucao"), d.get("gmail_clockin"), d.get("senha"),
                    d.get("usuario_anterior"), d.get("imei_1"), d.get("imei_2"),
                    d.get("num_serie"), d.get("armazenamento"), d.get("observacoes"),
                    id_ativo,
                ),
            )
            _log(cur, id_ativo, "Celular Turma", "Edição")
    return jsonify({"ok": True, "msg": "Celular de turma atualizado!"})
