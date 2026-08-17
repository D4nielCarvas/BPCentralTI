from flask import Blueprint, jsonify, request, Response
from utils.auth_utils import login_required, admin_required
from utils.db_layer import acquire_conn, fetch_all
from utils.api_utils import log_historico

api_descartes_bp = Blueprint('api_descartes', __name__)

@api_descartes_bp.route("/api/descartes", methods=["GET"])
@login_required
def listar_descartes() -> Response:
    """Lista todos os descartes registrados."""
    with acquire_conn() as conn:
        with conn.cursor() as cur:
            rows = fetch_all(cur, "SELECT * FROM descartes ORDER BY id DESC")
    return jsonify(rows)

@api_descartes_bp.route("/api/descartes", methods=["POST"])
@admin_required
def criar_descarte() -> Response:
    """Registra o descarte de um ativo e atualiza seu status na tabela de origem."""
    d = request.json
    tabela_map = {
        "Celular":           "celulares",
        "Celular Ponto":     "celulares_ponto",
        "Celular Turma":     "celulares_turma",
        "Celular Inspeção":  "celulares_inspecao",  # [FIX-4] estava ausente — status nunca era atualizado para 'Descartado'
        "Computador":        "computadores",
        "Impressora":        "impressoras",
        "Estabilizador":     "estabilizadores",
        "Starlink":          "starlink",
    }
    with acquire_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO descartes
                   (id_ativo,tipo_equipamento,modelo,motivo,data_descarte,
                    responsavel_descarte,forma_descarte,destinatario,
                    documento_referencia,observacoes)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (
                    d["id_ativo"], d["tipo_equipamento"], d.get("modelo"), d.get("motivo"),
                    d.get("data_descarte"), d.get("responsavel_descarte"), d.get("forma_descarte"),
                    d.get("destinatario"), d.get("documento_referencia"), d.get("observacoes"),
                ),
            )
            tabela = tabela_map.get(d["tipo_equipamento"])
            if tabela:
                cur.execute(
                    f"UPDATE {tabela} SET status='Descartado' WHERE id_ativo=%s",
                    (d["id_ativo"],),
                )
                
            if d["tipo_equipamento"] in ("Celular", "Celular Ponto", "Celular Turma", "Celular Inspeção"):
                from blueprints.celulares import desvincular_linha_para_estoque
                desvincular_linha_para_estoque(cur, d["id_ativo"])
                
            log_historico(cur, d["id_ativo"], d["tipo_equipamento"], "Descarte")
    return jsonify({"ok": True, "msg": "Descarte registrado!"})
