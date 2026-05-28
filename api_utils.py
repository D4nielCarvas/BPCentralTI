from typing import Any
from flask import jsonify, request, Response
from db_layer import acquire_conn, fetch_all
from auth_utils import get_fazenda_nome_filter

def _list_table(tabela: str, colunas_busca: list[str]) -> Response:
    """
    Retorna registros de uma tabela com suporte a filtro de status e busca textual.
    Também implementa Paginação (limit, offset) e Isolamento de Tenant (fazenda_nome).
    """
    filtro = request.args.get("status", "")
    busca = request.args.get("q", "")
    
    # Paginação
    try:
        page = int(request.args.get("page", 1))
        if page < 1:
            page = 1
    except ValueError:
        page = 1

    try:
        limit = int(request.args.get("limit", 50))
        if limit < 1 or limit > 500:
            limit = 50
    except ValueError:
        limit = 50

    offset = (page - 1) * limit

    query = f"SELECT * FROM {tabela} WHERE 1=1"
    params: list[Any] = []

    fazenda_nome = get_fazenda_nome_filter()
    if fazenda_nome:
        query += " AND fazenda = %s"
        params.append(fazenda_nome)

    if filtro:
        query += " AND status=%s"
        params.append(filtro)
    if busca:
        cond = " OR ".join([f"{c} ILIKE %s" for c in colunas_busca])
        query += f" AND ({cond})"
        params += [f"%{busca}%"] * len(colunas_busca)

    query += " ORDER BY id DESC LIMIT %s OFFSET %s"
    params.extend([limit + 1, offset])  # Fetch limit + 1 to check if there are more

    with acquire_conn() as conn:
        with conn.cursor() as cur:
            rows = fetch_all(cur, query, tuple(params))

    has_more = len(rows) > limit
    if has_more:
        rows.pop()  # Remove the extra row fetched for checking 'has_more'

    return jsonify({"data": rows, "has_more": has_more, "page": page, "limit": limit})

def log_historico(
    cur,
    id_ativo: str,
    tipo: str,
    acao: str,
    campo: str = None,
    anterior: str = None,
    novo: str = None,
) -> None:
    """
    Registra uma ação no histórico de alterações.
    """
    cur.execute(
        """INSERT INTO historico 
           (id_ativo, tipo_equipamento, acao, campo_alterado, valor_anterior, valor_novo)
           VALUES (%s, %s, %s, %s, %s, %s)""",
        (id_ativo, tipo, acao, campo, anterior, novo),
    )
