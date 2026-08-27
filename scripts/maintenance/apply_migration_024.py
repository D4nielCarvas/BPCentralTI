# [Linguagem: Python]
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from dotenv import load_dotenv
load_dotenv()

from utils.db_layer import acquire_conn
import app as _a

with _a.app.app_context():
    with acquire_conn() as conn:
        with conn.cursor() as cur:
            migration_path = os.path.join(os.path.dirname(__file__), "..", "..", "migrations", "024_add_apelido_equipamentos.sql")
            with open(migration_path, "r", encoding="utf-8") as f:
                sql = f.read()
            print("Executando migration 024...")
            cur.execute(sql)
            conn.commit()
            print("Migration 024 aplicada com sucesso!")
