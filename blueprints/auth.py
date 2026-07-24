"""
blueprints/auth.py — Blueprint de autenticacao completo.

Rotas:
    GET/POST /login              — Login com email ou username
    GET/POST /cadastro           — Auto-cadastro (role sempre 'viewer')
    GET/POST /recuperar-senha    — Solicita link de recuperacao por e-mail
    GET/POST /resetar-senha/<t>  — Redefine senha via token valido
    GET      /logout             — Encerra sessao

Seguranca:
    - Senhas: werkzeug.security.generate/check_password_hash (pbkdf2:sha256).
    - Tokens: secrets.token_urlsafe(32) — 256 bits de entropia.
    - Tokens expiram em 1 hora e sao marcados como usado=TRUE apos uso.
    - Session fixation: session.clear() antes de gravar nova sessao.
    - SMTP: credenciais apenas via os.environ — nunca hardcoded.

Risco a monitorar:
    - Rate-limit no /recuperar-senha (nao implementado aqui — usar Nginx/WAF).
    - Emails com texto puro incluidos como fallback para clientes sem HTML.
"""

from __future__ import annotations

import os
import secrets
import smtplib
from datetime import datetime, timedelta, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from flask import (Blueprint, flash, redirect, render_template,
                   request, session, url_for)
from werkzeug.security import check_password_hash, generate_password_hash
from flask_limiter.util import get_remote_address
from app import limiter

from utils.db_layer import acquire_conn, fetch_all, fetch_one

auth_bp = Blueprint("auth", __name__)


# Handler para erro 429 Too Many Requests (Brute Force/Abuso)
@auth_bp.errorhandler(429)
def ratelimit_handler(e):
    flash("Muitas tentativas de acesso. Por favor, aguarde alguns instantes antes de tentar novamente.", "warning")
    return redirect(url_for("auth.login"))

# ── Utilitario de e-mail ──────────────────────────────────────────────────────

def enviar_email_recuperacao(email_destino: str, token: str, base_url: str = "") -> bool:
    """
    Envia e-mail com link de recuperacao de senha via SMTP (Zoho/Outlook).

    Variaveis de ambiente necessarias:
        SMTP_HOST     — servidor SMTP (ex: smtp.zoho.com)
        SMTP_PORT     — porta (587 para STARTTLS)
        SMTP_USER     — usuario/remetente (ex: ti@empresa.com.br)
        SMTP_PASSWORD — senha do remetente

    O parametro base_url e preenchido automaticamente pela rota
    via request.host_url — nao e necessario configurar no .env.

    Retorna True em sucesso, False em falha (nao lanca excecao).
    """
    smtp_host = os.environ.get("SMTP_HOST", "")
    smtp_port = int(os.environ.get("SMTP_PORT", "587"))
    smtp_user = os.environ.get("SMTP_USER", "")
    smtp_pass = os.environ.get("SMTP_PASSWORD", "")

    # base_url vem do request.host_url injetado pela rota (ex: http://192.168.1.5:5000/)
    # Remove barra final para montar o link corretamente
    base_url = (base_url or "http://localhost:5000").rstrip("/")

    if not all([smtp_host, smtp_user, smtp_pass]):
        # SMTP nao configurado — loga mas nao quebra o fluxo
        print(f"[AUTH] SMTP nao configurado. Token para {email_destino}: {token}")
        return False

    link = f"{base_url}/resetar-senha/{token}"

    # Corpo HTML
    html = f"""
    <html><body style="font-family:Arial,sans-serif;background:#0d0f14;color:#e2e8f0;padding:30px">
      <div style="max-width:480px;margin:auto;background:#13161e;border-radius:12px;padding:30px;border:1px solid #252b3b">
        <h2 style="color:#3b82f6;margin-top:0">Recuperacao de Senha</h2>
        <p>Recebemos uma solicitacao de recuperacao de senha para sua conta no <strong>BP Central TI</strong>.</p>
        <p>Clique no botao abaixo para redefinir sua senha. O link expira em <strong>1 hora</strong>.</p>
        <div style="text-align:center;margin:24px 0">
          <a href="{link}" style="background:#3b82f6;color:#fff;padding:12px 28px;border-radius:8px;text-decoration:none;font-weight:600">
            Redefinir Senha
          </a>
        </div>
        <p style="font-size:12px;color:#475569">Se voce nao solicitou isso, ignore este e-mail.</p>
        <hr style="border-color:#252b3b;margin:20px 0">
        <p style="font-size:11px;color:#475569">Link direto: {link}</p>
      </div>
    </body></html>
    """

    # Corpo texto puro (fallback)
    texto = f"Recuperacao de Senha - BP Central TI\n\nLink: {link}\n\nExpira em 1 hora."

    msg = MIMEMultipart("alternative")
    msg["Subject"] = "Recuperacao de Senha — BP Central TI"
    msg["From"]    = smtp_user
    msg["To"]      = email_destino
    msg.attach(MIMEText(texto, "plain", "utf-8"))
    msg.attach(MIMEText(html,  "html",  "utf-8"))

    try:
        # Porta 465 = SSL direto; porta 587 = STARTTLS
        if smtp_port == 465:
            with smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=10) as server:
                server.login(smtp_user, smtp_pass)
                server.sendmail(smtp_user, [email_destino], msg.as_string())
        else:
            with smtplib.SMTP(smtp_host, smtp_port, timeout=10) as server:
                server.ehlo()
                server.starttls()
                server.login(smtp_user, smtp_pass)
                server.sendmail(smtp_user, [email_destino], msg.as_string())
        return True
    except Exception as exc:
        print(f"[AUTH] Falha ao enviar e-mail para {email_destino}: {exc}")
        return False


