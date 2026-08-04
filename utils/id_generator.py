"""
id_generator.py — Módulo de geração de IDs padronizados de ativos de TI.

Padrão de ID: TIPO-LOCAL-SETOR-NN
Exemplo: NT-CEN-ADM-03

Celulares de Turma usam formato especial: CL-TRM-NN (sem fazenda fixa)
Exemplo: CL-TRM-01, CL-TRM-02

Fonte: Guia de Padronização de Nomenclatura de TI (documento oficial)

Regras:
    - Sem acentos ou cedilha nas siglas.
    - Todas as siglas em MAIÚSCULAS.
    - Limite de 15 caracteres no nome total (compatibilidade NetBIOS/Windows).
    - Sequencial com no mínimo 2 dígitos: 01, 02 ... 09, 10, 11 ...

Integração:
    Importe este módulo no app.py:
        from id_generator import (
            gerar_id_ativo, proximo_sequencial, sugerir_id,
            gerar_id_turma, proximo_sequencial_turma, sugerir_id_turma,
            SIGLAS_TIPO, SIGLAS_LOCAL, SIGLAS_SETOR,
        )

Dependências:
    - psycopg2-binary (conexão PostgreSQL)
    Nenhuma dependência externa além das já listadas no requirements.txt.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

# Sprint 4.1 — importa da fonte única de verdade de tipos de equipamento
from utils.equipment_types import TABELA_POR_SIGLA as _TABELA_POR_SIGLA
from utils.equipment_types import SETOR_TABELA_OVERRIDE as _SETOR_TABELA_OVERRIDE

if TYPE_CHECKING:
    import psycopg2.extensions

# ── Tabelas de siglas ──────────────────────────────────────────────────────────
# Fonte: Guia de Padronização de Nomenclatura de TI

# A. Tipos de Equipamento
SIGLAS_TIPO: dict[str, str] = {
    "DK":  "Desktop (Computador de Mesa)",
    "NT":  "Notebook",
    "CL":  "Celular / Smartphone",
    "IMP": "Impressora",
    "TB":  "Tablet",
    "EST": "Estabilizador",
    "STL": "Starlink",
}

# B. Localidades (Fazendas e Unidades)
SIGLAS_LOCAL: dict[str, str] = {
    "CEN": "Central",
    "SMN": "São Manoel",
    "TNG": "Tangará",
    "SPD": "São Pedro",
    "SJU": "São Judas",
    "SFR": "São Francisco",
    "STN": "Santana",
    "CD":  "CD",
    "SEL": "Santa Eliza",
    "SLU": "Santa Lucia",
    "SL2": "Santa Lucia 2",
    "CLN": "Caroline",
    "SJO": "São João",
    "SLZ": "Santa Luzia",
    "SAD": "Santa Adelina",
    "SFC": "Santa Francisca",
}

# C. Setores
SIGLAS_SETOR: dict[str, str] = {
    "FT":  "Fito",
    "ALP": "Almoxarifado Peças",
    "ALI": "Almoxarifado Insumos",
    "COO": "Coordenador",
    "ADM": "Administrativo",
    "APO": "Apoio",
    "COL": "Colheita",
    "PTO": "Ponto",
    "TRM": "Turma",
    "ABS": "Abastecimento",
    "IRR": "Irrigação",
    "STR": "Sestr",
    "AGR": "Agrícola",
    "CDP": "CD",
    "INP": "Inspeção",
    "LDR": "Líderes",
    "TI":  "TI",
    "BLC": "Balança",
    "COA": "COA",
    "RH":  "RH",
}

# (removido na Sprint 4.1 — ver utils/equipment_types.py)

# Prefixo exclusivo para Celulares Turma (formato CL-TRM-NN)
_TURMA_PREFIX = "CL-TRM-"


# ── Funções públicas — Equipamentos padrão ─────────────────────────────────────

def gerar_id_ativo(tipo: str, localidade: str, setor: str, sequencial: int) -> str:
    """
    Gera um ID de ativo formatado no padrão TIPO-LOCAL-SETOR-NN.

    O número sequencial é sempre formatado com dois dígitos mínimos, expandindo
    automaticamente para três ou mais quando necessário (ex.: 99 → '99', 100 → '100').

    Args:
        tipo: Sigla do tipo de equipamento (ex.: 'NT', 'DK', 'CL').
              Deve ser uma chave válida em SIGLAS_TIPO.
        localidade: Sigla da localidade (ex.: 'CEN', 'SMN').
                    Deve ser uma chave válida em SIGLAS_LOCAL.
        setor: Sigla do setor (ex.: 'ADM', 'TI').
               Deve ser uma chave válida em SIGLAS_SETOR.
        sequencial: Número sequencial do ativo (inteiro positivo).

    Returns:
        String no formato 'TIPO-LOCAL-SETOR-NN' (ex.: 'NT-CEN-ADM-01').

    Raises:
        ValueError: Se tipo, localidade ou setor não forem siglas válidas.
        ValueError: Se sequencial for menor ou igual a zero.
    """
    # Converte para maiúsculas antes da validação para garantir consistência
    tipo = tipo.upper()
    localidade = localidade.upper()
    setor = setor.upper()

    if tipo not in SIGLAS_TIPO:
        raise ValueError(f"Tipo '{tipo}' inválido. Válidos: {list(SIGLAS_TIPO)}")
    if localidade not in SIGLAS_LOCAL:
        raise ValueError(f"Localidade '{localidade}' inválida. Válidas: {list(SIGLAS_LOCAL)}")
    if setor not in SIGLAS_SETOR:
        raise ValueError(f"Setor '{setor}' inválido. Válidos: {list(SIGLAS_SETOR)}")
    if sequencial <= 0:
        raise ValueError(f"Sequencial deve ser maior que zero, recebido: {sequencial}")

    # Formata com dois dígitos mínimos; expande automaticamente se > 99
    seq_str = f"{sequencial:02d}"

    return f"{tipo}-{localidade}-{setor}-{seq_str}"


def proximo_sequencial(
    cur: "psycopg2.extensions.cursor",
    tipo: str,
    localidade: str,
    setor: str,
) -> int:
    """
    Retorna o próximo número sequencial de forma **atômica**.

    Usa INSERT ... ON CONFLICT ... DO UPDATE na tabela `id_sequenciais`
    (migration 020), garantindo que dois workers concorrentes nunca
    recebam o mesmo número — eliminando a race condition do SELECT+max+1 anterior.

    Sprint 3.2 — substitui SELECT LIKE + max+1 (race condition)
                   por operação atômica no banco.
    """
    prefixo = f"{tipo}-{localidade}-{setor}"
    cur.execute(
        """
        INSERT INTO id_sequenciais (prefixo, proximo)
        VALUES (%s, 2)
        ON CONFLICT (prefixo) DO UPDATE
            SET proximo = id_sequenciais.proximo + 1
        RETURNING proximo - 1 AS sequencial
        """,
        (prefixo,),
    )
    return cur.fetchone()["sequencial"]


def sugerir_id(
    cur: "psycopg2.extensions.cursor",
    tipo: str,
    localidade: str,
    setor: str,
) -> str:
    """
    Sugere o próximo ID disponível para um ativo no formato padrão.
    """
    seq = proximo_sequencial(cur, tipo, localidade, setor)
    return gerar_id_ativo(tipo, localidade, setor, seq)


# ── Funções públicas — Celulares Turma (formato especial CL-TRM-NN) ───────────

def gerar_id_turma(sequencial: int) -> str:
    """
    Gera um ID de celular de turma no formato CL-TRM-NN.

    Celulares de turma são itinerantes (sem fazenda fixa), portanto o ID
    não carrega sigla de localidade.

    Args:
        sequencial: Número sequencial do ativo (inteiro positivo).

    Returns:
        String no formato 'CL-TRM-NN' (ex.: 'CL-TRM-01').

    Raises:
        ValueError: Se sequencial for menor ou igual a zero.
    """
    if sequencial <= 0:
        raise ValueError(f"Sequencial deve ser maior que zero, recebido: {sequencial}")
    return f"{_TURMA_PREFIX}{sequencial:02d}"


def proximo_sequencial_turma(cur: "psycopg2.extensions.cursor") -> int:
    """
    Retorna o próximo sequencial disponível para Celular Turma (CL-TRM-NN),
    de forma atômica via tabela id_sequenciais.

    Sprint 3.2 — mesma lógica atômica de proximo_sequencial.
    """
    cur.execute(
        """
        INSERT INTO id_sequenciais (prefixo, proximo)
        VALUES ('CL-TRM', 2)
        ON CONFLICT (prefixo) DO UPDATE
            SET proximo = id_sequenciais.proximo + 1
        RETURNING proximo - 1 AS sequencial
        """,
    )
    return cur.fetchone()["sequencial"]


def sugerir_id_turma(cur: "psycopg2.extensions.cursor") -> str:
    """
    Sugere o próximo ID disponível para um celular de turma (CL-TRM-NN).
    """
    seq = proximo_sequencial_turma(cur)
    return gerar_id_turma(seq)
