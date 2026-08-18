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

def is_admin_user() -> bool:
    """
    Retorna True se o usuário logado possui privilégios de administrador:
    - session['is_admin_master'] == True
    - session['role'] (case-insensitive) == 'admin'
    - permissão 'acesso_total' ou 'gerenciar_pedidos' no RBAC
    """
    if session.get("is_admin_master"):
        return True
    role = (session.get("role") or "").strip().lower()
    if role == "admin":
        return True
    permissoes = session.get("permissoes") or {}
    if isinstance(permissoes, dict) and (permissoes.get("acesso_total") or permissoes.get("gerenciar_pedidos")):
        return True
    return False


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
    if is_admin_user():
        return None
    return session.get("localidade_id")

def get_fazenda_nome_filter() -> Optional[str]:
    """
    Retorna o nome da fazenda correspondente à localidade do viewer.
    """
    if is_admin_user():
        return None
    
    # Se já foi cacheado no login (melhor performance)
    if "fazenda_nome" in session:
        return session["fazenda_nome"]
        
    return None


def get_usuario_id() -> Optional[int]:
    """
    Retorna o ID do usuário logado a partir da sessão Flask.
    """
    return session.get("usuario_id")


def get_role() -> Optional[str]:
    """
    Retorna a role ('admin', 'viewer', 'apoio') do usuário logado.
    """
    role = session.get("role")
    return role.lower() if role else None

def has_permission(perm_name: str) -> bool:
    """
    Verifica se o usuário logado possui uma permissão específica.
    """
    # Administradores têm acesso total irrestrito
    if is_admin_user():
        return True
    
    permissoes = session.get("permissoes") or {}
    if isinstance(permissoes, dict):
        return bool(permissoes.get(perm_name))
    return False


# ── Decorators de acesso ──────────────────────────────────────────────────────

def login_required(f):
    """
    Exige que o usuário esteja autenticado.
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        if "usuario_id" not in session:
            return redirect(url_for("auth.login"))
        return f(*args, **kwargs)
    return decorated


def viewer_required(f):
    """
    Exige autenticação E role 'viewer' ou privilégio admin.
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        if "usuario_id" not in session:
            return redirect(url_for("auth.login"))
        role = (session.get("role") or "").strip().lower()
        if not (is_admin_user() or role in ("viewer", "apoio")):
            abort(403)
        return f(*args, **kwargs)
    return decorated


def admin_required(f):
    """
    Exige autenticação E privilégios de administrador (is_admin_user).
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        if "usuario_id" not in session:
            return redirect(url_for("auth.login"))
        if not is_admin_user():
            abort(403)
        return f(*args, **kwargs)
    return decorated

def permission_required(perm_name: str):
    """
    Decorator que exige uma permissão granular específica.
    """
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if "usuario_id" not in session:
                return redirect(url_for("auth.login"))
            if not has_permission(perm_name):
                abort(403)
            return f(*args, **kwargs)
        return decorated
    return decorator
