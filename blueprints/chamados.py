"""
blueprints/chamados.py — Rotas de Chamados para viewers (Portal Fazenda / Helpdesk).

Segurança:
    - viewer_required em todas as rotas.
    - Anti-IDOR: viewers só acessam chamados da sua localidade_id de sessão.
    - localidade_id e usuario_id SEMPRE lidos da sessão — nunca do body.

Complexidade: O(n) para listagem; O(1) para criação e envio de mensagem.
"""

from __future__ import annotations

from typing import Any
import os
import uuid
from werkzeug.utils import secure_filename

from flask import (
    Blueprint, abort, flash, redirect,
    render_template, request, session, url_for,
)

from auth_utils import get_localidade_filter, get_usuario_id, viewer_required
from db_layer import acquire_conn, fetch_all, fetch_one

chamados_bp = Blueprint("chamados", __name__, url_prefix="/fazenda/chamados")

_STATUS_VALIDOS = frozenset({
    "aberto", "em_atendimento", "pendente_usuario", "resolvido", "fechado"
})
_PRIORIDADES = ["baixa", "media", "alta", "urgente"]
_TABELAS_EQUIPAMENTOS = [
    "celulares", "computadores", "impressoras",
    "estabilizadores", "starlink", "celulares_ponto",
]

UPLOAD_FOLDER = os.path.join('static', 'uploads', 'chamados')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'pdf', 'zip', 'rar', 'txt', 'csv'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def save_anexo(arquivo, chamado_id, mensagem_id, usuario_id, cur):
    if arquivo and arquivo.filename and allowed_file(arquivo.filename):
        filename = secure_filename(arquivo.filename)
        # prefixa com uuid para evitar colisao
        unique_name = f"{uuid.uuid4().hex[:8]}_{filename}"
        caminho = os.path.join(UPLOAD_FOLDER, unique_name)
        os.makedirs(UPLOAD_FOLDER, exist_ok=True)
        arquivo.save(caminho)
        caminho_db = f"/{UPLOAD_FOLDER.replace(os.sep, '/')}/{unique_name}"
        cur.execute(
            """
            INSERT INTO chamado_anexos (chamado_id, mensagem_id, usuario_id, nome_arquivo, caminho_arquivo)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (chamado_id, mensagem_id, usuario_id, filename, caminho_db)
        )


# ═══════════════════════════════════════════════════════════════════════════════
# LISTAGEM DE CHAMADOS DA LOCALIDADE
# ═══════════════════════════════════════════════════════════════════════════════

@chamados_bp.route("/")
@viewer_required
def listar_chamados():
    """Lista chamados da localidade do viewer. Admins veem todos."""
    localidade_id = get_localidade_filter()
    filtro_status = request.args.get("status", "").strip()

    params: list[Any] = []
    query = """
        SELECT
            c.id, c.titulo, c.prioridade, c.status,
            c.criado_em, c.atualizado_em,
            l.nome AS localidade_nome,
            ua.nome AS tecnico_nome
        FROM chamados c
        JOIN localidades l ON l.id = c.localidade_id
        LEFT JOIN usuarios ua ON ua.id = c.atribuido_a
        WHERE 1=1
    """

    if localidade_id:
        query += " AND c.localidade_id = %s"
        params.append(localidade_id)

    if filtro_status and filtro_status in _STATUS_VALIDOS:
        query += " AND c.status = %s"
        params.append(filtro_status)

    query += " ORDER BY c.id DESC"

    with acquire_conn() as conn:
        with conn.cursor() as cur:
            chamados = fetch_all(cur, query, tuple(params))

    return render_template(
        "fazenda/chamados.html",
        chamados=chamados,
        filtro_status=filtro_status,
        status_validos=sorted(_STATUS_VALIDOS),
    )


# ═══════════════════════════════════════════════════════════════════════════════
# NOVO CHAMADO
# ═══════════════════════════════════════════════════════════════════════════════

@chamados_bp.route("/novo", methods=["GET", "POST"])
@viewer_required
def novo_chamado():
    """Abre um novo chamado de suporte."""
    localidade_id = get_localidade_filter()
    usuario_id = get_usuario_id()

    if session.get("role") == "viewer" and not localidade_id:
        flash("Sua conta não está vinculada a uma localidade. Contate o administrador.", "danger")
        return redirect(url_for("chamados.listar_chamados"))

    if request.method == "POST":
        titulo     = (request.form.get("titulo") or "").strip()
        descricao  = (request.form.get("descricao") or "").strip()
        prioridade = (request.form.get("prioridade") or "media").strip()
        id_ativo   = (request.form.get("id_ativo") or "").strip() or None
        loc_id     = localidade_id or request.form.get("localidade_id")

        errors: list[str] = []
        if not titulo:
            errors.append("O título é obrigatório.")
        if not descricao:
            errors.append("A descrição do problema é obrigatória.")
        if prioridade not in _PRIORIDADES:
            prioridade = "media"
        if not loc_id:
            errors.append("Localidade não identificada.")

        if errors:
            for msg in errors:
                flash(msg, "warning")
            return redirect(url_for("chamados.novo_chamado"))

        etiquetas_selecionadas = request.form.getlist("etiqueta_ids")

        with acquire_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO chamados
                        (localidade_id, criado_por, id_ativo, titulo, descricao, prioridade, status)
                    VALUES (%s, %s, %s, %s, %s, %s, 'aberto')
                    RETURNING id
                    """,
                    (loc_id, usuario_id, id_ativo, titulo, descricao, prioridade),
                )
                novo_id = cur.fetchone()["id"]

                # Vincular etiquetas selecionadas
                if etiquetas_selecionadas:
                    for et_id in etiquetas_selecionadas:
                        if et_id.isdigit():
                            cur.execute(
                                "INSERT INTO chamados_etiquetas_rel (chamado_id, etiqueta_id) VALUES (%s, %s) ON CONFLICT DO NOTHING",
                                (novo_id, et_id),
                            )

                # Salvar anexo opcional
                arquivo = request.files.get("anexo")
                if arquivo:
                    save_anexo(arquivo, novo_id, None, usuario_id, cur)

                # Notificar administradores
                cur.execute(
                    """
                    INSERT INTO notificacoes (usuario_id, chamado_id, mensagem)
                    SELECT id, %s, %s
                    FROM usuarios 
                    WHERE role = 'admin' AND ativo = TRUE
                    """,
                    (novo_id, f"Novo chamado: {titulo[:50]}")
                )

        flash("Chamado aberto com sucesso! A equipe de TI entrará em contato.", "success")
        return redirect(url_for("chamados.detalhe_chamado", chamado_id=novo_id))

    # GET — carrega equipamentos ativos da localidade
    itens_ativos: list[str] = []
    localidades: list[dict] = []
    todas_etiquetas: list[dict] = []
    modelos_prontos: list[dict] = []

    with acquire_conn() as conn:
        with conn.cursor() as cur:
            todas_etiquetas = fetch_all(cur, "SELECT id, nome, cor_hex FROM chamado_etiquetas ORDER BY nome ASC")
            modelos_prontos = fetch_all(cur, "SELECT id, nome_modelo, titulo_padrao, descricao_padrao, prioridade_padrao FROM chamado_modelos WHERE ativo = TRUE ORDER BY nome_modelo ASC")
            loc_query = localidade_id

            if session.get("role") == "admin":
                localidades = fetch_all(
                    cur, "SELECT id, nome FROM localidades ORDER BY nome ASC"
                )
                loc_query = localidade_id  # admin sem localidade não filtra

            if loc_query:
                for tabela in _TABELAS_EQUIPAMENTOS:
                    try:
                        rows = fetch_all(
                            cur,
                            f"SELECT id_ativo FROM {tabela} WHERE localidade_id = %s AND status = 'Ativo' ORDER BY id_ativo",
                            (loc_query,),
                        )
                        itens_ativos.extend(r["id_ativo"] for r in rows)
                    except Exception:
                        pass

    return render_template(
        "fazenda/novo_chamado.html",
        itens_ativos=sorted(set(itens_ativos)),
        prioridades=_PRIORIDADES,
        localidades=localidades,
        localidade_id_sessao=localidade_id,
        todas_etiquetas=todas_etiquetas,
        modelos_prontos=modelos_prontos,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# DETALHE + CHAT DO CHAMADO
# ═══════════════════════════════════════════════════════════════════════════════

@chamados_bp.route("/<int:chamado_id>", methods=["GET", "POST"])
@viewer_required
def detalhe_chamado(chamado_id: int):
    """
    Exibe o chamado e o histórico de mensagens (chat).

    POST: Insere nova mensagem do usuário.
    Se o status era 'pendente_usuario', volta para 'em_atendimento' automaticamente.

    Segurança Anti-IDOR:
        Viewer só acessa chamados da própria localidade_id de sessão.
    """
    localidade_id = get_localidade_filter()
    usuario_id    = get_usuario_id()
    role          = session.get("role")

    with acquire_conn() as conn:
        with conn.cursor() as cur:
            chamado = fetch_one(
                cur,
                """
                SELECT c.*,
                       l.nome AS localidade_nome,
                       uc.nome AS criado_por_nome,
                       ua.nome AS tecnico_nome
                FROM chamados c
                JOIN localidades l  ON l.id  = c.localidade_id
                JOIN usuarios uc    ON uc.id = c.criado_por
                LEFT JOIN usuarios ua ON ua.id = c.atribuido_a
                WHERE c.id = %s
                """,
                (chamado_id,),
            )

            if not chamado:
                abort(404)

            # Anti-IDOR: viewer só vê chamados da sua localidade
            if role == "viewer" and chamado["localidade_id"] != localidade_id:
                abort(403)

            mensagens = fetch_all(
                cur,
                """
                SELECT cm.id, cm.mensagem, cm.criado_em, cm.is_sistema,
                       u.nome AS autor_nome, u.role AS autor_role, u.id AS autor_id,
                       ca.caminho_arquivo, ca.nome_arquivo
                FROM chamado_mensagens cm
                JOIN usuarios u ON u.id = cm.usuario_id
                LEFT JOIN chamado_anexos ca ON ca.mensagem_id = cm.id
                WHERE cm.chamado_id = %s
                ORDER BY cm.criado_em ASC
                """,
                (chamado_id,),
            )
            
            anexos_chamado = fetch_all(
                cur,
                """
                SELECT caminho_arquivo, nome_arquivo 
                FROM chamado_anexos 
                WHERE chamado_id = %s AND mensagem_id IS NULL
                """,
                (chamado_id,)
            )

    if request.method == "POST":
        mensagem = (request.form.get("mensagem") or "").strip()
        if not mensagem:
            flash("A mensagem não pode estar vazia.", "warning")
            return redirect(url_for("chamados.detalhe_chamado", chamado_id=chamado_id))

        with acquire_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO chamado_mensagens (chamado_id, usuario_id, mensagem) VALUES (%s, %s, %s) RETURNING id",
                    (chamado_id, usuario_id, mensagem),
                )
                nova_msg_id = cur.fetchone()["id"]

                # Salvar anexo opcional
                arquivo = request.files.get("anexo")
                if arquivo:
                    save_anexo(arquivo, chamado_id, nova_msg_id, usuario_id, cur)

                # Viewer respondeu → volta de 'pendente_usuario' para 'em_atendimento'
                if chamado["status"] == "pendente_usuario":
                    cur.execute(
                        "UPDATE chamados SET status = 'em_atendimento' WHERE id = %s",
                        (chamado_id,),
                    )

        return redirect(url_for("chamados.detalhe_chamado", chamado_id=chamado_id))

    return render_template(
        "fazenda/detalhe_chamado.html",
        chamado=chamado,
        mensagens=mensagens,
        anexos_chamado=anexos_chamado,
        usuario_id=usuario_id,
        status_validos=sorted(_STATUS_VALIDOS),
    )
