"""
services/id_rename_service.py — Responsabilidade única: renomear id_ativo.

Quando um ativo muda de fazenda/setor durante uma transferência, seu ID
precisa ser atualizado para refletir a nova localização (ex: CL-CEN-ADM-01
→ CL-SMN-AGR-03). Esta classe encapsula esse comportamento de forma
isolada e testável.

Por que IDs mudam?
    Os IDs são mnemônicos físicos — facilitam identificar um ativo só
    pelo código. Etiquetas são reimpressas após cada transferência.
    Esse comportamento é mantido por compatibilidade com o processo operacional.

Complexidade:
    O(k) onde k = quantidade de registros históricos do ativo.
    Os UPDATEs em historico e transferencias usam índices já existentes.

Risco documentado:
    Gaps no sequencial são permanentes em caso de rollback — por design da
    tabela id_sequenciais (INSERT ... ON CONFLICT DO UPDATE não é reversível).
    Isso é aceitável e esperado; não representa perda de dados.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from utils.id_generator import (
    SIGLAS_LOCAL, SIGLAS_SETOR,
    gerar_id_ativo, proximo_sequencial,
)

if TYPE_CHECKING:
    import psycopg2.extensions

logger = logging.getLogger(__name__)

# Mapeamento inverso: nome completo → sigla (ex: 'Central' → 'CEN')
# Guard de integridade: garante que não há nomes duplicados em SIGLAS_LOCAL/SETOR
assert len({v: k for k, v in SIGLAS_LOCAL.items()}) == len(SIGLAS_LOCAL), \
    "SIGLAS_LOCAL contém valores duplicados — inversão produziria perda silenciosa."
assert len({v: k for k, v in SIGLAS_SETOR.items()}) == len(SIGLAS_SETOR), \
    "SIGLAS_SETOR contém valores duplicados — inversão produziria perda silenciosa."

_FAZENDA_PARA_SIGLA: dict[str, str] = {v: k for k, v in SIGLAS_LOCAL.items()}
_SETOR_PARA_SIGLA: dict[str, str] = {v: k for k, v in SIGLAS_SETOR.items()}

# Tipos que possuem sigla de tipo mapeada (fixos; Computador resolve dinamicamente)
_SIGLA_TIPO_MAP: dict[str, str] = {
    "Celular":          "CL",
    "Celular Ponto":    "CL",
    "Celular Inspeção": "CL",   # FIX: era 'Celular Inspecão' (typo)
    "Impressora":       "IMP",
    "Estabilizador":    "EST",
    "Starlink":         "STL",
}

# Tipos que nunca têm id_ativo renomeado (itinerantes)
_TIPOS_SEM_RENOMEACAO = {"Celular Turma"}

# Tipo de transferência que não aciona renomeação
_TRANSF_SEM_RENOMEACAO = {"Usuario para Estoque"}


class IdRenameService:
    """
    Renomeia id_ativo quando o ativo muda de fazenda/setor.

    Uso:
        novo_id = IdRenameService().renomear_se_necessario(
            cur, id_ativo, tipo_eq, tabela, payload, transf_id
        )
    """

    def renomear_se_necessario(
        self,
        cur: "psycopg2.extensions.cursor",
        id_ativo: str,
        tipo_eq: str,
        tabela: str,
        payload: dict,
        transf_id: int,
        ativo_atual: dict | None = None,
    ) -> str:
        """
        Verifica se a renomeação é necessária e, se sim, executa.

        Retorna o id_ativo final (novo ou original, sem alteração).
        """
        fazenda_dest = (payload.get("fazenda_destino") or "").strip()
        setor_dest   = (payload.get("setor_destino") or "").strip()

        fazenda_orig = (
            (ativo_atual or {}).get("fazenda")
            or payload.get("fazenda_origem")
            or ""
        ).strip()
        setor_orig = (
            (ativo_atual or {}).get("setor")
            or payload.get("setor_origem")
            or ""
        ).strip()

        # Condições que dispensam renomeação
        if payload.get("tipo_transferencia") in _TRANSF_SEM_RENOMEACAO:
            return id_ativo
        if tipo_eq in _TIPOS_SEM_RENOMEACAO:
            return id_ativo
        if id_ativo.startswith("CL-TRM-"):
            return id_ativo
        if not fazenda_dest or not setor_dest:
            return id_ativo

        # Se não houve mudança de localidade (fazenda e setor iguais), mantém o ID
        if fazenda_dest and setor_dest and fazenda_dest == fazenda_orig and setor_dest == setor_orig:
            return id_ativo

        tipo_sigla = self._resolver_sigla_tipo(cur, id_ativo, tipo_eq, ativo_atual=ativo_atual)
        if not tipo_sigla:
            return id_ativo

        local_sigla = _FAZENDA_PARA_SIGLA.get(fazenda_dest, fazenda_dest.upper()[:3])
        setor_sigla = _SETOR_PARA_SIGLA.get(setor_dest,   setor_dest.upper()[:3])

        try:
            from utils.db_layer import fetch_one
            while True:
                seq     = proximo_sequencial(cur, tipo_sigla, local_sigla, setor_sigla)
                novo_id = gerar_id_ativo(tipo_sigla, local_sigla, setor_sigla, seq)
                # Blindagem contra colisão: garante que novo_id não existe na tabela de destino
                colisao = fetch_one(cur, f"SELECT 1 FROM {tabela} WHERE id_ativo=%s", (novo_id,))
                if not colisao:
                    break
        except ValueError as exc:
            logger.warning("Regen ID falhou para %s: %s", id_ativo, exc)
            raise  # propaga para o Service tratar como aviso

        # Anota o ID anterior nas observações do registro de transferência
        self._anotar_id_anterior(cur, transf_id, id_ativo)

        # Propaga o novo id para todas as tabelas relacionadas
        cur.execute(f"UPDATE {tabela} SET id_ativo=%s WHERE id_ativo=%s", (novo_id, id_ativo))
        cur.execute("UPDATE historico SET id_ativo=%s WHERE id_ativo=%s", (novo_id, id_ativo))
        cur.execute("UPDATE transferencias SET id_ativo=%s WHERE id_ativo=%s", (novo_id, id_ativo))

        logger.info("id_ativo renomeado: %s → %s", id_ativo, novo_id)
        return novo_id

    # ── Helpers privados ───────────────────────────────────────────────────────

    def _resolver_sigla_tipo(
        self,
        cur: "psycopg2.extensions.cursor",
        id_ativo: str,
        tipo_eq: str,
        ativo_atual: dict | None = None,
    ) -> str | None:
        """Resolve a sigla de tipo; para Computador e Tablets, consulta o subtipo ou prefixo."""
        if id_ativo.startswith("TB-") or ((ativo_atual or {}).get("tipo") or "").lower() == "tablet":
            return "TB"

        if tipo_eq == "Computador":
            from utils.db_layer import fetch_one
            row = fetch_one(cur, "SELECT tipo FROM computadores WHERE id_ativo=%s", (id_ativo,))
            tipo_sub = (row or {}).get("tipo", "").lower()
            return "DK" if tipo_sub == "desktop" else "NT"
        return _SIGLA_TIPO_MAP.get(tipo_eq)

    def _anotar_id_anterior(
        self,
        cur: "psycopg2.extensions.cursor",
        transf_id: int,
        id_anterior: str,
    ) -> None:
        """Adiciona nota 'ID anterior: XXX' nas observações do registro de transferência."""
        nota = f"ID anterior: {id_anterior}"
        cur.execute(
            """UPDATE transferencias
               SET observacoes = CASE
                   WHEN observacoes IS NULL OR observacoes = '' THEN %s
                   ELSE observacoes || ' | ' || %s
               END
               WHERE id = %s""",
            (nota, nota, transf_id),
        )
