"""
handlers/handler_usuario_turma.py — Usuário → Turma.

É o handler mais complexo: pode operar em modo UPDATE (ativo já é um
celular_turma/ponto) ou em modo MIGRAÇÃO (ativo vem de outra tabela e
precisa ser movido para celulares_turma com snapshot de auditoria).

Fluxo de migração:
    1. Busca o registro completo do ativo na tabela de origem.
    2. Gera novo id_ativo no formato CL-TRM-NN.
    3. Insere o ativo em celulares_turma com os dados migrados.
    4. Salva snapshot JSONB em ativos_arquivados (auditoria imutável).
    5. Deleta o registro original.
    6. Atualiza historico e transferencias com o novo id_ativo.

Retorna o id_ativo final (novo CL-TRM-NN em caso de migração,
ou o id_ativo original em caso de update simples).
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from flask import session

from handlers.base_handler import TransferenciaHandler
from utils.db_layer import fetch_one
from utils.id_generator import sugerir_id_turma

if TYPE_CHECKING:
    import psycopg2.extensions

# Tabelas que já são de turma/ponto e não precisam migrar
_TABELAS_TURMA = {"celulares_turma", "celulares_ponto"}


class UsuarioParaTurmaHandler(TransferenciaHandler):
    """
    Tipo: 'Usuario para Turma'

    Dois sub-fluxos:
        A) Ativo já está em celulares_turma ou celulares_ponto → UPDATE simples.
        B) Ativo está em outra tabela → Migração com snapshot + DELETE.
    """

    def executar(
        self,
        cur: "psycopg2.extensions.cursor",
        id_ativo: str,
        tabela: str,
        ativo_atual: dict,
        payload: dict,
    ) -> str:
        turma_destino = payload.get("turma_destino", "")
        fazenda_dest  = payload.get("fazenda_destino")
        setor_dest    = payload.get("setor_destino")
        data_entrega  = payload.get("data_transferencia")

        if tabela in _TABELAS_TURMA:
            return self._update_turma_existente(
                cur, id_ativo, tabela, ativo_atual,
                turma_destino, fazenda_dest, setor_dest, data_entrega,
            )
        else:
            return self._migrar_para_turma(
                cur, id_ativo, tabela, ativo_atual,
                turma_destino, fazenda_dest, setor_dest, data_entrega,
            )

    # ── Sub-fluxo A: UPDATE simples ────────────────────────────────────────────

    def _update_turma_existente(
        self, cur, id_ativo, tabela, ativo_atual,
        turma_destino, fazenda_dest, setor_dest, data_entrega,
    ) -> str:
        cur.execute(
            f"""UPDATE {tabela} SET
                    num_turma        = %s,
                    responsavel      = %s,
                    fazenda          = %s,
                    setor            = %s,
                    data_entrega     = %s,
                    usuario_anterior = %s,
                    updated_at       = NOW()
                WHERE id_ativo = %s""",
            (
                turma_destino, turma_destino,
                fazenda_dest, setor_dest,
                data_entrega,
                ativo_atual.get("responsavel"),
                id_ativo,
            ),
        )
        return id_ativo

    # ── Sub-fluxo B: Migração com snapshot ─────────────────────────────────────

    def _migrar_para_turma(
        self, cur, id_ativo, tabela, ativo_atual,
        turma_destino, fazenda_dest, setor_dest, data_entrega,
    ) -> str:
        # 1. Busca o registro completo para montar o snapshot
        ativo_full = fetch_one(cur, f"SELECT * FROM {tabela} WHERE id_ativo=%s", (id_ativo,))

        # 2. Gera novo id_ativo no formato CL-TRM-NN (atômico, sem race condition)
        novo_id = sugerir_id_turma(cur)

        # 3. Insere em celulares_turma com dados migrados
        cur.execute(
            """INSERT INTO celulares_turma
               (id_ativo, num_turma, responsavel, fazenda, setor, modelo, tipo, status,
                uso_celular, carregador, termo_assinado, data_entrega, data_devolucao,
                gmail_clockin, senha, usuario_anterior, imei_1, imei_2, num_serie,
                armazenamento, observacoes)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            (
                novo_id,
                turma_destino,
                turma_destino,
                fazenda_dest or ativo_full.get("fazenda"),
                setor_dest   or ativo_full.get("setor"),
                ativo_full.get("modelo"),
                ativo_full.get("tipo"),
                ativo_full.get("status"),
                ativo_full.get("uso_celular"),
                ativo_full.get("carregador"),
                ativo_full.get("termo_assinado"),
                data_entrega,
                ativo_full.get("data_devolucao"),
                ativo_full.get("gmail") or ativo_full.get("gmail_clockin"),
                ativo_full.get("senha"),
                ativo_atual.get("responsavel"),
                ativo_full.get("imei_1"),
                ativo_full.get("imei_2"),
                ativo_full.get("num_serie"),
                ativo_full.get("armazenamento"),
                f"Migrado do ID {id_ativo}",
            ),
        )

        # 4. Snapshot imutável em ativos_arquivados (auditoria)
        arquivado_por = session.get("usuario") or session.get("email") or "Sistema"
        cur.execute(
            """INSERT INTO ativos_arquivados
               (id_ativo_origem, tabela_origem, motivo, migrado_para, snapshot, arquivado_por)
               VALUES (%s, %s, %s, %s, %s, %s)""",
            (
                id_ativo,
                tabela,
                "Migração de Tipo",
                novo_id,
                json.dumps(dict(ativo_full), default=str),
                arquivado_por,
            ),
        )

        # 5. Deleta o registro original
        cur.execute(f"DELETE FROM {tabela} WHERE id_ativo=%s", (id_ativo,))

        # 6. Atualiza referências históricas com o novo id
        cur.execute(
            "UPDATE historico SET id_ativo=%s WHERE id_ativo=%s",
            (novo_id, id_ativo),
        )

        return novo_id