# ═══════════════════════════════════════════════════════════════════════════════
# LOGIN
# ═══════════════════════════════════════════════════════════════════════════════

@auth_bp.route("/login", methods=["GET", "POST"])
@limiter.limit("10 per minute")
def login():
    """
    GET  — Renderiza formulario de login.
    POST — Valida email (ou username) + senha e cria sessao Flask.

    Redireciona:
        admin  -> / (painel principal)
        viewer -> /fazenda/itens
    """
    if "usuario_id" in session:
        return redirect(url_for("core.index"))

    if request.method == "POST":
        login_input = (request.form.get("email") or "").strip().lower()
        senha_input = (request.form.get("senha") or "")

        if not login_input or not senha_input:
            flash("Preencha todos os campos.", "warning")
            return render_template("auth/login.html")

        with acquire_conn() as conn:
            with conn.cursor() as cur:
                # Aceita tanto email quanto username no mesmo campo
                usuario = fetch_one(
                    cur,
                    """
                    SELECT u.id, u.nome, u.login, u.senha_hash, u.role, u.localidade_id, u.ativo,
                           p.is_admin_master, p.permissoes, l.nome AS fazenda_nome
                    FROM usuarios u
                    LEFT JOIN perfis_acesso p ON u.perfil_id = p.id
                    LEFT JOIN localidades l ON u.localidade_id = l.id
                    WHERE u.login = %s OR u.email = %s
                    """,
                    (login_input, login_input),
                )

        _DUMMY_HASH = generate_password_hash("__dummy_timing_protection__")
        senha_hash = usuario["senha_hash"] if usuario else _DUMMY_HASH
        senha_ok = check_password_hash(senha_hash, senha_input)

        if not usuario or not senha_ok:
            flash("E-mail/usuario ou senha invalidos.", "danger")
            return render_template("auth/login.html")

        if not usuario["ativo"]:
            flash("Sua conta esta desativada. Contate o administrador.", "danger")
            return render_template("auth/login.html")

        session.clear()
        session["usuario_id"]    = usuario["id"]
        session["usuario_nome"]  = usuario["nome"]
        session["role"]          = usuario["role"]
        session["localidade_id"] = usuario["localidade_id"]
        if usuario.get("fazenda_nome"):
            session["fazenda_nome"] = usuario["fazenda_nome"]
        
        # Carregar as permissões e a flag de super_admin
        session["is_admin_master"] = usuario.get("is_admin_master", False)
        # Se for admin master ou a role legada for admin, carrega tudo ou define o acesso via utils depois
        import json
        permissoes_json = usuario.get("permissoes") or '{}'
        if isinstance(permissoes_json, str):
            try:
                session["permissoes"] = json.loads(permissoes_json)
            except:
                session["permissoes"] = {}
        else:
            session["permissoes"] = permissoes_json
            
        session.permanent = True

        if usuario["role"] == "viewer":
            return redirect(url_for("fazenda.listar_itens"))
        if usuario["role"] == "apoio":
            return redirect(url_for("apoio.celulares_inspecao"))
        return redirect(url_for("core.index"))

    return render_template("auth/login.html")


