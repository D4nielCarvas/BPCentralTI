"""
services/transferencia_service.py — Orquestrador central do sistema de transferências.

Responsabilidades:
    1. Validar o payload de entrada (regras de negócio puras, sem banco).
    2. Selecionar o handler correto via Strategy Pattern.
    3. Executar a transferência dentro de uma única transação de banco.
    4. Delegar renomeação de ID ao IdRenameService.
    5. Registrar o log no histórico do ativo.

NÃO é responsabilidade desta classe:
    - Serializar/deserializar HTTP (responsabilidade do blueprint).
    - Fazer commit/rollback (responsabilidade do acquire_conn).

Design Patterns:
    - Service Layer (Martin Fowler — Patterns of Enterprise Application Architecture)
    - Strategy (seleção de handler por tipo_transferencia)

Complexidade:
    - Caminho feliz sem renomeação: O(1) — 2 queries com acesso por PK.
    - Caminho com renomeação de ID: O(k), k = registros históricos do ativo.
    - Caminho de migração de tipo (Celular→Turma): O(k) + custo do INSERT.
"""

from __future__ import annotations

import logging
from datetime import date
from typing import TYPE_CHECKING

from handlers import (
    EstoqueParaUsuarioHandler,
    TransferenciaHandler,
    UsuarioParaEstoqueHandler,
    UsuarioParaTurmaHandler,
    UsuarioParaUsuarioHandler,
)
from services.id_rename_service import IdRenameService
from utils.api_utils import log_historico
from utils.db_layer import acquire_conn, fetch_one
from utils.equipment_types import TABELA_POR_TIPO

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

# ── Exceções de domínio ────────────────────────────────────────────────────────

class TransferenciaError(Exception):
    """Erro de negócio na criação de transferência. HTTP 400."""


class AtivoNaoEncontradoError(LookupError):
    """Ativo não existe na tabela esperada. HTTP 404."""


class StatusBloqueadoError(Exception):
    """Ativo está em status que impede transferência. HTTP 409."""


# ── Mapeamento Strategy ────────────────────────────────────────────────────────

_HANDLERS: dict[str, TransferenciaHandler] = {
    "Estoque para Usuario": EstoqueParaUsuarioHandler(),
    "Usuario para Estoque": UsuarioParaEstoqueHandler(),
    "Usuario para Usuario": UsuarioParaUsuarioHandler(),
    "Usuario para Turma":   UsuarioParaTurmaHandler(),
}

_STATUS_BLOQUEADOS = {"Manutenção", "Descartado"}


# ── Service ───────────────────────────────────────────────────────────────────

