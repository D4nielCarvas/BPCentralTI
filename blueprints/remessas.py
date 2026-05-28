from __future__ import annotations
from flask import Blueprint, flash, redirect, render_template, request, url_for, session
from auth_utils import login_required, get_usuario_id, get_localidade_filter
from db_layer import acquire_conn, fetch_all

remessas_bp = Blueprint("remessas", __name__, url_prefix="/remessas")

@remessas_bp.route("/")
@login_required
def listar_remessas():
    localidade_id = get_localidade_filter()
    role = session.get("role")
    
    query = """
        SELECT r.*, l.nome AS localidade_nome, c.titulo AS chamado_titulo, u.nome AS usuario_nome
        FROM remessas_equipamentos r
        LEFT JOIN localidades l ON l.id = r.localidade_id
        LEFT JOIN chamados c ON c.id = r.chamado_id
        LEFT JOIN usuarios u ON u.id = r.usuario_id
        WHERE 1=1
    """
    params = []
    
    if role == "viewer" and localidade_id:
        query += " AND r.localidade_id = %s"
        params.append(localidade_id)
        
    query += " ORDER BY r.data_hora DESC"
    
    with acquire_conn() as conn:
        with conn.cursor() as cur:
            remessas = fetch_all(cur, query, tuple(params))
            
    return render_template("remessas/listar.html", remessas=remessas)


@remessas_bp.route("/novo", methods=["GET", "POST"])
@login_required
def registrar_remessa():
    localidade_id = get_localidade_filter()
    role = session.get("role")
    usuario_id = get_usuario_id()
    
    if request.method == "POST":
        id_ativo = request.form.get("id_ativo", "").strip()
        evento = request.form.get("evento", "").strip()
        chamado_id = request.form.get("chamado_id") or None
        forma_envio = request.form.get("forma_envio", "").strip()
        forma_detalhe = request.form.get("forma_detalhe", "").strip()
        entregue_por = request.form.get("entregue_por", "").strip()
        recebido_por = request.form.get("recebido_por", "").strip()
        observacoes = request.form.get("observacoes", "").strip()
        loc_id = request.form.get("localidade_id") or localidade_id
        tipo_equipamento = request.form.get("tipo_equipamento", "").strip()
        modelo = request.form.get("modelo", "").strip()
        
        # Anti-IDOR e Validação de Fluxo
        if role == "viewer" and evento not in ["saida_fazenda", "chegada_fazenda"]:
            flash("Permissão negada para este evento.", "danger")
            return redirect(url_for("remessas.listar_remessas"))
            
        if role in ["admin", "apoio"] and evento not in ["chegada_ti", "saida_ti"]:
            flash("Permissão negada para este evento.", "danger")
            return redirect(url_for("remessas.listar_remessas"))
            
        with acquire_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO remessas_equipamentos 
                    (id_ativo, tipo_equipamento, modelo, chamado_id, localidade_id, 
                     evento, forma_envio, forma_detalhe, entregue_por, recebido_por, 
                     usuario_id, observacoes)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (id_ativo, tipo_equipamento, modelo, chamado_id, loc_id, 
                     evento, forma_envio, forma_detalhe, entregue_por, recebido_por, 
                     usuario_id, observacoes)
                )
                
        flash("Evento de remessa registrado com sucesso!", "success")
        return redirect(url_for("remessas.timeline", id_ativo=id_ativo))
        
    id_ativo_get = request.args.get("id_ativo", "")
    chamado_id_get = request.args.get("chamado_id", "")
    return render_template(
        "remessas/registrar.html", 
        id_ativo=id_ativo_get, 
        chamado_id=chamado_id_get,
        role=role
    )


@remessas_bp.route("/timeline/<id_ativo>")
@login_required
def timeline(id_ativo: str):
    with acquire_conn() as conn:
        with conn.cursor() as cur:
            eventos = fetch_all(
                cur,
                """
                SELECT r.*, u.nome AS usuario_nome, c.titulo AS chamado_titulo
                FROM remessas_equipamentos r
                LEFT JOIN usuarios u ON u.id = r.usuario_id
                LEFT JOIN chamados c ON c.id = r.chamado_id
                WHERE r.id_ativo = %s
                ORDER BY r.data_hora ASC
                """,
                (id_ativo,)
            )
    return render_template("remessas/timeline.html", eventos=eventos, id_ativo=id_ativo)
