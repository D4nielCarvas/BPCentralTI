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
@login_required  # [FIX-1] rota estava sem autenticação — qualquer usuário anônimo acessava
def dashboard() -> Response:
    """Retorna estatísticas gerais para o painel principal.

    [FIX-7] Consolidado em uma única query com CTEs para reduzir roundtrips TCP.
    Antes: 21 queries sequenciais (~800ms–1.2s de latência acumulada).
    Agora: 1 query consolidada + 3 queries de apoio.

    [FIX-9] Nomes de tabela passados via psycopg2.sql.Identifier em vez de f-string,
    eliminando o antipadrão de SQL dinâmico sem escaping.
    """
    with acquire_conn() as conn:
        with conn.cursor() as cur:

            # [FIX-7 + FIX-9] Uma única query com UNION ALL para todos os equipamentos,
            # usando sql.Identifier para escaping seguro do nome de tabela.
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

            # Manutenções abertas
            cur.execute(
                "SELECT COUNT(*) AS n FROM manutencoes "
                "WHERE status NOT IN ('Concluída','Cancelada')"
            )
            man = cur.fetchone()["n"]

            # Total de descartes
            cur.execute("SELECT COUNT(*) AS n FROM descartes")
            desc = cur.fetchone()["n"]

            # Toners com estoque abaixo do mínimo
            cur.execute(
                "SELECT COUNT(*) AS n FROM toners "
                "WHERE quantidade_estoque <= quantidade_minima"
            )
            ton_alerta = cur.fetchone()["n"]

            # Total de itens em estoque
            cur.execute("SELECT COUNT(*) AS n FROM estoque")
            est_itens = cur.fetchone()["n"]

            # Pedidos abertos
            cur.execute(
                "SELECT COUNT(*) AS n FROM pedidos "
                "WHERE status NOT IN ('Finalizado','Rejeitado')"
            )
            ped_abertos = cur.fetchone()["n"]

            # Últimas 10 ações no histórico
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
