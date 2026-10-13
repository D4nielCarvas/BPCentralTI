"""Rotas para geração, consulta e ações via QR Code."""

from __future__ import annotations

from flask import Blueprint, jsonify, render_template, request, session, Response

from utils.db_layer import acquire_conn as get_db, fetch_one as _fetch_one, row_to_dict
from utils.auth_utils import admin_required
from utils.api_utils import log_historico

bp = Blueprint("api_qrcode", __name__, url_prefix="")

_TIPO_CONFIG: dict[str, dict] = {
    "estoque": {
        "tabela": "estoque",
        "pk": "id",
        "pk_type": "int",
        "label": "Item de Estoque",
        "campos_display": ["item", "quantidade", "unidade", "localizacao", "observacoes"],
        "nome_campo": "item",
    },
    "computador": {
        "tabela": "computadores",
        "pk": "id_ativo",
        "pk_type": "str",
        "label": "Computador / Notebook",
        "campos_display": ["id_ativo", "modelo", "marca", "fazenda", "setor", "responsavel", "status"],
        "nome_campo": "modelo",
    },
    "celular": {
        "tabela": "celulares",
        "pk": "id_ativo",
        "pk_type": "str",
        "label": "Celular",
        "campos_display": ["id_ativo", "modelo", "marca", "fazenda", "setor", "responsavel", "status"],
        "nome_campo": "modelo",
    },
    "impressora": {
        "tabela": "impressoras",
        "pk": "id_ativo",
        "pk_type": "str",
        "label": "Impressora",
        "campos_display": ["id_ativo", "modelo", "marca", "fazenda", "setor", "status"],
        "nome_campo": "modelo",
    },
    "estabilizador": {
        "tabela": "estabilizadores",
        "pk": "id_ativo",
        "pk_type": "str",
        "label": "Estabilizador",
        "campos_display": ["id_ativo", "modelo", "marca", "fazenda", "setor", "status"],
        "nome_campo": "modelo",
    },
    "starlink": {
        "tabela": "starlink",
        "pk": "id_ativo",
        "pk_type": "str",
        "label": "Starlink",
        "campos_display": ["id_ativo", "modelo", "fazenda", "status"],
        "nome_campo": "modelo",
    },
}


def _get_item(tipo: str, item_id: str) -> dict | None:
    """
    Busca um item pelo tipo e ID.
    Retorna dict com os dados ou None se não encontrado.
    """
    cfg = _TIPO_CONFIG.get(tipo)
    if not cfg:
        return None

    pk_val = int(item_id) if cfg["pk_type"] == "int" else item_id

    with get_db() as conn:
        with conn.cursor() as cur:
            row = _fetch_one(
                cur,
                f"SELECT * FROM {cfg['tabela']} WHERE {cfg['pk']} = %s",
                (pk_val,),
            )
    return row


def _get_chamados_ativo(id_ativo: str) -> list[dict]:
    """Retorna chamados abertos vinculados ao id_ativo."""
    with get_db() as conn:
        with conn.cursor() as cur:
            from utils.db_layer import fetch_all as _fetch_all
            rows = _fetch_all(
                cur,
                """SELECT id, titulo, status, data_abertura
                   FROM chamados
                   WHERE id_ativo = %s AND status NOT IN ('Fechado', 'Cancelado')
                   ORDER BY data_abertura DESC LIMIT 10""",
                (id_ativo,),
            )
    return rows


@bp.route("/qr/<tipo>/<item_id>")
@admin_required
def qr_action_page(tipo: str, item_id: str) -> Response:
    """
    Página HTML exibida ao escanear o QR code.
    Comportamento diferenciado por tipo:
      - estoque  → formulário de baixa (saída)
      - ativos   → painel com status + botão "Chegou na TI" + chamados abertos
    """
    cfg = _TIPO_CONFIG.get(tipo)
    if not cfg:
        return render_template(
            "qr_action.html",
            erro="Tipo de item desconhecido.",
            tipo=tipo,
            item_id=item_id,
        )

    item = _get_item(tipo, item_id)
    if not item:
        return render_template(
            "qr_action.html",
            erro=f"{cfg['label']} não encontrado: {item_id}",
            tipo=tipo,
            item_id=item_id,
        )

    chamados = []
    if tipo != "estoque":
        try:
            chamados = _get_chamados_ativo(item_id)
        except Exception:
            chamados = []

    nome_display = item.get(cfg["nome_campo"], item_id) or item_id
    usuario_logado = session.get("nome") or session.get("usuario") or "Admin"

    return render_template(
        "qr_action.html",
        tipo=tipo,
        item_id=item_id,
        item=item,
        cfg=cfg,
        nome_display=nome_display,
        chamados=chamados,
        usuario_logado=usuario_logado,
        erro=None,
    )


