"""
blueprints/admin_chamados.py — Painel de Chamados para técnicos de TI.

Fluxo:
    1. Admin acessa /admin/chamados → vê fila de abertos + seus chamados.
    2. Clica "Assumir" → atribuido_a = usuario_id, status → em_atendimento.
    3. Abre o chat → troca mensagens, muda status, transfere ou gera manutenção.

Segurança: admin_required em todas as rotas. Nunca confia em IDs do body.
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

from auth_utils import admin_required, get_usuario_id
from db_layer import acquire_conn, fetch_all, fetch_one

admin_chamados_bp = Blueprint("admin_chamados", __name__, url_prefix="/admin/chamados")

_STATUS_VALIDOS = frozenset({
    "aberto", "em_atendimento", "pendente_usuario", "resolvido", "fechado"
})
_PRIORIDADES = ["baixa", "media", "alta", "urgente"]

UPLOAD_FOLDER = os.path.join('static', 'uploads', 'chamados')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'pdf', 'zip', 'rar', 'txt', 'csv'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def save_anexo(arquivo, chamado_id, mensagem_id, usuario_id, cur):
    if arquivo and arquivo.filename and allowed_file(arquivo.filename):
        filename = secure_filename(arquivo.filename)
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

# ── Helper: query base de chamados com etiquetas ──────────────────────────────
_QUERY_CHAMADOS = """
    SELECT
        c.id, c.titulo, c.descricao, c.prioridade, c.status,
        c.criado_em, c.atualizado_em, c.id_ativo,
        l.nome  AS localidade_nome,
        uc.nome AS criado_por_nome,
        ua.nome AS tecnico_nome,
        ua.id   AS tecnico_id
    FROM chamados c
    JOIN localidades l  ON l.id  = c.localidade_id
    JOIN usuarios uc    ON uc.id = c.criado_por
    LEFT JOIN usuarios ua ON ua.id = c.atribuido_a
