"""
handlers/handler_usuario_estoque.py — Usuário → Estoque.

Devolve o ativo ao estoque: limpa responsável, registra data de devolução
e o usuário anterior para fins de auditoria.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from handlers.base_handler import TransferenciaHandler

if TYPE_CHECKING:
    import psycopg2.extensions


class UsuarioParaEstoqueHandler(TransferenciaHandler):
    """
    Tipo: 'Usuario para Estoque'

    Ações:
        - status → 'Estoque'
        - responsavel → NULL
        - data_devolucao → payload['data_devolucao']
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
                    status          = 'Estoque',
                    responsavel     = NULL,
                    data_devolucao  = %s,
                    usuario_anterior = %s,
                    updated_at      = NOW()
                WHERE id_ativo = %s""",
            (
                payload.get("data_devolucao"),
                ativo_atual.get("responsavel"),
                id_ativo,
            ),
        )
        return id_ativo