@bp.route("/qr/imprimir/<tipo>/<item_id>")
@admin_required
def qr_imprimir_etiqueta(tipo: str, item_id: str) -> Response:
    """
    Renderiza uma página HTML isolada contendo exclusivamente a etiqueta
    formatada para impressoras térmicas (ex: Smart Label Printer 650).
    Evita que o navegador imprima elementos da aplicação ou quebre margens.
    """
    cfg = _TIPO_CONFIG.get(tipo)
    if not cfg:
        return "Tipo de item inválido", 400

    item = _get_item(tipo, item_id)
    if not item:
        return "Item não encontrado", 404

    nome_display = item.get(cfg["nome_campo"], item_id) or item_id
    qr_url = f"{request.host_url.rstrip('/')}/qr/{tipo}/{item_id}"

    return render_template(
        "etiqueta_impressao.html",
        tipo=tipo,
        item_id=item_id,
        item=item,
        cfg=cfg,
        nome_display=nome_display,
        qr_url=qr_url,
    )



@bp.route("/api/qr/info/<tipo>/<item_id>")
@admin_required
def api_qr_info(tipo: str, item_id: str) -> Response:
    """
    Retorna JSON com os dados resumidos do item para exibição no modal de QR.
    Não expõe campos sensíveis (senha_windows, etc.).
    """
    cfg = _TIPO_CONFIG.get(tipo)
    if not cfg:
        return jsonify({"ok": False, "msg": "Tipo inválido"}), 400

    item = _get_item(tipo, item_id)
    if not item:
        return jsonify({"ok": False, "msg": "Item não encontrado"}), 404

    # Sanitizar campos sensíveis antes de expor
    CAMPOS_SENSIVEIS = {"senha_windows", "senha_starlink", "senha", "pin"}
    safe_item = {k: v for k, v in item.items() if k not in CAMPOS_SENSIVEIS}

    return jsonify({
        "ok": True,
        "tipo": tipo,
        "label": cfg["label"],
        "nome_display": item.get(cfg["nome_campo"], item_id),
        "item": safe_item,
    })


@bp.route("/api/qr/ativo/checkin/<tipo>/<item_id>", methods=["POST"])
@admin_required
def api_qr_checkin_ativo(tipo: str, item_id: str) -> Response:
    """Registra recebimento do ativo no setor de TI via QR Code."""
    if tipo == "estoque":
        return jsonify({"ok": False, "msg": "Use a rota de saída para itens de estoque."}), 400

    cfg = _TIPO_CONFIG.get(tipo)
    if not cfg:
        return jsonify({"ok": False, "msg": "Tipo de ativo inválido"}), 400

    item = _get_item(tipo, item_id)
    if not item:
        return jsonify({"ok": False, "msg": "Ativo não encontrado"}), 404

    status_anterior = item.get("status", "Desconhecido")
    responsavel_ti = session.get("nome") or session.get("usuario") or "TI"
    observacao = request.json.get("observacao", "") if request.json else ""

    nota_historico = f"Chegou na TI via QR Code. Status anterior: {status_anterior}."
    if observacao:
        nota_historico += f" Obs: {observacao}"

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"UPDATE {cfg['tabela']} SET status='Com TI' WHERE {cfg['pk']} = %s",
                (item_id,),
            )
            log_historico(
                cur,
                item_id,
                cfg["label"],
                "Chegou na TI",
                "status",
                status_anterior,
                "Com TI",
            )

    return jsonify({
        "ok": True,
        "msg": f"Registrado: {item_id} está Com TI.",
        "status_anterior": status_anterior,
    })


@bp.route("/api/qr/estoque/<int:eid>/saida", methods=["POST"])
@admin_required
def api_qr_saida_estoque(eid: int) -> Response:
    """Registra saída de estoque via QR Code."""
    d = request.json or {}

    try:
        qtd = int(d.get("quantidade", 0))
    except (ValueError, TypeError):
        return jsonify({"ok": False, "msg": "Quantidade inválida"}), 400

    if qtd <= 0:
        return jsonify({"ok": False, "msg": "Quantidade deve ser maior que zero"}), 400

    motivo = d.get("motivo", "Saída via QR Code")
    responsavel = session.get("nome") or session.get("usuario") or "Admin"

    with get_db() as conn:
        with conn.cursor() as cur:
            # Bloqueia a linha para evitar concorrência
            cur.execute("SELECT * FROM estoque WHERE id=%s FOR UPDATE", (eid,))
            item = row_to_dict(cur.fetchone())
            if not item:
                return jsonify({"ok": False, "msg": "Item de estoque não encontrado"}), 404

            nova_qtd = item["quantidade"] - qtd
            if nova_qtd < 0:
                return jsonify({
                    "ok": False,
                    "msg": f"Estoque insuficiente! Disponível: {item['quantidade']}",
                }), 400

            cur.execute(
                "UPDATE estoque SET quantidade=%s, updated_at=NOW() WHERE id=%s",
                (nova_qtd, eid),
            )
            cur.execute(
                """INSERT INTO estoque_movimentacoes
                   (estoque_id, tipo, quantidade, motivo, responsavel)
                   VALUES (%s, 'saida', %s, %s, %s)""",
                (eid, qtd, motivo, responsavel),
            )

    return jsonify({
        "ok": True,
        "msg": f"Saída de {qtd} {item.get('unidade','un')} registrada!",
        "nova_quantidade": nova_qtd,
        "item_nome": item.get("item", ""),
    })
