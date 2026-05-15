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

from auth_utils import admin_required
from db_layer import acquire_conn, fetch_all, fetch_one

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


# ═══════════════════════════════════════════════════════════════════════════════
# LISTAGEM DE USUÁRIOS
# ═══════════════════════════════════════════════════════════════════════════════

@admin_bp.route("/usuarios")
@admin_required
def listar_usuarios():
    """
    Lista todos os usuários do sistema.

    Exibe: nome, login, role, localidade vinculada e status (ativo/inativo).
    Ordenação: admins primeiro, depois viewers por nome.
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
                    u.localidade_id,
                    u.ativo,
                    u.created_at,
                    l.nome AS localidade_nome
                FROM usuarios u
                LEFT JOIN localidades l ON l.id = u.localidade_id
                ORDER BY
                    CASE u.role WHEN 'admin' THEN 0 ELSE 1 END,
                    u.nome ASC
                """,
            )
            localidades = fetch_all(
                cur,
                "SELECT id, nome, tipo FROM localidades ORDER BY nome ASC",
            )

    return render_template("admin/usuarios.html", usuarios=usuarios, localidades=localidades)


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
    # Pré-carrega localidades para o formulário (GET e re-render em erro)
    with acquire_conn() as conn:
        with conn.cursor() as cur:
            localidades = fetch_all(
                cur,
                "SELECT id, nome, tipo FROM localidades ORDER BY nome ASC",
            )

    if request.method == "POST":
        username     = (request.form.get("username") or "").strip().lower()
        nome         = (request.form.get("nome") or "").strip()
        senha        = (request.form.get("senha") or "")
        role         = (request.form.get("role") or "").strip()
        localidade_id_raw = request.form.get("localidade_id") or None

        # ── Validações ────────────────────────────────────────────────────────
        errors: list[str] = []

        if not username:
            errors.append("O campo 'Usuário (login)' é obrigatório.")
        if not nome:
            errors.append("O campo 'Nome' é obrigatório.")
        if len(senha) < 6:
            errors.append("A senha deve ter no mínimo 6 caracteres.")
        if role not in ("admin", "viewer", "apoio"):
            errors.append("Role inválido.")
        if role == "viewer" and not localidade_id_raw:
            errors.append("Viewers devem ter uma localidade vinculada.")

        if errors:
            for msg in errors:
                flash(msg, "warning")
            return render_template(
                "admin/novo_usuario.html",
                localidades=localidades,
                form=request.form,
            )

        # Força localidade_id = NULL para admins e apoio
        localidade_id = None if role in ("admin", "apoio") else int(localidade_id_raw)

        # ── Hash da senha (werkzeug — pbkdf2:sha256 por padrão) ──────────────
        senha_hash = generate_password_hash(senha)

        try:
            with acquire_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO usuarios (nome, login, senha_hash, role, localidade_id)
                        VALUES (%s, %s, %s, %s, %s)
                        """,
                        (nome, username, senha_hash, role, localidade_id),
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
                form=request.form,
            )

    # GET — exibe formulário limpo
    return render_template(
        "admin/novo_usuario.html",
        localidades=localidades,
        form={},
    )


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

    role = (request.form.get("role") or "").strip()
    localidade_id_raw = request.form.get("localidade_id") or None

    if role not in ("admin", "viewer", "apoio"):
        flash("Perfil de acesso inválido.", "danger")
        return redirect(url_for("admin.listar_usuarios"))

    if role == "viewer" and not localidade_id_raw:
        flash("Viewers devem ter uma localidade vinculada.", "danger")
        return redirect(url_for("admin.listar_usuarios"))

    localidade_id = None if role in ("admin", "apoio") else int(localidade_id_raw)

    with acquire_conn() as conn:
        with conn.cursor() as cur:
            usuario = fetch_one(cur, "SELECT login FROM usuarios WHERE id = %s", (usuario_id,))
            if not usuario:
                abort(404)

            cur.execute(
                """
                UPDATE usuarios 
                SET role = %s, localidade_id = %s 
                WHERE id = %s
                """,
                (role, localidade_id, usuario_id),
            )

    flash(f"Perfil do usuário '{usuario['login']}' atualizado com sucesso.", "success")
    return redirect(url_for("admin.listar_usuarios"))