"""


# ═══════════════════════════════════════════════════════════════════════════════
# DASHBOARD: FILA + MEUS CHAMADOS
# ═══════════════════════════════════════════════════════════════════════════════

@admin_chamados_bp.route("/")
@admin_required
def dashboard_chamados():
    """
    Exibe:
        - Fila de Abertos: chamados sem atribuido_a e não resolvidos/fechados.
        - Meus Chamados: chamados atribuídos ao técnico logado.

    Filtros opcionais: localidade, prioridade, etiqueta.
    """
    usuario_id      = get_usuario_id()
    filtro_local    = request.args.get("localidade", "").strip()
    filtro_prioridade = request.args.get("prioridade", "").strip()

    def build_filter(base_query: str, params: list) -> str:
        q = base_query
        if filtro_local:
            q += " AND c.localidade_id = %s"
            params.append(filtro_local)
        if filtro_prioridade and filtro_prioridade in _PRIORIDADES:
            q += " AND c.prioridade = %s"
            params.append(filtro_prioridade)
        return q

    with acquire_conn() as conn:
        with conn.cursor() as cur:
            # Fila de abertos (sem técnico, não resolvidos)
            params_fila: list[Any] = []
            q_fila = build_filter(
                _QUERY_CHAMADOS + " WHERE c.atribuido_a IS NULL AND c.status NOT IN ('resolvido','fechado')",
                params_fila,
            ) + " ORDER BY CASE c.prioridade WHEN 'urgente' THEN 0 WHEN 'alta' THEN 1 WHEN 'media' THEN 2 ELSE 3 END, c.id ASC"
            fila_abertos = fetch_all(cur, q_fila, tuple(params_fila))

            # Meus chamados em andamento
            params_meus: list[Any] = [usuario_id]
            q_meus = build_filter(
                _QUERY_CHAMADOS + " WHERE c.atribuido_a = %s AND c.status NOT IN ('resolvido','fechado')",
                params_meus,
            ) + " ORDER BY CASE c.prioridade WHEN 'urgente' THEN 0 WHEN 'alta' THEN 1 WHEN 'media' THEN 2 ELSE 3 END, c.id DESC"
            meus_chamados = fetch_all(cur, q_meus, tuple(params_meus))

            localidades = fetch_all(cur, "SELECT id, nome FROM localidades ORDER BY nome ASC")

    return render_template(
        "admin/chamados_dashboard.html",
        fila_abertos=fila_abertos,
        meus_chamados=meus_chamados,
        localidades=localidades,
        prioridades=_PRIORIDADES,
        filtro_local=filtro_local,
        filtro_prioridade=filtro_prioridade,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# ASSUMIR CHAMADO
# ═══════════════════════════════════════════════════════════════════════════════

@admin_chamados_bp.route("/<int:chamado_id>/assumir", methods=["POST"])
@admin_required
def assumir_chamado(chamado_id: int):
    """Atribui o chamado ao técnico logado e muda status para 'em_atendimento'."""
    usuario_id = get_usuario_id()

    with acquire_conn() as conn:
        with conn.cursor() as cur:
            chamado = fetch_one(cur, "SELECT id, status, atribuido_a FROM chamados WHERE id = %s", (chamado_id,))
            if not chamado:
                abort(404)

            cur.execute(
                "UPDATE chamados SET atribuido_a = %s, status = 'em_atendimento' WHERE id = %s",
                (usuario_id, chamado_id),
            )
            # Mensagem automática no chat
            cur.execute(
                "INSERT INTO chamado_mensagens (chamado_id, usuario_id, mensagem, is_sistema) VALUES (%s, %s, %s, TRUE)",
                (chamado_id, usuario_id, f"Chamado assumido pela equipe de TI."),
            )

    flash("Chamado assumido com sucesso!", "success")
    return redirect(url_for("admin_chamados.detalhe_chamado_admin", chamado_id=chamado_id))


# ═══════════════════════════════════════════════════════════════════════════════
# DETALHE + CHAT DO CHAMADO (ADMIN)
# ═══════════════════════════════════════════════════════════════════════════════

@admin_chamados_bp.route("/<int:chamado_id>", methods=["GET", "POST"])
@admin_required
def detalhe_chamado_admin(chamado_id: int):
    """
    Tela de chat + painel de gerenciamento para o técnico.

    POST form fields:
        mensagem   — texto da mensagem a enviar.
        novo_status — (opcional) novo status a aplicar junto com a mensagem.
    """
    usuario_id = get_usuario_id()

    with acquire_conn() as conn:
        with conn.cursor() as cur:
            chamado = fetch_one(
                cur,
                _QUERY_CHAMADOS + " WHERE c.id = %s",
                (chamado_id,),
            )
            if not chamado:
                abort(404)

            mensagens = fetch_all(
                cur,
                """
                SELECT cm.id, cm.mensagem, cm.criado_em, cm.is_sistema,
                       u.nome AS autor_nome, u.role AS autor_role, u.id AS autor_id
                FROM chamado_mensagens cm
                JOIN usuarios u ON u.id = cm.usuario_id
                WHERE cm.chamado_id = %s
                ORDER BY cm.criado_em ASC
                """,
                (chamado_id,),
            )

            # Outros admins ativos para transferência
            outros_admins = fetch_all(
                cur,
                """
                SELECT id, nome FROM usuarios
                WHERE role = 'admin' AND ativo = TRUE AND id != %s
                ORDER BY nome ASC
                """,
                (usuario_id,),
            )

            # --- Anexos originais do chamado ---
            anexos_chamado = fetch_all(
                cur,
                """
                SELECT id, nome_arquivo, caminho_arquivo
                FROM chamado_anexos
                WHERE chamado_id = %s AND (mensagem_id IS NULL OR mensagem_id = 0)
                ORDER BY id ASC
                """,
                (chamado_id,)
            )

            # --- Etiquetas ---
            todas_etiquetas = fetch_all(cur, "SELECT id, nome, cor_hex FROM chamado_etiquetas ORDER BY nome ASC")
            etiquetas_vinculadas = fetch_all(
                cur,
                """
                SELECT e.id, e.nome, e.cor_hex
                FROM chamado_etiquetas e
                JOIN chamados_etiquetas_rel rel ON rel.etiqueta_id = e.id
                WHERE rel.chamado_id = %s
                ORDER BY e.nome ASC
                """,
                (chamado_id,)
            )
            ids_vinculados = [et["id"] for et in etiquetas_vinculadas]

    if request.method == "POST":
        mensagem   = (request.form.get("mensagem") or "").strip()
        novo_status = (request.form.get("novo_status") or "").strip()

        if not mensagem:
            flash("A mensagem não pode estar vazia.", "warning")
            return redirect(url_for("admin_chamados.detalhe_chamado_admin", chamado_id=chamado_id))

        with acquire_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO chamado_mensagens (chamado_id, usuario_id, mensagem) VALUES (%s, %s, %s) RETURNING id",
                    (chamado_id, usuario_id, mensagem),
                )
                nova_msg_id = cur.fetchone()["id"]

                arquivo = request.files.get("anexo")
                if arquivo:
                    save_anexo(arquivo, chamado_id, nova_msg_id, usuario_id, cur)

                if novo_status and novo_status in _STATUS_VALIDOS:
                    cur.execute(
                        "UPDATE chamados SET status = %s WHERE id = %s",
                        (novo_status, chamado_id),
                    )

        return redirect(url_for("admin_chamados.detalhe_chamado_admin", chamado_id=chamado_id))

    return render_template(
        "admin/detalhe_chamado_admin.html",
        chamado=chamado,
        mensagens=mensagens,
        anexos_chamado=anexos_chamado,
        outros_admins=outros_admins,
        usuario_id=usuario_id,
        status_validos=sorted(_STATUS_VALIDOS),
        todas_etiquetas=todas_etiquetas,
        etiquetas_chamado=etiquetas_vinculadas,
        ids_vinculados=ids_vinculados,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# GERENCIAR ETIQUETAS DO CHAMADO
# ═══════════════════════════════════════════════════════════════════════════════

@admin_chamados_bp.route("/<int:chamado_id>/etiquetas", methods=["POST"])
@admin_required
def gerenciar_etiquetas_chamado(chamado_id: int):
    """Atualiza as etiquetas associadas ao chamado."""
    novas_etiquetas = request.form.getlist("etiqueta_ids")

    with acquire_conn() as conn:
        with conn.cursor() as cur:
            # Remove antigas
            cur.execute("DELETE FROM chamados_etiquetas_rel WHERE chamado_id = %s", (chamado_id,))
            # Insere novas
            if novas_etiquetas:
                for et_id in novas_etiquetas:
                    if et_id.isdigit():
                        cur.execute(
                            "INSERT INTO chamados_etiquetas_rel (chamado_id, etiqueta_id) VALUES (%s, %s)",
                            (chamado_id, et_id),
                        )

    flash("Etiquetas atualizadas com sucesso.", "success")
    return redirect(url_for("admin_chamados.detalhe_chamado_admin", chamado_id=chamado_id))


# ═══════════════════════════════════════════════════════════════════════════════
# TRANSFERIR CHAMADO PARA OUTRO TÉCNICO
# ═══════════════════════════════════════════════════════════════════════════════

@admin_chamados_bp.route("/<int:chamado_id>/transferir", methods=["POST"])
@admin_required
def transferir_chamado(chamado_id: int):
    """Transfere o chamado para outro técnico e registra mensagem automática."""
    usuario_id      = get_usuario_id()
    novo_tecnico_id = request.form.get("novo_tecnico_id")

    if not novo_tecnico_id:
        flash("Selecione o técnico para transferir.", "warning")
        return redirect(url_for("admin_chamados.detalhe_chamado_admin", chamado_id=chamado_id))

    with acquire_conn() as conn:
        with conn.cursor() as cur:
            tecnico = fetch_one(cur, "SELECT nome FROM usuarios WHERE id = %s AND role = 'admin'", (novo_tecnico_id,))
            if not tecnico:
                abort(400)

            cur.execute(
                "UPDATE chamados SET atribuido_a = %s, status = 'em_atendimento' WHERE id = %s",
                (novo_tecnico_id, chamado_id),
            )
            cur.execute(
                "INSERT INTO chamado_mensagens (chamado_id, usuario_id, mensagem, is_sistema) VALUES (%s, %s, %s, TRUE)",
                (chamado_id, usuario_id, f"Chamado transferido para o técnico {tecnico['nome']}."),
            )

    flash(f"Chamado transferido para {tecnico['nome']}.", "success")
    return redirect(url_for("admin_chamados.detalhe_chamado_admin", chamado_id=chamado_id))


# ═══════════════════════════════════════════════════════════════════════════════
# GERAR MANUTENÇÃO A PARTIR DO CHAMADO
# ═══════════════════════════════════════════════════════════════════════════════

@admin_chamados_bp.route("/<int:chamado_id>/gerar-manutencao", methods=["POST"])
@admin_required
def gerar_manutencao(chamado_id: int):
    """
    Cria um registro de manutenção vinculado ao chamado.

    Requer: chamado deve ter id_ativo preenchido.
    Insere em 'manutencoes' e registra mensagem automática no chat.
    """
    usuario_id = get_usuario_id()

    with acquire_conn() as conn:
        with conn.cursor() as cur:
            chamado = fetch_one(
                cur,
                """
                SELECT c.*, l.nome AS localidade_nome
                FROM chamados c
                JOIN localidades l ON l.id = c.localidade_id
                WHERE c.id = %s
                """,
                (chamado_id,),
            )
            if not chamado:
                abort(404)

            if not chamado.get("id_ativo"):
                flash("Este chamado não possui equipamento vinculado. Vincule um ID de ativo antes de gerar manutenção.", "danger")
                return redirect(url_for("admin_chamados.detalhe_chamado_admin", chamado_id=chamado_id))

            # Verifica se já existe manutenção gerada para este chamado (evita duplicatas)
            existe = fetch_one(
                cur,
                "SELECT id FROM manutencoes WHERE problema_relatado ILIKE %s",
                (f"%chamado #{chamado_id}%",),
            )
            if existe:
                flash("Já existe uma manutenção gerada para este chamado.", "warning")
                return redirect(url_for("admin_chamados.detalhe_chamado_admin", chamado_id=chamado_id))

            cur.execute(
                """
                INSERT INTO manutencoes
                    (id_ativo, tipo_equipamento, problema_relatado, status,
                     local_atual, localidade_id, created_at, updated_at)
                VALUES (%s, 'Equipamento', %s, 'Em Análise', %s, %s, now(), now())
                RETURNING id
                """,
                (
                    chamado["id_ativo"],
                    f"[Chamado #{chamado_id}] {chamado['descricao'][:500]}",
                    chamado["localidade_nome"],
                    chamado["localidade_id"],
                ),
            )
            manutencao_id = cur.fetchone()["id"]

            # Mensagem automática no chat
            cur.execute(
                "INSERT INTO chamado_mensagens (chamado_id, usuario_id, mensagem, is_sistema) VALUES (%s, %s, %s, TRUE)",
                (chamado_id, usuario_id, f"Equipamento {chamado['id_ativo']} encaminhado para manutenção (OS #{manutencao_id}) pela TI."),
            )

    flash(f"Manutenção criada com sucesso (OS #{manutencao_id})!", "success")
    return redirect(url_for("admin_chamados.detalhe_chamado_admin", chamado_id=chamado_id))


# ═══════════════════════════════════════════════════════════════════════════════
# MODELOS PRE-PRONTOS DE CHAMADOS
# ═══════════════════════════════════════════════════════════════════════════════

@admin_chamados_bp.route("/modelos", methods=["GET", "POST"])
@admin_required
def gerenciar_modelos():
    """Gerencia modelos de chamados (criação e listagem)."""
    if request.method == "POST":
        nome_modelo = (request.form.get("nome_modelo") or "").strip()
        titulo_padrao = (request.form.get("titulo_padrao") or "").strip()
        descricao_padrao = (request.form.get("descricao_padrao") or "").strip()
        prioridade_padrao = request.form.get("prioridade_padrao")
        etiqueta_ids = request.form.getlist("etiqueta_ids")

        if not nome_modelo or not titulo_padrao or not descricao_padrao:
            flash("Preencha todos os campos obrigatórios.", "warning")
            return redirect(url_for("admin_chamados.gerenciar_modelos"))

        with acquire_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO chamado_modelos (nome_modelo, titulo_padrao, descricao_padrao, prioridade_padrao)
                    VALUES (%s, %s, %s, %s) RETURNING id
                    """,
                    (nome_modelo, titulo_padrao, descricao_padrao, prioridade_padrao)
                )
                novo_modelo_id = cur.fetchone()["id"]
                
                # Salvar etiquetas vinculadas
                for et_id in etiqueta_ids:
                    if et_id.isdigit():
                        cur.execute(
                            "INSERT INTO chamado_modelos_etiquetas_rel (modelo_id, etiqueta_id) VALUES (%s, %s)",
                            (novo_modelo_id, int(et_id))
                        )

        flash("Modelo de chamado adicionado com sucesso!", "success")
        return redirect(url_for("admin_chamados.gerenciar_modelos"))

    with acquire_conn() as conn:
        with conn.cursor() as cur:
            modelos = fetch_all(cur, "SELECT * FROM chamado_modelos ORDER BY nome_modelo ASC")
            todas_etiquetas = fetch_all(cur, "SELECT id, nome, cor_hex FROM chamado_etiquetas ORDER BY nome ASC")
            
            try:
                # Tentativa de buscar os relacionamentos. Caso a tabela não exista ainda, não quebra a página (ajuda no deploy manual da migration)
                rels = fetch_all(cur, "SELECT modelo_id, etiqueta_id FROM chamado_modelos_etiquetas_rel")
                rels_por_modelo = {}
                for row in rels:
                    rels_por_modelo.setdefault(row['modelo_id'], []).append(row['etiqueta_id'])
                for m in modelos:
                    m['etiquetas'] = rels_por_modelo.get(m['id'], [])
            except Exception:
                # Tabela de relacionamento não foi criada ainda
                conn.rollback()
                for m in modelos:
                    m['etiquetas'] = []

    return render_template(
        "admin/chamados_modelos.html", 
        modelos=modelos, 
        prioridades=_PRIORIDADES,
        todas_etiquetas=todas_etiquetas
    )

