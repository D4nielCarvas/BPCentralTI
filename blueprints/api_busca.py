from flask import Blueprint, jsonify, request, Response
from utils.auth_utils import login_required
from utils.db_layer import acquire_conn, fetch_all
from utils.id_generator import (
    SIGLAS_TIPO, SIGLAS_LOCAL, SIGLAS_SETOR,
    sugerir_id, sugerir_id_turma
)

api_busca_bp = Blueprint('api_busca', __name__)

@api_busca_bp.route("/api/busca")
@login_required
def busca_global() -> Response:
    """Busca global em todas as tabelas principais de equipamentos."""
    q = request.args.get("q", "").strip()
    if not q:
        return jsonify([])

    resultados = []
    
    tabelas_busca = [
        ("Celular",          "celulares",          ["id_ativo", "responsavel", "modelo", "fazenda", "numero", "setor", "cargo", "num_serie", "imei_1", "gmail"]),
        ("Celular Ponto",    "celulares_ponto",    ["id_ativo", "responsavel", "modelo", "fazenda", "num_turma", "funcao", "num_serie", "gmail_clockin"]),
        ("Celular Inspeção", "celulares_inspecao", ["id_ativo", "responsavel", "modelo", "fazenda", "id_sistema", "num_serie", "usuario_mip", "cargo", "setor"]),
        ("Celular Turma",    "celulares_turma",    ["id_ativo", "responsavel", "modelo", "fazenda", "num_turma", "num_serie", "imei_1", "setor"]),
        ("Computador",       "computadores",       ["id_ativo", "responsavel", "modelo", "fazenda", "marca", "numero_serie", "setor", "cargo", "processador", "memoria_ram", "armazenamento", "sistema_operacional", "usuario_windows"]),
        ("Impressora",       "impressoras",        ["id_ativo", "responsavel", "modelo", "fazenda", "marca", "ip_rede", "setor", "numero_serie", "patrimonio"]),
        ("Estabilizador",    "estabilizadores",    ["id_ativo", "modelo", "fazenda", "setor", "num_serie", "uso"]),
        ("Starlink",         "starlink",           ["id_ativo", "responsavel", "modelo", "fazenda", "setor", "num_serie", "ip_rede", "mac_address"]),
    ]

    with acquire_conn() as conn:
        with conn.cursor() as cur:
            for tipo_nome, tabela, colunas in tabelas_busca:
                condicoes = " OR ".join([f"{col}::text ILIKE %s" for col in colunas])
                sel_responsavel = "responsavel" if "responsavel" in colunas else "fazenda as responsavel"
                query = f"SELECT id_ativo, status, modelo, {sel_responsavel} FROM {tabela} WHERE {condicoes} ORDER BY id_ativo LIMIT 10"
                params = [f"%{q}%"] * len(colunas)
                
                rows = fetch_all(cur, query, tuple(params))
                for r in rows:
                    resultados.append({
                        "tipo": tipo_nome,
                        "id_ativo": r["id_ativo"],
                        "responsavel": r.get("responsavel", ""),
                        "modelo": r.get("modelo", ""),
                        "status": r.get("status", "")
                    })

    return jsonify(resultados[:30])

@api_busca_bp.route("/api/utils/siglas")
def get_siglas() -> Response:
    """Exporta as tabelas de siglas do id_generator para o frontend."""
    return jsonify({
        "tipo": SIGLAS_TIPO,
        "local": SIGLAS_LOCAL,
        "setor": SIGLAS_SETOR,
    })

@api_busca_bp.route("/api/utils/gerar-id")
def api_sugerir_id() -> Response:
    """Retorna uma sugestão de ID baseada em tipo, fazenda (local) e setor."""
    tipo = request.args.get("tipo")
    local = request.args.get("local")
    setor = request.args.get("setor")

    if not all([tipo, local, setor]):
        return jsonify({"ok": False, "msg": "Parâmetros 'tipo', 'local' e 'setor' são obrigatórios"}), 400

    try:
        with acquire_conn() as conn:
            with conn.cursor() as cur:
                novo_id = sugerir_id(cur, tipo, local, setor)
        return jsonify({"ok": True, "id_sugerido": novo_id})
    except Exception as e:
        return jsonify({"ok": False, "msg": f"Erro ao gerar ID: {str(e)}"}), 500

@api_busca_bp.route("/api/utils/gerar-id-turma")
def api_sugerir_id_turma() -> Response:
    """Retorna o próximo ID disponível para Celular Turma no formato CL-TRM-NN."""
    try:
        with acquire_conn() as conn:
            with conn.cursor() as cur:
                novo_id = sugerir_id_turma(cur)
        return jsonify({"ok": True, "id_sugerido": novo_id})
    except Exception as e:
        return jsonify({"ok": False, "msg": f"Erro ao gerar ID Turma: {str(e)}"}), 500
