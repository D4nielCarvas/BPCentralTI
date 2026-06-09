# [Linguagem: Python]
import os
import sys

# Garante que os módulos da raiz do projeto sejam encontrados
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from dotenv import load_dotenv
load_dotenv()

from utils.db_layer import init_pool, acquire_conn
import app as _a

tabelas = [
    'computadores','celulares','celulares_ponto','celulares_inspecao',
    'celulares_turma','impressoras','estabilizadores','starlink'
]

with _a.app.app_context():
    with acquire_conn() as conn:
        with conn.cursor() as cur:
            for t in tabelas:
                cur.execute(
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_name = %s ORDER BY ordinal_position",
                    (t,)
                )
                rows = cur.fetchall()
                cols = [r['column_name'] for r in rows]
                print(f"{t}: {cols}")
