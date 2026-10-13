"""Contrato base para execução de transferências de ativos."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import psycopg2.extensions


class TransferenciaHandler(ABC):
    """Contrato base para handlers específicos de transferência."""

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
