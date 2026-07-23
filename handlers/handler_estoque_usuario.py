"""
handlers/handler_estoque_usuario.py — Estoque → Usuário.

Entrega um ativo do estoque para um responsável:
seta status 'Ativo', atribui responsável/fazenda/setor e registra data de entrega.

FIX (bug anterior): data_entrega agora usa payload['data_transferencia']
em vez de date.today() hardcoded, permitindo registros retroativos.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from handlers.base_handler import TransferenciaHandler

if TYPE_CHECKING:
    import psycopg2.extensions


class EstoqueParaUsuarioHandler(TransferenciaHandler):
    """
    Tipo: 'Estoque para Usuario'

    Ações:
        - status → 'Ativo'
        - responsavel → payload['responsavel_destino']
        - fazenda → payload['fazenda_destino']
        - setor → payload['setor_destino']
        - data_entrega → payload['data_transferencia']   ← FIX: era date.today()
        - data_devolucao → NULL
        - usuario_anterior → responsavel atual (auditoria)
    """

    def executar(
        self,
        cur: "psycopg2.extensions.cursor",
        id_ativo: str,
        tabela: str,
        ativo_atual: dict,
        payload: dict,
    ) -> str:
        cur.execute(
            f"""UPDATE {tabela} SET
                    status           = 'Ativo',
                    responsavel      = %s,
                    fazenda          = %s,
                    setor            = %s,
                    data_entrega     = %s,
                    data_devolucao   = NULL,
                    usuario_anterior = %s,
                    updated_at       = NOW()
                WHERE id_ativo = %s""",
            (
                payload.get("responsavel_destino"),
                payload.get("fazenda_destino"),
                payload.get("setor_destino"),
                payload.get("data_transferencia"),   # usa a data do payload
                ativo_atual.get("responsavel"),
                id_ativo,
            ),
        )
        return id_ativo
