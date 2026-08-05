from flask import Blueprint, request, jsonify, Response
from typing import Any
from datetime import date
import psycopg2

from utils.db_layer import acquire_conn as get_db, fetch_all as _fetch_all, fetch_one as _fetch_one, row_to_dict
from utils.auth_utils import login_required, admin_required, get_fazenda_nome_filter
from utils.crypto_utils import encrypt_field, decrypt_field
from utils.api_utils import _list_table, log_historico

bp = Blueprint('api_manutencoes', __name__, url_prefix='')

# MANUTENÇÕES
# ═══════════════════════════════════════════════════════════════════════════════

@bp.route("/api/manutencoes", methods=["GET"])
@login_required
def listar_manutencoes() -> Response:
    """Lista manutenções com filtros de status, tipo e busca textual."""
    filtro = request.args.get("status", "")
    tipo = request.args.get("tipo", "")
    busca = request.args.get("q", "")
    query = "SELECT * FROM manutencoes WHERE 1=1"
    params: list[Any] = []

    if filtro:
        query += " AND status=%s"
        params.append(filtro)
    if tipo:
        query += " AND tipo_equipamento=%s"
        params.append(tipo)
    if busca:
        query += " AND (id_ativo ILIKE %s OR modelo ILIKE %s OR problema_relatado ILIKE %s)"
        params += [f"%{busca}%"] * 3

    query += " ORDER BY id DESC"

    with get_db() as conn:
        with conn.cursor() as cur:
            rows = _fetch_all(cur, query, tuple(params))
    return jsonify(rows)


@bp.route("/api/manutencoes", methods=["POST"])
@admin_required
def criar_manutencao() -> Response:
    """Registra uma nova ocorrência de manutenção."""
    d = request.json
    
    localidade_id = None
    tabela_equipamento = {
        "Celular": "celulares",
        "Celular Ponto": "celulares_ponto",
        "Celular Inspeção": "celulares_inspecao",
        "Celular Turma": "celulares_turma",
        "Computador": "computadores",
        "Impressora": "impressoras",
        "Estabilizador": "estabilizadores",
        "Starlink": "starlink"
    }.get(d.get("tipo_equipamento"))

    if tabela_equipamento and d.get("id_ativo"):
        try:
            with get_db() as conn:
                with conn.cursor() as cur:
                    row = _fetch_one(cur, f"SELECT localidade_id FROM {tabela_equipamento} WHERE id_ativo=%s", (d["id_ativo"],))
                    if row:
                        localidade_id = row.get("localidade_id")
        except Exception:
            pass
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO manutencoes
                   (id_ativo,tipo_equipamento,modelo,local_atual,data_recebimento,
                    pessoa_recebimento,problema_relatado,data_manutencao,os_manutencao,
                    orcamento,status,data_envio,forma_envio,data_retorno,
                    solucao_aplicada,tecnico,observacoes,
                    tipo_manutencao,pecas_utilizadas,subtipo,localidade_id)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (
                    d["id_ativo"], d["tipo_equipamento"], d.get("modelo"), d.get("local_atual"),
                    d.get("data_recebimento"), d.get("pessoa_recebimento"), d.get("problema_relatado"),
                    d.get("data_manutencao"), d.get("os_manutencao"), d.get("orcamento"),
                    d.get("status", "Aberta"), d.get("data_envio"), d.get("forma_envio"),
                    d.get("data_retorno"), d.get("solucao_aplicada"), d.get("tecnico"),
                    d.get("observacoes"), d.get("tipo_manutencao"),
                    d.get("pecas_utilizadas"), d.get("subtipo"), localidade_id,
                ),
            )
            log_historico(cur, d["id_ativo"], d["tipo_equipamento"], "Manutenção Aberta")
    return jsonify({"ok": True, "msg": "Manutenção registrada!"})


@bp.route("/api/manutencoes/<int:mid>", methods=["GET"])
@admin_required
def get_manutencao(mid: int) -> Response:
    """Retorna dados de uma manutenção pelo ID."""
    with get_db() as conn:
        with conn.cursor() as cur:
            row = _fetch_one(cur, "SELECT * FROM manutencoes WHERE id=%s", (mid,))
    return jsonify(row)


@bp.route("/api/manutencoes/<int:mid>", methods=["PUT"])
@admin_required
def atualizar_manutencao(mid: int) -> Response:
    """Atualiza dados de uma manutenção existente."""
    d = request.json
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """UPDATE manutencoes SET
                   local_atual=%s,data_recebimento=%s,pessoa_recebimento=%s,
                   problema_relatado=%s,data_manutencao=%s,os_manutencao=%s,orcamento=%s,
                   status=%s,data_envio=%s,forma_envio=%s,data_retorno=%s,
                   solucao_aplicada=%s,tecnico=%s,observacoes=%s,
                   tipo_manutencao=%s,pecas_utilizadas=%s,subtipo=%s,updated_at=NOW()
                   WHERE id=%s""",
                (
                    d.get("local_atual"), d.get("data_recebimento"), d.get("pessoa_recebimento"),
                    d.get("problema_relatado"), d.get("data_manutencao"), d.get("os_manutencao"),
                    d.get("orcamento"), d.get("status"), d.get("data_envio"), d.get("forma_envio"),
                    d.get("data_retorno"), d.get("solucao_aplicada"), d.get("tecnico"),
                    d.get("observacoes"), d.get("tipo_manutencao"),
                    d.get("pecas_utilizadas"), d.get("subtipo"), mid,
                ),
            )
    return jsonify({"ok": True, "msg": "Manutenção atualizada!"})


# ═══════════════════════════════════════════════════════════════════════════════
