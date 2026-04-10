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
<<<<<<< HEAD
    "DK": "Desktop (Computador de Mesa)",
    "NT": "Notebook",
    "CL": "Celular / Smartphone",
    "IMP": "Impressora",
    "TB": "Tablet",
    "EST": "Estabilizador",  # Mantido para compatibilidade
    "STL": "Starlink",       # Mantido para compatibilidade
=======
    "DK":  "Desktop",
    "NT":  "Notebook",
    "CL":  "Celular",
    "IMP": "Impressora",
    "TB":  "Tablet",
>>>>>>> 3fb7f168516f89f26f043169e4684bc53c148fb8
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
<<<<<<< HEAD
    "CD": "CD",
=======
    "CD":  "CD",
>>>>>>> 3fb7f168516f89f26f043169e4684bc53c148fb8
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
<<<<<<< HEAD
    "FT": "Fito",
=======
    "FT":  "Fito",
    "ALP": "Almoxarifado de Peças",
    "ALI": "Almoxarifado de Insumos",
    "COO": "Coordenador",
    "ADM": "Administrativo",
    "APO": "Apoio",
>>>>>>> 3fb7f168516f89f26f043169e4684bc53c148fb8
    "COL": "Colheita",
    "ALP": "Almoxarifado Peças",
    "PTO": "Ponto",
<<<<<<< HEAD
    "ALI": "Almoxarifado Insumos",
    "COO": "Coordenador",
    "ADM": "ADM",
    "APO": "Apoio",
=======
>>>>>>> 3fb7f168516f89f26f043169e4684bc53c148fb8
    "TRM": "Turma",
    "ABS": "Abastecimento",
    "IRR": "Irrigação",
}

# Mapeamento tipo → tabela do banco (para proximo_sequencial)
_TABELA_POR_TIPO: dict[str, str] = {
    "DK":  "computadores",
    "NT":  "computadores",
    "CL":  "celulares",
    "IMP": "impressoras",
    "TB":  "celulares",
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

    Exemplos:
        >>> gerar_id_ativo('NT', 'TNG', 'FT', 1)
        'NT-TNG-FT-01'
        >>> gerar_id_ativo('IMP', 'CEN', 'ADM', 2)
        'IMP-CEN-ADM-02'
        >>> gerar_id_ativo('CL', 'SL2', 'COO', 4)
        'CL-SL2-COO-04'
        >>> gerar_id_ativo('DK', 'SFR', 'ALP', 1)
        'DK-SFR-ALP-01'
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
    
    # Validação NetBIOS (opcional, apenas log se passar de 15)
    if len(id_gerado) > 15:
        # Poderíamos logar aqui se necessário, mas seguimos o padrão solicitado
        pass
        
    return id_gerado


def proximo_sequencial(
    cur: "psycopg2.extensions.cursor",
    tipo: str,
    localidade: str,
    setor: str,
) -> int:
    """
    Consulta o banco e retorna o próximo número sequencial disponível.

    Busca todos os IDs existentes no padrão 'TIPO-LOCAL-SETOR-NN' na tabela
    correspondente ao tipo informado, extrai os sequenciais e retorna o maior + 1.
    Se nenhum registro for encontrado, retorna 1.

    Usa %s como placeholder (compatível com psycopg2 / PostgreSQL).

    Args:
        cur: Cursor psycopg2 ativo (dentro de uma transação aberta).
        tipo: Sigla do tipo de equipamento (ex.: 'NT').
        localidade: Sigla da localidade (ex.: 'CEN').
        setor: Sigla do setor (ex.: 'ADM').

    Returns:
        Inteiro representando o próximo sequencial disponível (mínimo 1).

    Exemplos:
        Se existem NT-CEN-ADM-01 e NT-CEN-ADM-02, retorna 3.
        Se não há registros com esse prefixo, retorna 1.
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
    Sugere o próximo ID disponível para um ativo, combinando proximo_sequencial e gerar_id_ativo.

    Função de conveniência que encapsula a consulta ao banco e a formatação do ID
    em uma única chamada.

    Args:
        cur: Cursor psycopg2 ativo (dentro de uma transação aberta).
        tipo: Sigla do tipo de equipamento.
        localidade: Sigla da localidade.
        setor: Sigla do setor.

    Returns:
        String com o próximo ID disponível no padrão 'TIPO-LOCAL-SETOR-NN'.

    Exemplos:
        >>> # Se NT-CEN-ADM-01 já existe:
        >>> sugerir_id(cur, 'NT', 'CEN', 'ADM')
        'NT-CEN-ADM-02'
    """
    seq = proximo_sequencial(cur, tipo, localidade, setor)
    return gerar_id_ativo(tipo, localidade, setor, seq)
