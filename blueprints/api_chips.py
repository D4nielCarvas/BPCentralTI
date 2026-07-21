from __future__ import annotations
from flask import Blueprint, Response, jsonify, request
from utils.db_layer import acquire_conn, fetch_all, fetch_one

api_chips_bp = Blueprint("api_chips", __name__, url_prefix="/api/chips")

@api_chips_bp.route("", methods=["GET"])
def listar_chips() -> Response:
    """Lista todas as linhas (chips) e sua alocação atual."""
    # Similar ao _list_paginado, vamos permitir busca textual e paginação
    busca = request.args.get("q", "")
    
    query = """
        SELECT 
            l.id, l.numero, l.status,
            a.id_ativo, f.nome as responsavel,
            a.data_inicio
        FROM linhas_celular l
        LEFT JOIN atribuicoes_linha a ON l.id = a.linha_id AND a.data_devolucao IS NULL
        LEFT JOIN funcionarios f ON a.funcionario_id = f.id
        WHERE 1=1
    """
    params = []
    
    if busca:
        query += " AND (l.numero ILIKE %s OR f.nome ILIKE %s OR a.id_ativo ILIKE %s)"
        params.extend([f"%{busca}%", f"%{busca}%", f"%{busca}%"])
        
    query += " ORDER BY l.numero ASC"
    
    with acquire_conn() as conn:
        with conn.cursor() as cur:
            rows = fetch_all(cur, query, tuple(params))
            
    return jsonify(rows)

@api_chips_bp.route("/<linha_id>/historico", methods=["GET"])
def historico_chip(linha_id: str) -> Response:
    """Retorna a timeline de um chip específico."""
    query = """
        SELECT 
            a.id_ativo, f.nome as responsavel,
            a.data_inicio, a.data_devolucao
        FROM atribuicoes_linha a
        JOIN funcionarios f ON a.funcionario_id = f.id
        WHERE a.linha_id = %s
        ORDER BY a.data_inicio DESC
    """
    with acquire_conn() as conn:
        with conn.cursor() as cur:
            rows = fetch_all(cur, query, (linha_id,))
            
    return jsonify(rows)
