import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()
try:
    conn = psycopg2.connect(os.getenv("SUPABASE_DATABASE_URL"))
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM celulares_inspecao")
    print(f"Count: {cur.fetchone()[0]}")
    conn.close()
except Exception as e:
    print(f"Error: {e}")
