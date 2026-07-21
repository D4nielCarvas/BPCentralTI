"""
equipment_types.py — Fonte única de verdade para mapeamentos de tipo de equipamento.

Sprint 4.1 — elimina a duplicação de _TABELA_POR_TIPO que existia
em api_transferencias.py e id_generator.py.

Importe daqui em qualquer módulo que precise mapear tipos → tabelas.
"""

# tipo_equipamento (nome legível da UI) → nome da tabela PostgreSQL
TABELA_POR_TIPO: dict[str, str] = {
    "Celular":          "celulares",
    "Celular Ponto":    "celulares_ponto",
    "Celular Inspeção": "celulares_inspecao",
    "Celular Turma":    "celulares_turma",
    "Computador":       "computadores",
    "Impressora":       "impressoras",
    "Estabilizador":    "estabilizadores",
    "Starlink":         "starlink",
}

# sigla_tipo (usada no id_generator) → tabela do banco
TABELA_POR_SIGLA: dict[str, str] = {
    "DK":  "computadores",
    "NT":  "computadores",
    "CL":  "celulares",
    "CLI": "celulares_inspecao",
    "IMP": "impressoras",
    "TB":  "celulares",
    "EST": "estabilizadores",
    "STL": "starlink",
    "BLC": "balancas",
}

# Setores que forçam uma tabela alternativa no proximo_sequencial.
# Chave: (sigla_tipo, sigla_setor) → tabela override.
# Centraliza a regra de negócio que antes estava hardcoded no id_generator.
SETOR_TABELA_OVERRIDE: dict[tuple[str, str], str] = {
    ("CL", "PTO"): "celulares_ponto",
}
