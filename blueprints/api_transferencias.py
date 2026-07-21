from flask import Blueprint, jsonify, request, Response, session, current_app
from datetime import date
from utils.auth_utils import login_required, admin_required
from utils.db_layer import acquire_conn, fetch_all, fetch_one
from utils.api_utils import log_historico
from utils.id_generator import (
    proximo_sequencial, gerar_id_ativo, sugerir_id_turma,
    SIGLAS_TIPO, SIGLAS_LOCAL, SIGLAS_SETOR
)
# Sprint 4.1 — fonte única de verdade para mapeamentos de tipo
from utils.equipment_types import TABELA_POR_TIPO as _TABELA_POR_TIPO

FAZENDA_PARA_SIGLA: dict[str, str] = {v: k for k, v in SIGLAS_LOCAL.items()}
SETOR_PARA_SIGLA: dict[str, str]   = {v: k for k, v in SIGLAS_SETOR.items()}

api_transferencias_bp = Blueprint('api_transferencias', __name__)

# Mapeamento tipo_equipamento → sigla para id_generator
_SIGLA_TIPO_MAP: dict[str, str] = {
    "Celular":          "CL",
    "Celular Ponto":    "CL",
    "Celular Inspeção": "CL",
    "Celular Turma":    "CL",  # Não remapeado — usa CL-TRM-NN
    "Impressora":       "IMP",
    "Estabilizador":    "EST",
    "Starlink":         "STL",
}

_STATUS_BLOQUEADOS = {"Manutenção", "Descartado"}