class TransferenciaService:
    """Ponto de entrada único para criação de transferências."""

    def criar(self, payload: dict, registrado_por: str) -> dict:
        """
        Cria uma transferência completa.

        Args:
            payload:        Dados da requisição (tipo_equipamento, id_ativo, etc.).
            registrado_por: Usuário da sessão Flask (nunca vem do payload).

        Returns:
            {"ok": True, "id_ativo": str} com o id_ativo final.

        Raises:
            TransferenciaError:     Validação de negócio falhou (400).
            AtivoNaoEncontradoError: Ativo não existe (404).
            StatusBloqueadoError:   Ativo em Manutenção/Descartado (409).
        """
        # 1. Validação pura (sem banco)
        self._validar(payload)

        tipo_eq     = payload["tipo_equipamento"]
        id_ativo    = payload["id_ativo"]
        tipo_transf = payload["tipo_transferencia"]
        tabela      = TABELA_POR_TIPO[tipo_eq]

        # 2. Seleciona o handler pelo tipo de transferência
        handler = _HANDLERS.get(tipo_transf)
        if not handler:
            raise TransferenciaError(f"Tipo de transferência desconhecido: '{tipo_transf}'")

        # 3. Executa dentro de uma única transação
        with acquire_conn() as conn:
            with conn.cursor() as cur:
                # 3a. Busca e valida o ativo no banco
                ativo_atual = self._buscar_e_validar_ativo(cur, id_ativo, tabela, tipo_eq)

                # 3b. Registra o evento na tabela transferencias (RETURNING id)
                transf_id = self._inserir_registro(cur, payload, ativo_atual, registrado_por)

                # 3c. Aplica o UPDATE correto via Strategy
                id_ativo_final = handler.executar(cur, id_ativo, tabela, ativo_atual, payload)

                # 3d. Atualiza o tipo_equipamento e id_ativo no registro de transferência
                #     (necessário quando a migração de tipo muda ambos)
                if id_ativo_final != id_ativo:
                    cur.execute(
                        """UPDATE transferencias
                           SET id_ativo=%s, tipo_equipamento='Celular Turma',
                               observacoes = CASE
                                   WHEN observacoes IS NULL OR observacoes = '' THEN %s
                                   ELSE observacoes || ' | ' || %s
                               END
                           WHERE id = %s""",
                        (
                            id_ativo_final,
                            f"ID anterior: {id_ativo}",
                            f"ID anterior: {id_ativo}",
                            transf_id,
                        ),
                    )

                # 3e. Renomeia id_ativo se mudou de fazenda/setor (pode gerar aviso)
                tipo_eq_final = "Celular Turma" if id_ativo_final != id_ativo else tipo_eq
                try:
                    id_ativo_final = IdRenameService().renomear_se_necessario(
                        cur, id_ativo_final, tipo_eq_final, tabela, payload, transf_id,
                    )
                except ValueError as exc:
                    # Renomeação falhou, mas transferência foi registrada
                    log_historico(cur, id_ativo_final, tipo_eq_final,
                                  f"Transferência: {tipo_transf} → {payload.get('responsavel_destino') or 'Estoque'}")
                    return {
                        "ok": True,
                        "id_ativo": id_ativo_final,
                        "aviso": f"Transferência registrada. Não foi possível gerar novo ID: {exc}",
                    }

                # 3f. Registra no histórico do ativo
                log_historico(
                    cur, id_ativo_final, tipo_eq_final,
                    f"Transferência: {tipo_transf} → {payload.get('responsavel_destino') or 'Estoque'}",
                )

                # 3g. Gerenciamento automático de Chips (Linhas Celular)
                from blueprints.celulares import desvincular_linha_para_estoque, repassar_linha_para_novo_responsavel
                if tipo_eq_final in ("Celular", "Celular Ponto", "Celular Turma", "Celular Inspeção"):
                    if "Estoque" in tipo_transf and tipo_transf.endswith("Estoque"):
                        desvincular_linha_para_estoque(cur, id_ativo_final)
                    elif payload.get("responsavel_destino"):
                        repassar_linha_para_novo_responsavel(cur, id_ativo_final, payload.get("responsavel_destino"), data_str)
                    elif payload.get("turma_destino"):
                        repassar_linha_para_novo_responsavel(cur, id_ativo_final, payload.get("turma_destino"), data_str)

        logger.info(
            "Transferência criada: %s [%s] → %s (por: %s)",
            id_ativo_final, tipo_transf,
            payload.get("responsavel_destino") or "Estoque",
            registrado_por,
        )

        return {"ok": True, "id_ativo": id_ativo_final}

    # ── Validação de negócio (sem banco) ──────────────────────────────────────

    def _validar(self, payload: dict) -> None:
        """
        Valida todas as regras de negócio que independem do banco de dados.
        Levanta TransferenciaError com mensagem descritiva em caso de falha.
        """
        tipo_eq = payload.get("tipo_equipamento", "")
        if not TABELA_POR_TIPO.get(tipo_eq):
            raise TransferenciaError(f"Tipo de equipamento inválido: '{tipo_eq}'")

        if not payload.get("id_ativo"):
            raise TransferenciaError("id_ativo é obrigatório.")

        tipo_transf  = payload.get("tipo_transferencia", "")
        data_str     = payload.get("data_transferencia") or date.today().isoformat()

        # Valida formato e valor da data
        try:
            data_parsed = date.fromisoformat(data_str)
        except ValueError:
            raise TransferenciaError("data_transferencia inválida. Use o formato AAAA-MM-DD.")

        if data_parsed > date.today():
            raise TransferenciaError("data_transferencia não pode ser uma data futura.")

        # Valida campos obrigatórios por tipo
        if tipo_transf == "Estoque para Usuario" and not payload.get("responsavel_destino"):
            raise TransferenciaError("responsavel_destino é obrigatório para 'Estoque para Usuario'.")

        if tipo_transf == "Usuario para Estoque" and not payload.get("data_devolucao"):
            raise TransferenciaError("data_devolucao é obrigatório para 'Usuario para Estoque'.")

        if tipo_transf == "Usuario para Usuario" and not payload.get("responsavel_destino"):
            raise TransferenciaError("responsavel_destino é obrigatório para transferência entre usuários.")

        if tipo_transf == "Usuario para Turma" and not payload.get("turma_destino"):
            raise TransferenciaError("turma_destino é obrigatório para 'Usuario para Turma'.")

    # ── Acesso ao banco ────────────────────────────────────────────────────────

    def _buscar_e_validar_ativo(
        self,
        cur,
        id_ativo: str,
        tabela: str,
        tipo_eq: str,
    ) -> dict:
        """Busca o ativo e garante que está em estado transferível."""
        ativo = fetch_one(
            cur,
            f"SELECT id_ativo, status, responsavel FROM {tabela} WHERE id_ativo=%s",
            (id_ativo,),
        )
        if not ativo:
            raise AtivoNaoEncontradoError(f"Ativo '{id_ativo}' não encontrado em '{tipo_eq}'.")

        if ativo["status"] in _STATUS_BLOQUEADOS:
            raise StatusBloqueadoError(
                f"Ativo com status '{ativo['status']}' não pode ser transferido."
            )
        return ativo

    def _inserir_registro(
        self,
        cur,
        payload: dict,
        ativo_atual: dict,
        registrado_por: str,
    ) -> int:
        """
        Insere o registro na tabela transferencias.
        Usa RETURNING id para ancorar UPDATEs posteriores no PK (nunca muda).

        O campo responsavel_destino para 'Usuario para Turma' é preenchido
        com turma_destino, mantendo o comportamento original.
        """
        resp_destino = payload.get("responsavel_destino")
        if payload.get("tipo_transferencia") == "Usuario para Turma":
            resp_destino = payload.get("turma_destino")

        data_transf = payload.get("data_transferencia") or date.today().isoformat()

        cur.execute(
            """INSERT INTO transferencias
               (id_ativo, tipo_equipamento,
                responsavel_origem, fazenda_origem, setor_origem,
                responsavel_destino, fazenda_destino, setor_destino,
                tipo_transferencia, motivo, data_transferencia,
                registrado_por, observacoes, termo_pdf)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
               RETURNING id""",
            (
                payload["id_ativo"],
                payload["tipo_equipamento"],
                payload.get("responsavel_origem"),
                payload.get("fazenda_origem"),
                payload.get("setor_origem"),
                resp_destino,
                payload.get("fazenda_destino"),
                payload.get("setor_destino"),
                payload.get("tipo_transferencia"),
                payload.get("motivo"),
                data_transf,
                registrado_por,
                payload.get("observacoes"),
                payload.get("termo_pdf"),
            ),
        )
        return cur.fetchone()["id"]
