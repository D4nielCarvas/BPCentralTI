"""
bootstrap_id_sequenciais.py
===========================
Popula a tabela `id_sequenciais` (migration 020) com os máximos
sequenciais reais já existentes nos ativos de cada tabela.

EXECUTE UMA ÚNICA VEZ após rodar a migration 020_seq_id_lock.sql.

Uso:
    cd inventario-ti-v3
    python scripts/maintenance/bootstrap_id_sequenciais.py

Saída esperada:
    Analisando celulares (X registros)...
    Analisando computadores (Y registros)...
    ...
    Bootstrap concluído: N prefixos registrados em id_sequenciais.
    Prefixos e próximos sequenciais:
      NT-CEN-ADM → 5
      CL-SMN-TRM → 12
      ...
"""

import re
import sys
import os

# Garante que o módulo utils seja encontrado ao rodar da raiz do projeto
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from utils.db_layer import init_pool, acquire_conn, fetch_all

# Padrão: TIPO-LOCAL-SETOR-NN (ex: NT-CEN-ADM-03)
ID_PATTERN = re.compile(r"^([A-Z]+-[A-Z0-9]+-[A-Z0-9]+)-(\d+)$")
# Padrão especial Celular Turma: CL-TRM-NN
TURMA_PATTERN = re.compile(r"^(CL-TRM)-(\d+)$")

TABELAS = [
    "celulares",
    "celulares_ponto",
    "celulares_inspecao",
    "celulares_turma",
    "computadores",
    "impressoras",
    "estabilizadores",
    "starlink",
]


def main() -> None:
    init_pool()

    maximos: dict[str, int] = {}

    with acquire_conn() as conn:
        with conn.cursor() as cur:
            for tabela in TABELAS:
                rows = fetch_all(cur, f"SELECT id_ativo FROM {tabela}")
                print(f"Analisando {tabela} ({len(rows)} registros)...")

                for r in rows:
                    id_val: str = r["id_ativo"]

                    # Tenta padrão turma primeiro (CL-TRM-NN)
                    m = TURMA_PATTERN.match(id_val)
                    if m:
                        prefixo, seq = m.group(1), int(m.group(2))
                        maximos[prefixo] = max(maximos.get(prefixo, 0), seq)
                        continue

                    # Padrão padrão (TIPO-LOCAL-SETOR-NN)
                    m = ID_PATTERN.match(id_val)
                    if m:
                        prefixo, seq = m.group(1), int(m.group(2))
                        maximos[prefixo] = max(maximos.get(prefixo, 0), seq)

            if not maximos:
                print("Nenhum ativo encontrado. Tabela id_sequenciais permanece vazia.")
                return

            for prefixo, maximo in sorted(maximos.items()):
                cur.execute(
                    """INSERT INTO id_sequenciais (prefixo, proximo)
                       VALUES (%s, %s)
                       ON CONFLICT (prefixo) DO UPDATE
                           SET proximo = GREATEST(id_sequenciais.proximo, EXCLUDED.proximo)""",
                    (prefixo, maximo + 1),
                )

    print(f"\nBootstrap concluído: {len(maximos)} prefixos registrados em id_sequenciais.")
    print("Prefixos e próximos sequenciais:")
    for prefixo, maximo in sorted(maximos.items()):
        print(f"  {prefixo} → {maximo + 1}")


if __name__ == "__main__":
    main()