@api_transferencias_bp.route("/api/transferencias", methods=["POST"])
@admin_required
def criar_transferencia() -> Response:
    """Registra uma transferência de ativo entre responsáveis/fazendas/setores."""
    d = request.json
    tipo_eq = d.get("tipo_equipamento", "")
    tabela = _TABELA_POR_TIPO.get(tipo_eq)

    if not tabela:
        return jsonify({"ok": False, "msg": f"Tipo de equipamento inválido: {tipo_eq}"}), 400

    id_ativo = d.get("id_ativo", "")
    tipo_transf = d.get("tipo_transferencia", "")
    data_transf = d.get("data_transferencia") or date.today().isoformat()

    try:
        if date.fromisoformat(data_transf) > date.today():
            return jsonify({"ok": False, "msg": "Data de transferência não pode ser futura"}), 400
    except ValueError:
        return jsonify({"ok": False, "msg": "Data de transferência inválida"}), 400

    if tipo_transf == "Estoque para Usuario" and not d.get("responsavel_destino"):
        return jsonify({"ok": False, "msg": "responsavel_destino é obrigatório para 'Estoque para Usuario'"}), 400
    if tipo_transf == "Usuario para Estoque" and not d.get("data_devolucao"):
        return jsonify({"ok": False, "msg": "data_devolucao é obrigatório para 'Usuario para Estoque'"}), 400
    if tipo_transf == "Usuario para Usuario" and not d.get("responsavel_destino"):
        return jsonify({"ok": False, "msg": "responsavel_destino é obrigatório para transferência entre usuários"}), 400
    if tipo_transf == "Usuario para Turma":
        if not d.get("turma_destino"):
            return jsonify({"ok": False, "msg": "A turma destino é obrigatória para este tipo de transferência"}), 400
        # Mapeia a turma para o responsável destino para fins de log na tabela transferencias
        d["responsavel_destino"] = d.get("turma_destino")

    hoje = date.today().isoformat()

    with acquire_conn() as conn:
        with conn.cursor() as cur:
            ativo = fetch_one(
                cur, f"SELECT id_ativo,status,responsavel FROM {tabela} WHERE id_ativo=%s", (id_ativo,)
            )
            if not ativo:
                return jsonify({"ok": False, "msg": f"Ativo '{id_ativo}' não encontrado em {tipo_eq}"}), 404

            if ativo["status"] in _STATUS_BLOQUEADOS:
                return jsonify({
                    "ok": False,
                    "msg": f"Ativo com status '{ativo['status']}' não pode ser transferido",
                }), 409

            # Sprint 1.1 — registrado_por sempre vem da sessão, nunca do body da request
            _registrado_por = (
                session.get("usuario")
                or session.get("email")
                or "Sistema"
            )

            # Sprint 1.3 — RETURNING id captura o PK para ancorar UPDATEs posteriores
            cur.execute(
                """INSERT INTO transferencias
                   (id_ativo,tipo_equipamento,responsavel_origem,fazenda_origem,setor_origem,
                    responsavel_destino,fazenda_destino,setor_destino,tipo_transferencia,
                    motivo,data_transferencia,registrado_por,observacoes,termo_pdf)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                   RETURNING id""",
                (
                    id_ativo, tipo_eq,
                    d.get("responsavel_origem"), d.get("fazenda_origem"), d.get("setor_origem"),
                    d.get("responsavel_destino"), d.get("fazenda_destino"), d.get("setor_destino"),
                    tipo_transf, d.get("motivo"), data_transf,
                    _registrado_por, d.get("observacoes"), d.get("termo_pdf"),
                ),
            )
            transf_id: int = cur.fetchone()["id"]

            if tipo_transf == "Usuario para Estoque":
                cur.execute(
                    f"""UPDATE {tabela} SET
                        status='Estoque', responsavel=NULL,
                        data_devolucao=%s, usuario_anterior=%s,
                        updated_at=NOW() WHERE id_ativo=%s""",
                    (d.get("data_devolucao"), ativo["responsavel"], id_ativo),
                )
            elif tipo_transf == "Estoque para Usuario":
                cur.execute(
                    f"""UPDATE {tabela} SET
                        status='Ativo', responsavel=%s, fazenda=%s, setor=%s,
                        data_entrega=%s, data_devolucao=NULL,
                        usuario_anterior=%s, updated_at=NOW() WHERE id_ativo=%s""",
                    (
                        d.get("responsavel_destino"), d.get("fazenda_destino"),
                        d.get("setor_destino"), hoje,
                        ativo["responsavel"], id_ativo,
                    ),
                )
            elif tipo_transf == "Usuario para Turma":
                if tabela in ("celulares_turma", "celulares_ponto"):
                    cur.execute(
                        f"""UPDATE {tabela} SET
                            num_turma=%s, responsavel=%s, fazenda=%s, setor=%s,
                            data_entrega=%s, usuario_anterior=%s,
                            updated_at=NOW() WHERE id_ativo=%s""",
                        (
                            d.get("turma_destino"), d.get("turma_destino"), d.get("fazenda_destino"),
                            d.get("setor_destino"), hoje,
                            ativo["responsavel"], id_ativo,
                        ),
                    )
                else:
                    ativo_full = fetch_one(cur, f"SELECT * FROM {tabela} WHERE id_ativo=%s", (id_ativo,))
                    novo_id = sugerir_id_turma(cur)
                    
                    cur.execute(
                        """INSERT INTO celulares_turma
                           (id_ativo,num_turma,responsavel,fazenda,setor,modelo,tipo,status,
                            uso_celular,carregador,termo_assinado,data_entrega,data_devolucao,
                            gmail_clockin,senha,usuario_anterior,imei_1,imei_2,num_serie,
                            armazenamento,observacoes)
                           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                        (
                            novo_id, d.get("turma_destino"), d.get("turma_destino"), 
                            d.get("fazenda_destino") or ativo_full.get("fazenda"),
                            d.get("setor_destino") or ativo_full.get("setor"), 
                            ativo_full.get("modelo"), ativo_full.get("tipo"),
                            ativo_full.get("status"), ativo_full.get("uso_celular"), 
                            ativo_full.get("carregador"), ativo_full.get("termo_assinado"), 
                            hoje, ativo_full.get("data_devolucao"),
                            ativo_full.get("gmail"), ativo_full.get("senha"), 
                            ativo["responsavel"], ativo_full.get("imei_1"), 
                            ativo_full.get("imei_2"), ativo_full.get("num_serie"),
                            ativo_full.get("armazenamento"), f"Migrado do ID {id_ativo}"
                        )
                    )
                    # Sprint 1.2 — snapshot em ativos_arquivados antes de apagar o original
                    import json as _json
                    cur.execute(
                        """INSERT INTO ativos_arquivados
                           (id_ativo_origem, tabela_origem, motivo, migrado_para, snapshot, arquivado_por)
                           VALUES (%s, %s, %s, %s, %s, %s)""",
                        (
                            id_ativo, tabela, "Migração de Tipo",
                            novo_id,
                            _json.dumps(dict(ativo_full), default=str),
                            session.get("usuario") or session.get("email"),
                        ),
                    )
                    cur.execute(f"DELETE FROM {tabela} WHERE id_ativo=%s", (id_ativo,))

                    # Sprint 1.3 — ancorar UPDATE no PK transf_id (nunca muda)
                    cur.execute(
                        "UPDATE transferencias SET observacoes = CASE "
                        "WHEN observacoes IS NULL OR observacoes = '' THEN %s "
                        "ELSE observacoes || ' | ' || %s END "
                        "WHERE id = %s",
                        (
                            f"ID anterior: {id_ativo}", f"ID anterior: {id_ativo}",
                            transf_id,
                        ),
                    )
                    cur.execute("UPDATE historico SET id_ativo=%s WHERE id_ativo=%s", (novo_id, id_ativo))
                    cur.execute("UPDATE transferencias SET id_ativo=%s, tipo_equipamento='Celular Turma' WHERE id_ativo=%s", (novo_id, id_ativo))
                    
                    id_ativo = novo_id
                    tipo_eq = "Celular Turma"
            else:
                cur.execute(
                    f"""UPDATE {tabela} SET
                        responsavel=%s, fazenda=%s, setor=%s,
                        data_entrega=%s, usuario_anterior=%s,
                        updated_at=NOW() WHERE id_ativo=%s""",
                    (
                        d.get("responsavel_destino"), d.get("fazenda_destino"),
                        d.get("setor_destino"), hoje,
                        ativo["responsavel"], id_ativo,
                    ),
                )

            log_historico(
                cur, id_ativo, tipo_eq,
                f"Transferência: {tipo_transf} → {d.get('responsavel_destino') or 'Estoque'}",
            )

            fazenda_dest = d.get("fazenda_destino", "")
            setor_dest   = d.get("setor_destino", "")
            if (
                tipo_transf not in ("Usuario para Estoque",)
                and fazenda_dest
                and setor_dest
                and not id_ativo.startswith("CL-TRM-")
            ):
                tipo_sigla = _SIGLA_TIPO_MAP.get(tipo_eq)
                if tipo_eq == "Computador" and not tipo_sigla:
                    ativo_full = fetch_one(cur, "SELECT tipo FROM computadores WHERE id_ativo=%s", (id_ativo,))
                    tipo_sigla = "DK" if (ativo_full or {}).get("tipo", "").lower() == "desktop" else "NT"

                if tipo_sigla:
                    local_sigla = FAZENDA_PARA_SIGLA.get(fazenda_dest, fazenda_dest.upper()[:3])
                    setor_sigla = SETOR_PARA_SIGLA.get(setor_dest, setor_dest.upper()[:3])
                    try:
                        seq = proximo_sequencial(cur, tipo_sigla, local_sigla, setor_sigla)
                        novo_id = gerar_id_ativo(tipo_sigla, local_sigla, setor_sigla, seq)
                        # Sprint 1.3 — ancorar UPDATE no PK transf_id
                        cur.execute(
                            "UPDATE transferencias SET observacoes = CASE "
                            "WHEN observacoes IS NULL OR observacoes = '' THEN %s "
                            "ELSE observacoes || ' | ' || %s END "
                            "WHERE id = %s",
                            (
                                f"ID anterior: {id_ativo}", f"ID anterior: {id_ativo}",
                                transf_id,
                            ),
                        )
                        cur.execute(
                            f"UPDATE {tabela} SET id_ativo=%s WHERE id_ativo=%s",
                            (novo_id, id_ativo),
                        )
                        cur.execute(
                            "UPDATE historico SET id_ativo=%s WHERE id_ativo=%s",
                            (novo_id, id_ativo),
                        )
                        cur.execute(
                            "UPDATE transferencias SET id_ativo=%s WHERE id_ativo=%s",
                            (novo_id, id_ativo),
                        )
                        id_ativo = novo_id
                    except ValueError as e:
                        current_app.logger.warning(f"Regen ID falhou para {id_ativo}: {e}")
                        return jsonify({
                            "ok": True,
                            "msg": "Transferência registrada com sucesso!",
                            "aviso": f"Aviso: Não foi possível gerar novo ID automaticamente. Erro: {e}"
                        })

    # Sprint 4.4 — retorna id_ativo final (pode ter sido renomeado durante a transferência)
    return jsonify({"ok": True, "msg": "Transferência registrada com sucesso!", "id_ativo": id_ativo})

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

    # Sprint 2.1 — paginação para evitar varredura completa da tabela
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

    return jsonify({"items": rows, "page": page, "per_page": per_page})

@api_transferencias_bp.route("/api/transferencias/<id_ativo>/historico")
@login_required
def historico_transferencias(id_ativo: str) -> Response:
    """Retorna o histórico paginado de transferências de um ativo."""
    page = max(1, int(request.args.get("page", 1)))
    per_page = min(100, max(1, int(request.args.get("per_page", 20))))
    offset = (page - 1) * per_page

    with acquire_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) AS total FROM transferencias WHERE id_ativo=%s",
                (id_ativo,),
            )
            total = cur.fetchone()["total"]

            rows = fetch_all(
                cur,
                "SELECT * FROM transferencias WHERE id_ativo=%s ORDER BY id DESC LIMIT %s OFFSET %s",
                (id_ativo, per_page, offset),
            )

    return jsonify({
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": (total + per_page - 1) // per_page,
        "items": rows,
    })

@api_transferencias_bp.route("/api/transferencias/estoque")
@login_required
def ativos_em_estoque() -> Response:
    """Lista todos os ativos com status 'Estoque' em uma única query UNION ALL.

    Sprint 2.2 — substitui loop de N queries por 1 UNION ALL,
    reduzindo de 8 round-trips para 1 e eliminando risco de DoS por query explosion.
    """
    _UNION_ESTOQUE_SQL = """
        SELECT id_ativo, modelo, fazenda, setor, updated_at, 'Celular'          AS tipo_equipamento FROM celulares          WHERE status='Estoque'
        UNION ALL
        SELECT id_ativo, modelo, fazenda, NULL,   updated_at, 'Celular Ponto'   AS tipo_equipamento FROM celulares_ponto     WHERE status='Estoque'
        UNION ALL
        SELECT id_ativo, modelo, fazenda, setor, updated_at, 'Celular Inspecão' AS tipo_equipamento FROM celulares_inspecao  WHERE status='Estoque'
        UNION ALL
        SELECT id_ativo, modelo, fazenda, setor, updated_at, 'Celular Turma'   AS tipo_equipamento FROM celulares_turma     WHERE status='Estoque'
        UNION ALL
        SELECT id_ativo, modelo, fazenda, setor, updated_at, 'Computador'      AS tipo_equipamento FROM computadores        WHERE status='Estoque'
        UNION ALL
        SELECT id_ativo, modelo, fazenda, setor, updated_at, 'Impressora'      AS tipo_equipamento FROM impressoras         WHERE status='Estoque'
        UNION ALL
        SELECT id_ativo, modelo, fazenda, setor, updated_at, 'Estabilizador'   AS tipo_equipamento FROM estabilizadores     WHERE status='Estoque'
        UNION ALL
        SELECT id_ativo, modelo, fazenda, setor, updated_at, 'Starlink'        AS tipo_equipamento FROM starlink            WHERE status='Estoque'
        ORDER BY updated_at DESC
    """
    with acquire_conn() as conn:
        with conn.cursor() as cur:
            resultado = fetch_all(cur, _UNION_ESTOQUE_SQL)
    return jsonify(resultado)
