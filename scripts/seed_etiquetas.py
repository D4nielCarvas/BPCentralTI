"""
scripts/seed_etiquetas.py — Seed das etiquetas padrão de TI.

Executa a migration 007 e insere as etiquetas caso não existam.
Idempotente: ON CONFLICT DO NOTHING garante re-execução segura.
"""

from __future__ import annotations
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db_layer import acquire_conn

ETIQUETAS_PADRAO = [
    ("Impressora",    "#f59e0b"),
    ("Datasul",       "#3b82f6"),
    ("Gatec",         "#8b5cf6"),
    ("PowerBI",       "#f97316"),
    ("Sistema",       "#06b6d4"),
    ("PC",            "#10b981"),
    ("Periférico",    "#64748b"),
    ("Rede/Internet", "#ef4444"),
]


def run() -> None:
    print("Criando tabelas de etiquetas e relacionamento...")
    with acquire_conn() as conn:
        with conn.cursor() as cur:

            # Cria tabelas (idempotente)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS public.chamado_etiquetas (
                    id      SERIAL PRIMARY KEY,
                    nome    VARCHAR(50) UNIQUE NOT NULL,
                    cor_hex VARCHAR(7)  DEFAULT '#6c757d'
                )
            """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS public.pedidos_viewer_etiquetas (
                    pedido_id   INT REFERENCES public.pedidos_viewer(id) ON DELETE CASCADE,
                    etiqueta_id INT REFERENCES public.chamado_etiquetas(id) ON DELETE CASCADE,
                    PRIMARY KEY (pedido_id, etiqueta_id)
                )
            """)

            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_pve_pedido
                ON public.pedidos_viewer_etiquetas(pedido_id)
            """)
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_pve_etiqueta
                ON public.pedidos_viewer_etiquetas(etiqueta_id)
            """)

            # Insere etiquetas padrão
            inserted = 0
            for nome, cor in ETIQUETAS_PADRAO:
                cur.execute(
                    """
                    INSERT INTO chamado_etiquetas (nome, cor_hex)
                    VALUES (%s, %s)
                    ON CONFLICT (nome) DO NOTHING
                    """,
                    (nome, cor),
                )
                if cur.rowcount:
                    inserted += 1
                    print(f"  + Inserida: {nome} ({cor})")

        conn.commit()

    print(f"\nConcluído! {inserted} etiqueta(s) nova(s) inserida(s).")


if __name__ == "__main__":
    from app import app
    with app.app_context():
        run()
