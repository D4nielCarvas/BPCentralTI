"""
handlers/handler_usuario_usuario.py — Usuário → Usuário.

Transferência direta entre dois responsáveis: atualiza responsável,
fazenda, setor e registra a data de entrega.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from handlers.base_handler import TransferenciaHandler

if TYPE_CHECKING:
    import psycopg2.extensions


class UsuarioParaUsuarioHandler(TransferenciaHandler):
    """
    Tipo: 'Usuario para Usuario'

    Ações:
        - responsavel → payload['responsavel_destino']
        - fazenda → payload['fazenda_destino']
        - setor → payload['setor_destino']
        - data_entrega → payload['data_transferencia']
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
                    responsavel      = %s,
                    fazenda          = %s,
                    setor            = %s,
                    data_entrega     = %s,
                    usuario_anterior = %s,
                    updated_at       = NOW()
                WHERE id_ativo = %s""",
            (
                payload.get("responsavel_destino"),
                payload.get("fazenda_destino"),
                payload.get("setor_destino"),
                payload.get("data_transferencia"),
                ativo_atual.get("responsavel"),
                id_ativo,
            ),
        )
        return id_ativo
