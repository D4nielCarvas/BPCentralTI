"""
blueprints/apoio.py — Painel de Apoio (somente leitura).

Acesso: usuários com role='apoio' (cargo de supervisor/apoio de campo).
Funcionalidade: visualização de todos os celulares de inspeção com dados
sensíveis visíveis (gmail, senha, id_sistema) + filtro por fazenda.

Segurança:
    - apoio_required: exige role == 'apoio' ou 'admin'.
    - Somente GET — nenhuma rota de escrita disponível.
    - Senha exibida apenas para este perfil — nunca exposta a viewers comuns.
"""

from __future__ import annotations

from flask import Blueprint, render_template, request, session, redirect, url_for

from auth_utils import login_required
from db_layer import acquire_conn, fetch_all

apoio_bp = Blueprint("apoio", __name__, url_prefix="/apoio")


def _apoio_or_admin_required(f):
    """Permite acesso a roles 'apoio' e 'admin'. Redireciona os demais."""
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if "usuario_id" not in session:
            return redirect(url_for("auth.login"))
        role = session.get("role", "")
        if role not in ("apoio", "admin"):
            return redirect(url_for("auth.login"))
        return f(*args, **kwargs)
    return decorated


@apoio_bp.route("/celulares-inspecao")
@_apoio_or_admin_required
def celulares_inspecao():
    """
    Lista todos os celulares de inspeção com filtro opcional por fazenda.
    Exibe campos sensíveis: gmail, senha, id_sistema.

    Query params:
        fazenda — nome da fazenda para filtrar (opcional).
        q       — busca textual em id_ativo, responsavel, modelo, id_sistema.
    """
    filtro_fazenda = (request.args.get("fazenda") or "").strip()
    busca = (request.args.get("q") or "").strip()

    with acquire_conn() as conn:
        with conn.cursor() as cur:
            # Busca todas as fazendas distintas para o filtro
            fazendas = fetch_all(
                cur,
                """
                SELECT DISTINCT fazenda
                FROM celulares_inspecao
                WHERE fazenda IS NOT NULL
                ORDER BY fazenda ASC
                """,
            )

            # Query principal com filtros
            query = """
                SELECT
                    id_ativo, id_sistema, fazenda, setor, responsavel, cargo,
                    modelo, numero, status, gmail, senha, observacoes,
                    data_entrega, data_devolucao
                FROM celulares_inspecao
                WHERE 1=1
            """
            params: list = []

            if filtro_fazenda:
                query += " AND fazenda = %s"
                params.append(filtro_fazenda)

            if busca:
                query += """
                    AND (
                        id_ativo   ILIKE %s OR
                        id_sistema ILIKE %s OR
                        responsavel ILIKE %s OR
                        modelo      ILIKE %s OR
                        numero      ILIKE %s
                    )
                """
                params += [f"%{busca}%"] * 5

            query += " ORDER BY fazenda ASC, id_ativo ASC"

            celulares = fetch_all(cur, query, tuple(params))

    return render_template(
        "apoio/celulares_inspecao.html",
        celulares=celulares,
        fazendas=fazendas,
        filtro_fazenda=filtro_fazenda,
        busca=busca,
        total=len(celulares),
    )