@admin_chamados_bp.route("/modelos/<int:modelo_id>/editar", methods=["POST"])
@admin_required
def editar_modelo(modelo_id: int):
    """Edita um modelo de chamado existente e atualiza as etiquetas."""
    nome_modelo = (request.form.get("nome_modelo") or "").strip()
    titulo_padrao = (request.form.get("titulo_padrao") or "").strip()
    descricao_padrao = (request.form.get("descricao_padrao") or "").strip()
    prioridade_padrao = request.form.get("prioridade_padrao")
    etiqueta_ids = request.form.getlist("etiqueta_ids")

    if not nome_modelo or not titulo_padrao or not descricao_padrao:
        flash("Preencha todos os campos obrigatórios.", "warning")
        return redirect(url_for("admin_chamados.gerenciar_modelos"))

    with acquire_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE chamado_modelos 
                SET nome_modelo = %s, titulo_padrao = %s, descricao_padrao = %s, prioridade_padrao = %s
                WHERE id = %s
                """,
                (nome_modelo, titulo_padrao, descricao_padrao, prioridade_padrao, modelo_id)
            )
            
            try:
                # Limpa etiquetas antigas
                cur.execute("DELETE FROM chamado_modelos_etiquetas_rel WHERE modelo_id = %s", (modelo_id,))
                
                # Insere as novas
                for et_id in etiqueta_ids:
                    if et_id.isdigit():
                        cur.execute(
                            "INSERT INTO chamado_modelos_etiquetas_rel (modelo_id, etiqueta_id) VALUES (%s, %s)",
                            (modelo_id, int(et_id))
                        )
            except Exception:
                conn.rollback()
                flash("Modelo editado, mas houve falha ao salvar etiquetas. A tabela de relacionamento existe?", "warning")
                return redirect(url_for("admin_chamados.gerenciar_modelos"))

    flash("Modelo atualizado com sucesso!", "success")
    return redirect(url_for("admin_chamados.gerenciar_modelos"))

@admin_chamados_bp.route("/modelos/<int:modelo_id>/toggle", methods=["POST"])
@admin_required
def toggle_modelo(modelo_id: int):
    """Ativa ou desativa um modelo de chamado."""
    with acquire_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE chamado_modelos SET ativo = NOT ativo WHERE id = %s", (modelo_id,))
    flash("Status do modelo atualizado.", "success")
    return redirect(url_for("admin_chamados.gerenciar_modelos"))


# ═══════════════════════════════════════════════════════════════════════════════
# LER NOTIFICAÇÃO
# ═══════════════════════════════════════════════════════════════════════════════

@admin_chamados_bp.route("/notificacao/<int:notif_id>/ler")
@admin_required
def ler_notificacao(notif_id: int):
    """Marca a notificação como lida e redireciona para o chamado."""
    usuario_id = get_usuario_id()
    with acquire_conn() as conn:
        with conn.cursor() as cur:
            notificacao = fetch_one(
                cur, 
                "SELECT chamado_id FROM notificacoes WHERE id = %s AND usuario_id = %s", 
                (notif_id, usuario_id)
            )
            if notificacao:
                cur.execute(
                    "UPDATE notificacoes SET lida = TRUE WHERE id = %s",
                    (notif_id,)
                )
                return redirect(url_for('admin_chamados.detalhe_chamado_admin', chamado_id=notificacao['chamado_id']))
    
    flash("Notificação não encontrada.", "warning")
    return redirect(url_for('admin_chamados.dashboard_chamados'))
