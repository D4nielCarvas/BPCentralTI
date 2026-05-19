"""
blueprints/apoio.py — Painel de Apoio (Administrador de Celulares de Inspeção).

Acesso: usuários com role='apoio' (administrador dos celulares de inspeção).
Funcionalidades:
    - Listagem completa de todos os celulares de inspeção de todas as fazendas.
    - Edição de cadastros (incluindo credenciais Gmail e MIP).
    - Campos sensíveis visíveis: gmail, senha, usuario_mip, senha_mip, id_sistema.

Segurança:
    - _apoio_or_admin_required: exige role == 'apoio' ou 'admin'.
    - Whitelist explícita de campos editáveis no POST — nunca aceita campos
      arbitrários do body (prevenção de mass assignment).
    - id_ativo (PK) nunca é alterado — vem exclusivamente da URL.
"""

from __future__ import annotations

from flask import Blueprint, flash, render_template, request, session, redirect, url_for

from db_layer import acquire_conn, fetch_all, fetch_one

apoio_bp = Blueprint("apoio", __name__, url_prefix="/apoio")


def _apoio_or_admin_required(f):
    """Permite acesso a roles 'apoio' e 'admin'. Redireciona os demais."""
    from functools import wraps

    @wraps(f)
    def decorated(*args, **kwargs):
        if "usuario_id" not in session:
            return redirect(url_for("auth.login"))
        if session.get("role", "") not in ("apoio", "admin"):
            return redirect(url_for("auth.login"))
        return f(*args, **kwargs)

    return decorated


# ═══════════════════════════════════════════════════════════════════════════════
# LISTAGEM — todos os celulares de inspeção de todas as fazendas
# ═══════════════════════════════════════════════════════════════════════════════

@apoio_bp.route("/celulares-inspecao")
@_apoio_or_admin_required
def celulares_inspecao():
    """
    Lista todos os celulares de inspeção com filtro opcional por fazenda.
    Exibe campos sensíveis: gmail, senha, id_sistema, usuario_mip, senha_mip.

    Query params:
        fazenda — nome da fazenda para filtrar (opcional).
        q       — busca textual em id_ativo, responsavel, modelo, id_sistema, usuario_mip.
    """
    filtro_fazenda = (request.args.get("fazenda") or "").strip()
    busca = (request.args.get("q") or "").strip()

    with acquire_conn() as conn:
        with conn.cursor() as cur:
            fazendas = fetch_all(
                cur,
                """
                SELECT DISTINCT fazenda
                FROM celulares_inspecao
                WHERE fazenda IS NOT NULL
                ORDER BY fazenda ASC
                """,
            )

            query = """
                SELECT
                    id_ativo, id_sistema, fazenda, setor, responsavel, cargo,
                    modelo, status, gmail, senha, usuario_mip, senha_mip,
                    observacoes, data_entrega, data_devolucao
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
                        id_ativo    ILIKE %s OR
                        id_sistema  ILIKE %s OR
                        responsavel ILIKE %s OR
                        modelo      ILIKE %s OR
                        usuario_mip ILIKE %s
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


# ═══════════════════════════════════════════════════════════════════════════════
# EDIÇÃO — atualizar cadastro de um celular de inspeção
# ═══════════════════════════════════════════════════════════════════════════════

@apoio_bp.route("/celulares-inspecao/<id_ativo>/editar", methods=["GET", "POST"])
@_apoio_or_admin_required
def editar_celular_inspecao(id_ativo: str):
    """
    GET:  Carrega o formulário de edição do celular de inspeção.
    POST: Persiste as alterações no banco.

    Campos editáveis (whitelist explícita):
        id_sistema, fazenda, setor, responsavel, cargo, modelo, status,
        gmail, senha, usuario_mip, senha_mip, data_entrega,
        data_devolucao, observacoes.

    Complexidade: O(1) — operação por chave primária.
    """
    with acquire_conn() as conn:
        with conn.cursor() as cur:
            celular = fetch_one(
                cur,
                """
                SELECT id_ativo, id_sistema, fazenda, setor, responsavel, cargo,
                       modelo, status, gmail, senha, usuario_mip, senha_mip,
                       observacoes, data_entrega, data_devolucao
                FROM celulares_inspecao
                WHERE id_ativo = %s
                """,
                (id_ativo,),
            )

    if not celular:
        flash("Celular de inspeção não encontrado.", "danger")
        return redirect(url_for("apoio.celulares_inspecao"))

    if request.method == "POST":
        # Helper: retorna None para strings vazias (evita gravar "" no banco)
        def _f(field: str) -> str | None:
            val = (request.form.get(field) or "").strip()
            return val or None

        with acquire_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE celulares_inspecao SET
                        id_sistema     = %s,
                        fazenda        = %s,
                        setor          = %s,
                        responsavel    = %s,
                        cargo          = %s,
                        modelo         = %s,
                        status         = %s,
                        gmail          = %s,
                        senha          = %s,
                        usuario_mip    = %s,
                        senha_mip      = %s,
                        data_entrega   = %s,
                        data_devolucao = %s,
                        observacoes    = %s,
                        updated_at     = NOW()
                    WHERE id_ativo = %s
                    """,
                    (
                        _f("id_sistema"),
                        _f("fazenda"),
                        _f("setor"),
                        _f("responsavel"),
                        _f("cargo"),
                        _f("modelo"),
                        _f("status") or "Ativo",
                        _f("gmail"),
                        _f("senha"),
                        _f("usuario_mip"),
                        _f("senha_mip"),
                        _f("data_entrega") or None,
                        _f("data_devolucao") or None,
                        _f("observacoes"),
                        id_ativo,
                    ),
                )

        flash(f"Celular {id_ativo} atualizado com sucesso!", "success")
        return redirect(url_for("apoio.celulares_inspecao"))

    return render_template(
        "apoio/editar_celular_inspecao.html",
        celular=celular,
    )
