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
    """Registra uma nova ocorrência de manutenção e vincula peças."""
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
            
    tipo_manut = d.get("tipo_manutencao")
    orcamento = d.get("orcamento") if tipo_manut != "Manutenção Local" else None
    os_manutencao = d.get("os_manutencao") # if local, we generate later
    
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO manutencoes
                   (id_ativo,tipo_equipamento,modelo,local_atual,data_recebimento,
                    pessoa_recebimento,problema_relatado,data_manutencao,os_manutencao,
                    orcamento,status,data_envio,forma_envio,data_retorno,
                    solucao_aplicada,tecnico,observacoes,
                    tipo_manutencao,pecas_utilizadas,subtipo,localidade_id,chamado_id)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id""",
                (
                    d["id_ativo"], d["tipo_equipamento"], d.get("modelo"), d.get("local_atual"),
                    d.get("data_recebimento"), d.get("pessoa_recebimento"), d.get("problema_relatado"),
                    d.get("data_manutencao"), os_manutencao, orcamento,
                    d.get("status", "Aberta"), d.get("data_envio"), d.get("forma_envio"),
                    d.get("data_retorno"), d.get("solucao_aplicada"), d.get("tecnico"),
                    d.get("observacoes"), tipo_manut,
                    d.get("pecas_utilizadas"), d.get("subtipo"), localidade_id, d.get("chamado_id")
                ),
            )
            novo_id = cur.fetchone()["id"]
            
            if tipo_manut == "Manutenção Local":
                ano = date.today().year
                os_manutencao = f"OS-LOC-{ano}-{novo_id:04d}"
                cur.execute("UPDATE manutencoes SET os_manutencao=%s WHERE id=%s", (os_manutencao, novo_id))

            # Processar peças do estoque
            pecas = d.get("pecas_json", [])
            for p in pecas:
                qtd = int(p.get("quantidade", 1))
                if qtd <= 0: continue
                
                estoque_id = p.get("estoque_id")
                nome_peca = p.get("nome_peca")
                
                if estoque_id:
                    # Debitar do estoque
                    cur.execute("SELECT quantidade FROM estoque WHERE id=%s FOR UPDATE", (estoque_id,))
                    item_estoque = _fetch_one(cur, "SELECT quantidade FROM estoque WHERE id=%s", (estoque_id,))
                    if item_estoque:
                        nova_qtd = item_estoque["quantidade"] - qtd
                        if nova_qtd < 0:
                            raise Exception(f"Estoque insuficiente para o item ID {estoque_id}")
                        cur.execute("UPDATE estoque SET quantidade=%s, updated_at=NOW() WHERE id=%s", (nova_qtd, estoque_id))
                        cur.execute(
                            "INSERT INTO estoque_movimentacoes (estoque_id,tipo,quantidade,motivo,responsavel) VALUES (%s,'saida',%s,%s,%s)",
                            (estoque_id, qtd, f"Uso na Manutenção #{novo_id}", "Sistema")
                        )
                
                cur.execute(
                    "INSERT INTO manutencoes_pecas (manutencao_id, estoque_id, nome_peca, quantidade) VALUES (%s, %s, %s, %s)",
                    (novo_id, estoque_id, nome_peca, qtd)
                )

            log_historico(cur, d["id_ativo"], d["tipo_equipamento"], f"Manutenção Aberta (OS: {os_manutencao or 'S/N'})")
            
    return jsonify({"ok": True, "msg": "Manutenção registrada!", "id": novo_id})


@bp.route("/api/manutencoes/<int:mid>", methods=["GET"])
@admin_required
def get_manutencao(mid: int) -> Response:
    """Retorna dados de uma manutenção pelo ID, incluindo peças."""
    with get_db() as conn:
        with conn.cursor() as cur:
            row = _fetch_one(cur, "SELECT * FROM manutencoes WHERE id=%s", (mid,))
            if row:
                pecas = _fetch_all(cur, "SELECT mp.*, e.item as estoque_nome FROM manutencoes_pecas mp LEFT JOIN estoque e ON e.id = mp.estoque_id WHERE mp.manutencao_id=%s", (mid,))
                row["pecas_json"] = pecas
    return jsonify(row)


@bp.route("/api/manutencoes/<int:mid>", methods=["PUT"])
@admin_required
def atualizar_manutencao(mid: int) -> Response:
    """Atualiza dados de uma manutenção existente."""
    d = request.json
    tipo_manut = d.get("tipo_manutencao")
    orcamento = d.get("orcamento") if tipo_manut != "Manutenção Local" else None
    
    with get_db() as conn:
        with conn.cursor() as cur:
            # Mantemos o OS gerado caso seja local, senão usamos o que veio do form
            row = _fetch_one(cur, "SELECT os_manutencao FROM manutencoes WHERE id=%s", (mid,))
            os_manutencao = d.get("os_manutencao")
            if tipo_manut == "Manutenção Local":
                if row and row.get("os_manutencao") and row.get("os_manutencao").startswith("OS-LOC-"):
                    os_manutencao = row.get("os_manutencao")
                else:
                    ano = date.today().year
                    os_manutencao = f"OS-LOC-{ano}-{mid:04d}"

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
                    d.get("problema_relatado"), d.get("data_manutencao"), os_manutencao, orcamento,
                    d.get("status"), d.get("data_envio"), d.get("forma_envio"),
                    d.get("data_retorno"), d.get("solucao_aplicada"), d.get("tecnico"),
                    d.get("observacoes"), tipo_manut,
                    d.get("pecas_utilizadas"), d.get("subtipo"), mid,
                ),
            )
            
            if "pecas_json" in d:
                # 1. Devolver peças antigas ao estoque
                pecas_antigas = _fetch_all(cur, "SELECT * FROM manutencoes_pecas WHERE manutencao_id=%s", (mid,))
                for pa in pecas_antigas:
                    if pa["estoque_id"]:
                        cur.execute("SELECT quantidade FROM estoque WHERE id=%s FOR UPDATE", (pa["estoque_id"],))
                        cur.execute("UPDATE estoque SET quantidade=quantidade + %s WHERE id=%s", (pa["quantidade"], pa["estoque_id"]))
                        cur.execute(
                            "INSERT INTO estoque_movimentacoes (estoque_id,tipo,quantidade,motivo,responsavel) VALUES (%s,'entrada',%s,%s,%s)",
                            (pa["estoque_id"], pa["quantidade"], f"Restituição da Manutenção #{mid} (edição)", "Sistema")
                        )
                
                # 2. Deletar vínculos
                cur.execute("DELETE FROM manutencoes_pecas WHERE manutencao_id=%s", (mid,))
                
                # 3. Debitar novas peças
                for p in d["pecas_json"]:
                    qtd = int(p.get("quantidade", 1))
                    if qtd <= 0: continue
                    estoque_id = p.get("estoque_id")
                    nome_peca = p.get("nome_peca")
                    
                    if estoque_id:
                        cur.execute("SELECT quantidade FROM estoque WHERE id=%s FOR UPDATE", (estoque_id,))
                        item_estoque = _fetch_one(cur, "SELECT quantidade FROM estoque WHERE id=%s", (estoque_id,))
                        if item_estoque:
                            nova_qtd = item_estoque["quantidade"] - qtd
                            if nova_qtd < 0:
                                raise Exception(f"Estoque insuficiente para o item ID {estoque_id}")
                            cur.execute("UPDATE estoque SET quantidade=%s, updated_at=NOW() WHERE id=%s", (nova_qtd, estoque_id))
                            cur.execute(
                                "INSERT INTO estoque_movimentacoes (estoque_id,tipo,quantidade,motivo,responsavel) VALUES (%s,'saida',%s,%s,%s)",
                                (estoque_id, qtd, f"Uso na Manutenção #{mid} (edição)", "Sistema")
                            )
                    
                    cur.execute(
                        "INSERT INTO manutencoes_pecas (manutencao_id, estoque_id, nome_peca, quantidade) VALUES (%s, %s, %s, %s)",
                        (mid, estoque_id, nome_peca, qtd)
                    )

    return jsonify({"ok": True, "msg": "Manutenção atualizada!"})


# ═══════════════════════════════════════════════════════════════════════════════
