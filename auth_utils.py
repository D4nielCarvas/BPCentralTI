"""
auth_utils.py - Utilitarios de autenticacao e controle de acesso multi-tenant.

Padrao: Decorator (AOP) + sessao Flask.
Complexidade: O(1) - todas as verificacoes sao leituras de sessao em memoria.

Seguranca:
    - Nunca confie no localidade_id vindo do corpo da requisicao.
      Use sempre get_localidade_filter() para obter o valor da sessao.
    - Senhas armazenadas com werkzeug.security.generate_password_hash (pbkdf2:sha256).
    - Risco de IDOR: validar sempre que o pedido_id pertence ao usuario_id
      da sessao antes de exibir (feito nas rotas do blueprint fazenda.py).
"""

from __future__ import annotations

from functools import wraps
from typing import Optional

from flask import abort, redirect, session, url_for


# ── Filtro de localidade ──────────────────────────────────────────────────────

def get_localidade_filter() -> Optional[int]:
    """
    Retorna localidade_id se o usuário logado for viewer, ou None se for admin.

    Uso nas queries para filtrar dados por localidade:
        localidade_id = get_localidade_filter()
        if localidade_id:
            query += " AND localidade_id = %s"
            params.append(localidade_id)

    Returns:
        int  — ID da localidade do viewer (restringe a query).
        None — Usuário é admin; nenhum filtro aplicado.
    """
    if session.get("role") == "viewer":
        return session.get("localidade_id")
    return None


def get_usuario_id() -> Optional[int]:
    """
    Retorna o ID do usuário logado a partir da sessão Flask.

    Returns:
        int ou None se não houver sessão ativa.
    """
    return session.get("usuario_id")


def get_role() -> Optional[str]:
    """
    Retorna a role ('admin' ou 'viewer') do usuário logado.

    Returns:
        str ou None se não houver sessão ativa.
    """
    return session.get("role")


# ── Decorators de acesso ──────────────────────────────────────────────────────

def login_required(f):
    """
    Exige que o usuário esteja autenticado.

    Redireciona para a rota de login se não houver sessão ativa.
    Aplica-se a qualquer rota (admin ou viewer).
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        if "usuario_id" not in session:
            return redirect(url_for("auth.login"))
        return f(*args, **kwargs)
    return decorated


def viewer_required(f):
    """
    Exige que o usuário esteja autenticado (viewer ou admin).

    Viewers e admins podem acessar as rotas decoradas com este decorator.
    Redireciona para login se não houver sessão.
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        if "usuario_id" not in session:
            return redirect(url_for("auth.login"))
        return f(*args, **kwargs)
    return decorated


def admin_required(f):
    """
    Exige autenticação E role == 'admin'.

    Retorna 403 Forbidden se o usuário estiver logado mas não for admin.
    Redireciona para login se não houver sessão.

    Risco de segurança: Garanta que 'role' na sessão só é gravado
    no momento do login a partir do banco de dados — nunca a partir
    de input do usuário (evita privilege escalation).
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        if "usuario_id" not in session:
            return redirect(url_for("auth.login"))
        if session.get("role") != "admin":
            abort(403)
        return f(*args, **kwargs)
    return decorated
