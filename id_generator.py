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
}

# Mapeamento tipo → tabela do banco (para proximo_sequencial)
_TABELA_POR_TIPO: dict[str, str] = {
    "DK":  "computadores",
    "NT":  "computadores",
    "CL":  "celulares",
    "CLI": "celulares_inspecao",
    "IMP": "impressoras",
    "TB":  "celulares",
    "EST": "estabilizadores",
    "STL": "starlink",
}

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
    Consulta o banco e retorna o próximo número sequencial disponível.

    Busca todos os IDs com o prefixo TIPO-LOCAL-SETOR- na tabela correspondente
    e retorna max_encontrado + 1. IDs liberados por transferência podem ser
    reutilizados se o max cair (comportamento natural do max+1).
    """
    tabela = _TABELA_POR_TIPO.get(tipo, "computadores")
    if tipo == "CL" and setor in ("PTO",):
        tabela = "celulares_ponto"

    prefixo = f"{tipo}-{localidade}-{setor}-"

    cur.execute(
        f"SELECT id_ativo FROM {tabela} WHERE id_ativo LIKE %s",
        (f"{prefixo}%",),
    )
    rows = cur.fetchall()

    maior = 0
    for row in rows:
        id_val: str = row["id_ativo"] if isinstance(row, dict) else row[0]
        sufixo = id_val[len(prefixo):]
        if sufixo.isdigit():
            maior = max(maior, int(sufixo))

    return maior + 1


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
    Consulta a tabela celulares_turma e retorna o próximo sequencial disponível.

    Busca todos os IDs com prefixo 'CL-TRM-' e retorna max_encontrado + 1.
    """
    cur.execute(
        "SELECT id_ativo FROM celulares_turma WHERE id_ativo LIKE %s",
        (f"{_TURMA_PREFIX}%",),
    )
    rows = cur.fetchall()

    maior = 0
    for row in rows:
        id_val: str = row["id_ativo"] if isinstance(row, dict) else row[0]
        sufixo = id_val[len(_TURMA_PREFIX):]
        if sufixo.isdigit():
            maior = max(maior, int(sufixo))

    return maior + 1


def sugerir_id_turma(cur: "psycopg2.extensions.cursor") -> str:
    """
    Sugere o próximo ID disponível para um celular de turma (CL-TRM-NN).
    """
    seq = proximo_sequencial_turma(cur)
    return gerar_id_turma(seq)
