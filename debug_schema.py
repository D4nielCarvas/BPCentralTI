import sys
sys.path.append('.')
import psycopg2
from app import DATABASE_URL

tables = ["celulares", "celulares_ponto", "computadores", "impressoras", "estabilizadores", "starlink", "manutencoes", "descartes", "toners", "estoque", "historico"]

try:
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()
    for table in tables:
        print(f"--- Table: {table} ---")
        try:
            cur.execute(f"SELECT column_name, data_type FROM information_schema.columns WHERE table_name = '{table}'")
            cols = cur.fetchall()
            for col in cols:
                print(f"  {col[0]} ({col[1]})")
        except Exception as e:
            print(f"  Error checking table {table}: {e}")
    cur.close()
    conn.close()
except Exception as e:
    print(f"Global Error: {e}")
