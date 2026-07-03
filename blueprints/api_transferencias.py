from flask import Blueprint, jsonify, request, Response
from datetime import date
from utils.auth_utils import login_required, admin_required
from utils.db_layer import acquire_conn, fetch_all, fetch_one
from utils.api_utils import log_historico
from utils.id_generator import (
    proximo_sequencial, gerar_id_ativo, 
    SIGLAS_TIPO, SIGLAS_LOCAL, SIGLAS_SETOR
)
from app import app  # para app.logger.warning (após refatorar o log, idealmente usar current_app)
from flask import current_app

FAZENDA_PARA_SIGLA: dict[str, str] = {v: k for k, v in SIGLAS_LOCAL.items()}
SETOR_PARA_SIGLA: dict[str, str]   = {v: k for k, v in SIGLAS_SETOR.items()}

api_transferencias_bp = Blueprint('api_transferencias', __name__)

# Mapeamento tipo_equipamento → nome da tabela
_TABELA_POR_TIPO: dict[str, str] = {
    "Celular":          "celulares",
    "Celular Ponto":    "celulares_ponto",
    "Celular Inspeção": "celulares_inspecao",
    "Celular Turma":    "celulares_turma",
    "Computador":       "computadores",
    "Impressora":       "impressoras",
    "Estabilizador":    "estabilizadores",
    "Starlink":         "starlink",
}

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

            cur.execute(
                """INSERT INTO transferencias
                   (id_ativo,tipo_equipamento,responsavel_origem,fazenda_origem,setor_origem,
                    responsavel_destino,fazenda_destino,setor_destino,tipo_transferencia,
                    motivo,data_transferencia,registrado_por,observacoes,termo_pdf)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (
                    id_ativo, tipo_eq,
                    d.get("responsavel_origem"), d.get("fazenda_origem"), d.get("setor_origem"),
                    d.get("responsavel_destino"), d.get("fazenda_destino"), d.get("setor_destino"),
                    tipo_transf, d.get("motivo"), data_transf,
                    d.get("registrado_por"), d.get("observacoes"), d.get("termo_pdf"),
                ),
            )

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
                    cur.execute(
                        f"""UPDATE {tabela} SET
                            responsavel=%s, fazenda=%s, setor=%s,
                            data_entrega=%s, usuario_anterior=%s,
                            updated_at=NOW() WHERE id_ativo=%s""",
                        (
                            d.get("turma_destino"), d.get("fazenda_destino"),
                            d.get("setor_destino"), hoje,
                            ativo["responsavel"], id_ativo,
                        ),
                    )
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
                        cur.execute(
                            "UPDATE transferencias SET observacoes = CASE "
                            "WHEN observacoes IS NULL OR observacoes = '' THEN %s "
                            "ELSE observacoes || ' | ' || %s END "
                            "WHERE id_ativo=%s AND id=(SELECT MAX(id) FROM transferencias WHERE id_ativo=%s)",
                            (
                                f"ID anterior: {id_ativo}", f"ID anterior: {id_ativo}",
                                id_ativo, id_ativo,
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

    return jsonify({"ok": True, "msg": "Transferência registrada com sucesso!"})

@api_transferencias_bp.route("/api/transferencias", methods=["GET"])
@login_required
def listar_transferencias() -> Response:
    """Lista transferências com filtros opcionais."""
    id_ativo = request.args.get("id_ativo", "")
    tipo_eq = request.args.get("tipo_equipamento", "")
    data_ini = request.args.get("data_inicio", "")
    data_fim = request.args.get("data_fim", "")

    query = "SELECT * FROM transferencias WHERE 1=1"
    params = []

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

    query += " ORDER BY id DESC"

    with acquire_conn() as conn:
        with conn.cursor() as cur:
            rows = fetch_all(cur, query, tuple(params))

    return jsonify(rows)

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
    """Lista todos os ativos com status 'Estoque' em todas as tabelas de equipamentos."""
    resultado = []
    with acquire_conn() as conn:
        with conn.cursor() as cur:
            for tipo_nome, nome_tabela in _TABELA_POR_TIPO.items():
                rows = fetch_all(
                    cur,
                    f"SELECT id_ativo, modelo, fazenda, setor, updated_at "
                    f"FROM {nome_tabela} WHERE status='Estoque' ORDER BY updated_at DESC",
                )
                for r in rows:
                    resultado.append({**r, "tipo_equipamento": tipo_nome})
    return jsonify(resultado)
