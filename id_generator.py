"""
id_generator.py — Módulo de geração de IDs padronizados de ativos de TI.

Padrão de ID: TIPO-LOCAL-SETOR-NN
Exemplo: NT-CEN-ADM-03

Fonte: Guia de Padronização de Nomenclatura de TI (documento oficial)

Regras:
    - Sem acentos ou cedilha nas siglas.
    - Todas as siglas em MAIÚSCULAS.
    - Limite de 15 caracteres no nome total (compatibilidade NetBIOS/Windows).
    - Sequencial com no mínimo 2 dígitos: 01, 02 ... 09, 10, 11 ...

Integração:
    Importe este módulo no app.py:
        from id_generator import gerar_id_ativo, proximo_sequencial, sugerir_id
        from id_generator import SIGLAS_TIPO, SIGLAS_LOCAL, SIGLAS_SETOR

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
    "DK": "Desktop (Computador de Mesa)",
    "NT": "Notebook",
    "CL": "Celular / Smartphone",
    "IMP": "Impressora",
    "TB": "Tablet",
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
    "CD": "CD",
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


# ── Funções públicas ───────────────────────────────────────────────────────────

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
        setor: Sigla do setor (ex.: 'ADM', 'FT').
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
    
    id_gerado = f"{tipo}-{localidade}-{setor}-{seq_str}"
    
    return id_gerado


def proximo_sequencial(
    cur: "psycopg2.extensions.cursor",
    tipo: str,
    localidade: str,
    setor: str,
) -> int:
    """
    Consulta o banco e retorna o próximo número sequencial disponível.
    """
    tabela = _TABELA_POR_TIPO.get(tipo, "computadores")
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
    Sugere o próximo ID disponível para um ativo.
    """
    seq = proximo_sequencial(cur, tipo, localidade, setor)
    return gerar_id_ativo(tipo, localidade, setor, seq)
