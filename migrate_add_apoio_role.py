"""
migrate_add_apoio_role.py
Adiciona a role 'apoio' ao CHECK constraint da tabela usuarios no Supabase.

Executar UMA VEZ com:
    python migrate_add_apoio_role.py
"""
import os
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
