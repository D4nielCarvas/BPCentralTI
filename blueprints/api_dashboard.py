from psycopg2 import sql
from flask import Blueprint, jsonify, Response
from utils.auth_utils import login_required
from utils.db_layer import acquire_conn, fetch_all

api_dashboard_bp = Blueprint('api_dashboard', __name__)

# Tabelas de equipamentos permitidas — allowlist para evitar SQL dinâmico não controlado
_TABELAS_EQUIPAMENTOS = [
    "celulares",
    "celulares_ponto",
    "celulares_inspecao",
    "celulares_turma",
    "computadores",
    "impressoras",
    "estabilizadores",
    "starlink",
]


@api_dashboard_bp.route("/api/dashboard")
@login_required
def dashboard() -> Response:
    """Retorna estatísticas consolidadas para o painel principal."""
    with acquire_conn() as conn:
        with conn.cursor() as cur:
            # Consulta consolidada de contagens por tipo de equipamento
            union_parts = []
            for tbl in _TABELAS_EQUIPAMENTOS:
                union_parts.append(
                    sql.SQL(
                        "SELECT {tbl_name} AS tbl, COUNT(*) AS total, "
                        "COUNT(*) FILTER (WHERE status = 'Ativo') AS ativos "
                        "FROM {tbl_ident}"
                    ).format(
                        tbl_name=sql.Literal(tbl),
                        tbl_ident=sql.Identifier(tbl),
                    )
                )

            cur.execute(sql.SQL(" UNION ALL ").join(union_parts))
            stats: dict[str, dict] = {}
            for row in cur.fetchall():
                stats[row["tbl"]] = {"total": row["total"], "ativos": row["ativos"]}

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
                "SELECT id_ativo, tipo_equipamento, acao, data_hora "
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
