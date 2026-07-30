"""
blueprints/admin.py — Gestão de usuários do sistema (apenas admins).

Rotas protegidas pelo decorator @admin_required.
Usa werkzeug.security.generate_password_hash para armazenar senhas com segurança.

Segurança:
    - admin_required retorna 403 para qualquer role != 'admin'.
    - localidade_id forçado para NULL quando role == 'admin' (sem exceção).
    - Senha nunca armazenada em texto plano — hash pbkdf2:sha256.

Risco de segurança a monitorar:
    - Username duplicado: tratado com try/except na inserção (UNIQUE constraint).
    - Senha mínima: validada no backend (mínimo 6 caracteres).
"""

from __future__ import annotations

from werkzeug.security import generate_password_hash
from flask import Blueprint, abort, flash, redirect, render_template, request, url_for

from utils.auth_utils import admin_required
from utils.db_layer import acquire_conn, fetch_all, fetch_one

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


# ═══════════════════════════════════════════════════════════════════════════════
# LISTAGEM DE USUÁRIOS
# ═══════════════════════════════════════════════════════════════════════════════

@admin_bp.route("/usuarios")
@admin_required
def listar_usuarios():
    """
    Lista todos os usuários do sistema com seus perfis dinâmicos.
    """
    with acquire_conn() as conn:
        with conn.cursor() as cur:
            usuarios = fetch_all(
                cur,
                """
                SELECT
                    u.id,
                    u.nome,
                    u.login,
                    u.role,
                    u.perfil_id,
                    p.nome AS perfil_nome,
                    p.is_admin_master,
                    u.localidade_id,
                    u.ativo,
                    u.created_at,
                    l.nome AS localidade_nome
                FROM usuarios u
                LEFT JOIN localidades l ON l.id = u.localidade_id
                LEFT JOIN perfis_acesso p ON p.id = u.perfil_id
                ORDER BY
                    p.is_admin_master DESC NULLS LAST,
                    u.nome ASC
                """,
            )
            localidades = fetch_all(
                cur,
                "SELECT id, nome, tipo FROM localidades ORDER BY nome ASC",
            )
            perfis = fetch_all(
                cur,
                "SELECT id, nome, is_admin_master FROM perfis_acesso ORDER BY nome ASC",
            )

    return render_template("admin/usuarios.html", usuarios=usuarios, localidades=localidades, perfis=perfis)


# ═══════════════════════════════════════════════════════════════════════════════
# CRIAÇÃO DE USUÁRIO
# ═══════════════════════════════════════════════════════════════════════════════

