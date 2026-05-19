# [Linguagem: Python]
import os
import sys

# Garante que os módulos da raiz do projeto sejam encontrados
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from dotenv import load_dotenv
import psycopg2

load_dotenv()

DATABASE_URL = os.environ["SUPABASE_DATABASE_URL"]

SQL = """
ALTER TABLE usuarios
    DROP CONSTRAINT IF EXISTS usuarios_role_check;

ALTER TABLE usuarios
    ADD CONSTRAINT usuarios_role_check
    CHECK (role IN ('admin', 'viewer', 'apoio'));
"""

print("Conectando ao banco...")
conn = psycopg2.connect(DATABASE_URL)
conn.autocommit = True

with conn.cursor() as cur:
    print("Executando migração...")
    cur.execute(SQL)

conn.close()
print("[OK] Constraint 'usuarios_role_check' atualizado com sucesso!")
print("     Agora aceita: admin | viewer | apoio")