# ═══════════════════════════════════════════════════════════════════════════════
# CADASTRO (auto-cadastro — sempre viewer)
# ═══════════════════════════════════════════════════════════════════════════════

@auth_bp.route("/cadastro", methods=["GET", "POST"])
def cadastro():
    """
    GET  — Renderiza formulario de cadastro com lista de localidades ativas.
    POST — Cria usuario com role='viewer' e localidade vinculada.

    Regra de negocio: todo auto-cadastro e viewer.
    Admins sao criados exclusivamente por /admin/usuarios/novo.
    """
    with acquire_conn() as conn:
        with conn.cursor() as cur:
            localidades = fetch_all(
                cur, "SELECT id, nome, tipo FROM localidades ORDER BY nome ASC"
            )

    if request.method == "POST":
        nome     = (request.form.get("nome") or "").strip()
        username = (request.form.get("username") or "").strip().lower()
        email    = (request.form.get("email") or "").strip().lower()
        senha    = (request.form.get("senha") or "")
        loc_id   = request.form.get("localidade_id") or None

        errors: list[str] = []
        if not nome:              errors.append("Nome e obrigatorio.")
        if not username:          errors.append("Usuario e obrigatorio.")
        if not email or "@" not in email: errors.append("E-mail invalido.")
        if len(senha) < 6:        errors.append("Senha deve ter no minimo 6 caracteres.")
        if not loc_id:            errors.append("Selecione a sua fazenda/localidade.")

        if errors:
            for e in errors:
                flash(e, "warning")
            return render_template("auth/cadastro.html", localidades=localidades, form=request.form)

        senha_hash = generate_password_hash(senha)

        try:
            with acquire_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO usuarios (nome, login, email, senha_hash, role, localidade_id, ativo)
                        VALUES (%s, %s, %s, %s, 'viewer', %s, TRUE)
                        """,
                        (nome, username, email, senha_hash, int(loc_id)),
                    )

            flash("Conta criada com sucesso! Faca o login.", "success")
            return redirect(url_for("auth.login"))

        except Exception as exc:
            err = str(exc).lower()
            if "unique" in err or "duplicat" in err:
                if "login" in err or "usuarios_login" in err:
                    flash(f"O usuario '{username}' ja esta em uso.", "danger")
                elif "email" in err:
                    flash(f"O e-mail '{email}' ja esta cadastrado.", "danger")
                else:
                    flash("Usuario ou e-mail ja cadastrados.", "danger")
            else:
                flash(f"Erro ao criar conta: {exc}", "danger")

            return render_template("auth/cadastro.html", localidades=localidades, form=request.form)

    return render_template("auth/cadastro.html", localidades=localidades, form={})


# ═══════════════════════════════════════════════════════════════════════════════
# RECUPERACAO DE SENHA — solicitar link
# ═══════════════════════════════════════════════════════════════════════════════

@auth_bp.route("/recuperar-senha", methods=["GET", "POST"])
@limiter.limit("5 per hour", key_func=lambda: request.form.get("email", get_remote_address()))
def recuperar_senha():
    """
    GET  — Formulario pedindo apenas o e-mail.
    POST — Gera token seguro e envia e-mail com link de recuperacao.

    Seguranca: retorna sempre a mesma mensagem neutra,
    independente de o e-mail existir ou nao (evita user enumeration).
    """
    if request.method == "POST":
        email_input = (request.form.get("email") or "").strip().lower()

        if not email_input or "@" not in email_input:
            flash("Informe um e-mail valido.", "warning")
            return render_template("auth/recuperar_senha.html")

        with acquire_conn() as conn:
            with conn.cursor() as cur:
                usuario = fetch_one(
                    cur,
                    "SELECT id, email FROM usuarios WHERE email = %s AND ativo = TRUE",
                    (email_input,),
                )

                if usuario:
                    token = secrets.token_urlsafe(32)
                    expira = datetime.now(timezone.utc) + timedelta(hours=1)

                    cur.execute(
                        """
                        INSERT INTO password_reset_tokens (usuario_id, token, expira_em)
                        VALUES (%s, %s, %s)
                        """,
                        (usuario["id"], token, expira),
                    )

                    enviar_email_recuperacao(usuario["email"], token, request.host_url)

        # Mensagem neutra — nao revela se o email existe
        flash("Se o e-mail estiver cadastrado, voce recebera o link em instantes.", "info")
        return redirect(url_for("auth.login"))

    return render_template("auth/recuperar_senha.html")


# ═══════════════════════════════════════════════════════════════════════════════
# RESETAR SENHA — via token
# ═══════════════════════════════════════════════════════════════════════════════

@auth_bp.route("/resetar-senha/<token>", methods=["GET", "POST"])
def resetar_senha(token: str):
    """
    GET  — Valida token e exibe formulario de nova senha.
    POST — Atualiza hash da senha e marca token como usado.

    Validacoes:
        - Token deve existir no banco.
        - Token nao deve ter sido usado (usado = FALSE).
        - Token nao deve estar expirado (expira_em > NOW()).
    """
    with acquire_conn() as conn:
        with conn.cursor() as cur:
            registro = fetch_one(
                cur,
                """
                SELECT prt.id, prt.usuario_id, prt.usado, prt.expira_em
                FROM password_reset_tokens prt
                WHERE prt.token = %s
                """,
                (token,),
            )

    # Validacoes do token
    agora = datetime.now(timezone.utc)
    token_invalido = (
        not registro
        or registro["usado"]
        or registro["expira_em"].replace(tzinfo=timezone.utc) < agora
    )

    if token_invalido:
        flash("Link invalido ou expirado. Solicite um novo.", "danger")
        return redirect(url_for("auth.recuperar_senha"))

    if request.method == "POST":
        nova_senha    = (request.form.get("nova_senha") or "")
        confirmar     = (request.form.get("confirmar_senha") or "")

        if len(nova_senha) < 6:
            flash("A senha deve ter no minimo 6 caracteres.", "warning")
            return render_template("auth/nova_senha.html", token=token)

        if nova_senha != confirmar:
            flash("As senhas nao coincidem.", "warning")
            return render_template("auth/nova_senha.html", token=token)

        novo_hash = generate_password_hash(nova_senha)

        try:
            with acquire_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "UPDATE usuarios SET senha_hash = %s WHERE id = %s",
                        (novo_hash, registro["usuario_id"]),
                    )
                    cur.execute(
                        "UPDATE password_reset_tokens SET usado = TRUE WHERE id = %s",
                        (registro["id"],),
                    )
        except Exception as exc:
            print(f"[AUTH] Erro ao resetar senha: {exc}")
            flash("Erro interno ao redefinir senha. Tente novamente.", "danger")
            return render_template("auth/nova_senha.html", token=token)

        flash("Senha redefinida com sucesso! Faca o login.", "success")
        return redirect(url_for("auth.login"))

    return render_template("auth/nova_senha.html", token=token)


# ═══════════════════════════════════════════════════════════════════════════════
# LOGOUT
# ═══════════════════════════════════════════════════════════════════════════════

@auth_bp.route("/logout")
def logout():
    """Encerra a sessao e redireciona para login."""
    session.clear()
    flash("Sessao encerrada.", "info")
    return redirect(url_for("auth.login"))
