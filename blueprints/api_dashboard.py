from flask import Blueprint, jsonify, Response
from utils.db_layer import acquire_conn, fetch_all

api_dashboard_bp = Blueprint('api_dashboard', __name__)

@api_dashboard_bp.route("/api/dashboard")
def dashboard() -> Response:
    """Retorna estatísticas gerais para o painel principal."""
    with acquire_conn() as conn:
        with conn.cursor() as cur:
            stats: dict[str, dict] = {}
            for tbl in [
                "celulares", "celulares_ponto", "celulares_inspecao",
                "celulares_turma",
                "computadores", "impressoras", "estabilizadores", "starlink",
            ]:
                cur.execute(f"SELECT COUNT(*) AS n FROM {tbl}")
                tot = cur.fetchone()["n"]
                cur.execute(f"SELECT COUNT(*) AS n FROM {tbl} WHERE status='Ativo'")
                atv = cur.fetchone()["n"]
                stats[tbl] = {"total": tot, "ativos": atv}

            cur.execute(
                "SELECT COUNT(*) AS n FROM manutencoes "
                "WHERE status NOT IN ('Concluída','Cancelada')"
            )
            man = cur.fetchone()["n"]

            cur.execute("SELECT COUNT(*) AS n FROM descartes")
            desc = cur.fetchone()["n"]

            cur.execute(
                "SELECT COUNT(*) AS n FROM toners "
                "WHERE quantidade_estoque <= quantidade_minima"
            )
            ton_alerta = cur.fetchone()["n"]

            cur.execute("SELECT COUNT(*) AS n FROM estoque")
            est_itens = cur.fetchone()["n"]

            cur.execute(
                "SELECT COUNT(*) AS n FROM pedidos "
                "WHERE status NOT IN ('Finalizado','Rejeitado')"
            )
            ped_abertos = cur.fetchone()["n"]

            recentes = fetch_all(
                cur,
                "SELECT id_ativo,tipo_equipamento,acao,data_hora "
                "FROM historico ORDER BY id DESC LIMIT 10",
            )

    return jsonify(
        {
            "equipamentos": stats,
            "manutencoes_abertas": man,
            "descartes": desc,
            "toner_alerta": ton_alerta,
            "estoque_itens": est_itens,
            "pedidos_abertos": ped_abertos,
            "atividade_recente": recentes,
        }
    )