@admin_bp.route("/usuarios/novo", methods=["GET", "POST"])
@admin_required
def novo_usuario():
    """
    Formulário para criar novo usuário (GET) e processar inserção (POST).

    POST form fields:
        username     — login único (case-insensitive, salvo em lowercase).
        nome         — nome de exibição.
        senha        — senha em texto plano (mínimo 6 chars); armazenada como hash.
        role         — 'admin' ou 'viewer'.
        localidade_id — obrigatório se role == 'viewer'; forçado NULL se role == 'admin'.

    Regras de negócio:
        - role == 'admin' → localidade_id = NULL (sem exceção).
        - role == 'viewer' sem localidade_id → erro de validação.
        - Username duplicado → erro amigável (não expõe stack trace).
    """
    # Pré-carrega localidades e perfis para o formulário
    with acquire_conn() as conn:
        with conn.cursor() as cur:
            localidades = fetch_all(
                cur,
                "SELECT id, nome, tipo FROM localidades ORDER BY nome ASC",
            )
            perfis = fetch_all(
                cur,
                "SELECT id, nome, is_admin_master FROM perfis_acesso ORDER BY nome ASC",
            )

    if request.method == "POST":
        username     = (request.form.get("username") or "").strip().lower()
        nome         = (request.form.get("nome") or "").strip()
        senha        = (request.form.get("senha") or "")
        perfil_id_raw = request.form.get("perfil_id") or None
        localidade_id_raw = request.form.get("localidade_id") or None

        # ── Validações ────────────────────────────────────────────────────────
        errors: list[str] = []

        if not username:
            errors.append("O campo 'Usuário (login)' é obrigatório.")
        if not nome:
            errors.append("O campo 'Nome' é obrigatório.")
        if len(senha) < 6:
            errors.append("A senha deve ter no mínimo 6 caracteres.")
        if not perfil_id_raw:
            errors.append("Selecione um perfil de acesso.")
            
        perfil_id = int(perfil_id_raw) if perfil_id_raw else None

        if errors:
            for msg in errors:
                flash(msg, "warning")
            return render_template(
                "admin/novo_usuario.html",
                localidades=localidades,
                perfis=perfis,
                form=request.form,
            )

        # Regra simplificada: Admin Master ignora localidade. Outros perfis podem ter localidade
        is_admin_master = False
        for p in perfis:
            if p["id"] == perfil_id and p["is_admin_master"]:
                is_admin_master = True
                
        localidade_id = None if is_admin_master else (int(localidade_id_raw) if localidade_id_raw else None)
        
        # Mantém role como viewer por padrão para compatibilidade
        role = "admin" if is_admin_master else "viewer"

        # ── Hash da senha (werkzeug — pbkdf2:sha256 por padrão) ──────────────
        senha_hash = generate_password_hash(senha)

        try:
            with acquire_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO usuarios (nome, login, senha_hash, role, perfil_id, localidade_id)
                        VALUES (%s, %s, %s, %s, %s, %s)
                        """,
                        (nome, username, senha_hash, role, perfil_id, localidade_id),
                    )

            flash(f"Usuário '{username}' criado com sucesso!", "success")
            return redirect(url_for("admin.listar_usuarios"))

        except Exception as exc:
            # UNIQUE violation ou outro erro de banco
            if "unique" in str(exc).lower() or "duplicat" in str(exc).lower():
                flash(f"O login '{username}' já está em uso. Escolha outro.", "danger")
            else:
                flash(f"Erro ao criar usuário: {exc}", "danger")

            return render_template(
                "admin/novo_usuario.html",
                localidades=localidades,
                perfis=perfis,
                form=request.form,
            )

    # GET — exibe formulário limpo
    return render_template(
        "admin/novo_usuario.html",
        localidades=localidades,
        perfis=perfis,
        form={},
    )


# ═══════════════════════════════════════════════════════════════════════════════
# GERENCIAMENTO DE PERFIS DE ACESSO (RBAC)
# ═══════════════════════════════════════════════════════════════════════════════

# Mapa de todas as permissões disponíveis no sistema, agrupadas por categoria.
# Cada entrada: (chave_json, rótulo_exibido)
PERMISSOES_SISTEMA = {
    "Dados dos Membros": [
        ("ver_telefones",         "Ver números de telefone"),
        ("ver_email_membros",     "Ver e-mail dos membros"),
    ],
    "Equipamentos": [
        ("ver_equipamentos",      "Visualizar equipamentos"),
        ("ver_celulares_ponto",   "Visualizar Celulares Ponto"),
        ("ver_celulares_turma",   "Visualizar Celulares Turma"),
        ("ver_celulares_inspecao", "Visualizar Celulares Inspeção"),
        ("exportar_equipamentos", "Exportar listagem de equipamentos"),
        ("editar_equipamentos",   "Editar dados dos equipamentos"),
    ],
    "Termos de Responsabilidade": [
        ("ver_termos",            "Visualizar termos assinados"),
        ("anexar_termos",         "Anexar / assinar termos"),
        ("excluir_termos",        "Excluir termos"),
        ("gerar_termos",          "Gerar Termos em PDF"),
    ],
    "Chamados de TI": [
        ("abrir_chamados",        "Abrir chamados"),
        ("responder_chamados",    "Responder chamados"),
        ("fechar_chamados",       "Fechar chamados"),
        ("ver_chamados_outros",   "Ver chamados de outros usuários"),
    ],
    "Relatórios": [
        ("ver_relatorios",        "Ver relatórios globais"),
        ("exportar_relatorios",   "Exportar relatórios"),
    ],
}


@admin_bp.route("/perfis")
@admin_required
def listar_perfis():
    """Lista todos os perfis de acesso cadastrados."""
    with acquire_conn() as conn:
        with conn.cursor() as cur:
            perfis = fetch_all(
                cur,
                """
                SELECT p.id, p.nome, p.is_admin_master, p.permissoes, p.criado_em,
                       COUNT(u.id) AS total_usuarios
                FROM perfis_acesso p
                LEFT JOIN usuarios u ON u.perfil_id = p.id
                GROUP BY p.id
                ORDER BY p.is_admin_master DESC, p.nome ASC
                """,
            )
    return render_template("admin/perfis.html", perfis=perfis, permissoes_sistema=PERMISSOES_SISTEMA)


@admin_bp.route("/perfis/novo", methods=["GET", "POST"])
@admin_required
def novo_perfil():
    """Cria um novo perfil de acesso com permissões granulares."""
    if request.method == "POST":
        import json
        nome = (request.form.get("nome") or "").strip()
        is_admin_master = request.form.get("is_admin_master") == "1"

        if not nome:
            flash("O nome do perfil é obrigatório.", "warning")
            return render_template("admin/perfis.html", perfis=[], permissoes_sistema=PERMISSOES_SISTEMA)

        # Coleta permissões do formulário (checkboxes)
        permissoes = {}
        for grupo, perms in PERMISSOES_SISTEMA.items():
            for chave, _ in perms:
                permissoes[chave] = (request.form.get(f"perm_{chave}") == "1")

        try:
            with acquire_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "INSERT INTO perfis_acesso (nome, is_admin_master, permissoes) VALUES (%s, %s, %s)",
                        (nome, is_admin_master, json.dumps(permissoes)),
                    )
            flash(f"Perfil '{nome}' criado com sucesso!", "success")
        except Exception as exc:
            if "unique" in str(exc).lower():
                flash(f"Já existe um perfil com o nome '{nome}'.", "danger")
            else:
                flash(f"Erro ao criar perfil: {exc}", "danger")

        return redirect(url_for("admin.listar_perfis"))

    return redirect(url_for("admin.listar_perfis"))


@admin_bp.route("/perfis/<int:perfil_id>/editar", methods=["POST"])
@admin_required
def editar_perfil(perfil_id: int):
    """Atualiza nome e permissões de um perfil existente."""
    import json
    nome = (request.form.get("nome") or "").strip()
    is_admin_master = request.form.get("is_admin_master") == "1"

    if not nome:
        flash("O nome do perfil é obrigatório.", "warning")
        return redirect(url_for("admin.listar_perfis"))

    permissoes = {}
    for grupo, perms in PERMISSOES_SISTEMA.items():
        for chave, _ in perms:
            permissoes[chave] = (request.form.get(f"perm_{chave}") == "1")

    with acquire_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE perfis_acesso SET nome=%s, is_admin_master=%s, permissoes=%s, atualizado_em=NOW() WHERE id=%s",
                (nome, is_admin_master, json.dumps(permissoes), perfil_id),
            )

    flash(f"Perfil '{nome}' atualizado com sucesso!", "success")
    return redirect(url_for("admin.listar_perfis"))


@admin_bp.route("/perfis/<int:perfil_id>/excluir", methods=["POST"])
@admin_required
def excluir_perfil(perfil_id: int):
    """Remove um perfil. Não permite excluir se houver usuários vinculados."""
    with acquire_conn() as conn:
        with conn.cursor() as cur:
            total = fetch_one(cur, "SELECT COUNT(*) as c FROM usuarios WHERE perfil_id = %s", (perfil_id,))
            if total and total["c"] > 0:
                flash(f"Não é possível excluir: {total['c']} usuário(s) usam este perfil.", "danger")
                return redirect(url_for("admin.listar_perfis"))
            perfil = fetch_one(cur, "SELECT nome FROM perfis_acesso WHERE id = %s", (perfil_id,))
            if not perfil:
                abort(404)
            cur.execute("DELETE FROM perfis_acesso WHERE id = %s", (perfil_id,))

    flash(f"Perfil '{perfil['nome']}' excluído.", "success")
    return redirect(url_for("admin.listar_perfis"))


# ═══════════════════════════════════════════════════════════════════════════════
# TOGGLE ATIVO/INATIVO
# ═══════════════════════════════════════════════════════════════════════════════

@admin_bp.route("/usuarios/<int:usuario_id>/toggle-ativo", methods=["POST"])
@admin_required
def toggle_ativo_usuario(usuario_id: int):
    """Ativa ou desativa um usuario. Admin nao pode desativar a si mesmo."""
    from flask import session as flask_session
    if usuario_id == flask_session.get("usuario_id"):
        flash("Voce nao pode desativar sua propria conta.", "danger")
        return redirect(url_for("admin.listar_usuarios"))

    with acquire_conn() as conn:
        with conn.cursor() as cur:
            usuario = fetch_one(cur, "SELECT ativo, login FROM usuarios WHERE id = %s", (usuario_id,))
            if not usuario:
                abort(404)

            novo_estado = not usuario["ativo"]
            cur.execute(
                "UPDATE usuarios SET ativo = %s WHERE id = %s",
                (novo_estado, usuario_id),
            )

    estado_str = "ativado" if novo_estado else "desativado"
    flash(f"Usuario '{usuario['login']}' {estado_str}.", "success")
    return redirect(url_for("admin.listar_usuarios"))


# ═══════════════════════════════════════════════════════════════════════════════
# RESET DE SENHA PELO ADMIN
# ═══════════════════════════════════════════════════════════════════════════════

@admin_bp.route("/usuarios/<int:usuario_id>/resetar-senha", methods=["POST"])
@admin_required
def resetar_senha_usuario(usuario_id: int):
    """
    Admin redefine a senha de qualquer usuario sem precisar do token de e-mail.

    POST form fields:
        nova_senha — nova senha em texto plano (minimo 6 chars).
    """
    nova_senha = (request.form.get("nova_senha") or "").strip()

    if len(nova_senha) < 6:
        flash("A senha deve ter no minimo 6 caracteres.", "warning")
        return redirect(url_for("admin.listar_usuarios"))

    with acquire_conn() as conn:
        with conn.cursor() as cur:
            usuario = fetch_one(cur, "SELECT login FROM usuarios WHERE id = %s", (usuario_id,))
            if not usuario:
                abort(404)

            novo_hash = generate_password_hash(nova_senha)
            cur.execute(
                "UPDATE usuarios SET senha_hash = %s WHERE id = %s",
                (novo_hash, usuario_id),
            )

    flash(f"Senha do usuario '{usuario['login']}' redefinida com sucesso.", "success")
    return redirect(url_for("admin.listar_usuarios"))


# ═══════════════════════════════════════════════════════════════════════════════
# EDITAR USUÁRIO (ROLE/LOCALIDADE)
# ═══════════════════════════════════════════════════════════════════════════════

@admin_bp.route("/usuarios/<int:usuario_id>/editar", methods=["POST"])
@admin_required
def editar_usuario(usuario_id: int):
    """Admin altera o role e/ou localidade de um usuário."""
    from flask import session as flask_session
    if usuario_id == flask_session.get("usuario_id"):
        flash("Você não pode editar o seu próprio perfil de acesso por aqui.", "danger")
        return redirect(url_for("admin.listar_usuarios"))

    perfil_id_raw = request.form.get("perfil_id") or None
    localidade_id_raw = request.form.get("localidade_id") or None

    if not perfil_id_raw:
        flash("Perfil de acesso inválido.", "danger")
        return redirect(url_for("admin.listar_usuarios"))
        
    perfil_id = int(perfil_id_raw)

    with acquire_conn() as conn:
        with conn.cursor() as cur:
            # Pega infos do perfil selecionado para definir se é admin master
            perfil = fetch_one(cur, "SELECT is_admin_master FROM perfis_acesso WHERE id = %s", (perfil_id,))
            if not perfil:
                flash("Perfil de acesso inválido.", "danger")
                return redirect(url_for("admin.listar_usuarios"))
                
            localidade_id = None if perfil["is_admin_master"] else (int(localidade_id_raw) if localidade_id_raw else None)
            role = "admin" if perfil["is_admin_master"] else "viewer"

            usuario = fetch_one(cur, "SELECT login FROM usuarios WHERE id = %s", (usuario_id,))
            if not usuario:
                abort(404)

            cur.execute(
                """
                UPDATE usuarios 
                SET role = %s, perfil_id = %s, localidade_id = %s 
                WHERE id = %s
                """,
                (role, perfil_id, localidade_id, usuario_id),
            )

    flash(f"Perfil do usuário '{usuario['login']}' atualizado com sucesso.", "success")
    return redirect(url_for("admin.listar_usuarios"))
