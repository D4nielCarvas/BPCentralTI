"""
handlers/base_handler.py — Contrato Strategy para handlers de transferência.

Cada tipo de transferência implementa esta ABC.
O handler é responsável APENAS pelo UPDATE na tabela do ativo.
Commit, validação e log são responsabilidade do TransferenciaService.

Complexidade por operação: O(1) — todas as operações atuam sobre PK id_ativo.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import psycopg2.extensions


class TransferenciaHandler(ABC):
    """
    Strategy Pattern — contrato de handler de transferência.

    Cada implementação concreta aplica exatamente o UPDATE correto
    na tabela do ativo conforme o tipo de transferência.

    Não deve:
        - Fazer commit (responsabilidade do acquire_conn).
        - Registrar log no histórico (responsabilidade do Service).
        - Renomear id_ativo (responsabilidade do IdRenameService).
    """

    @abstractmethod
    def executar(
        self,
        cur: "psycopg2.extensions.cursor",
        id_ativo: str,
        tabela: str,
        ativo_atual: dict,
        payload: dict,
    ) -> str:
        """
        Aplica a mutação correta na tabela do ativo.

        Args:
            cur:        Cursor psycopg2 dentro de uma transação ativa.
            id_ativo:   Identificador do ativo a transferir.
            tabela:     Nome da tabela PostgreSQL onde o ativo vive.
            ativo_atual: Dict com os campos atuais do ativo (pré-transferência).
            payload:    Payload JSON da requisição POST.

        Returns:
            id_ativo final após a operação (pode mudar em migração de tipo).
        """
        ...
