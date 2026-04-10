import sys
sys.path.append('.')
import psycopg2
from app import DATABASE_URL

print(f"Connecting to: {DATABASE_URL.split('@')[-1]}")
try:
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()
    cur.execute("""
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'public'
    """)
    tables = cur.fetchall()
    print("Tables found in public schema:")
    for t in tables:
        print(f" - {t[0]}")
    
    # Check if a specific table exists to be sure
    cur.execute("SELECT count(*) FROM celulares")
    print("Count in 'celulares':", cur.fetchone()[0])
    
    cur.close()
    conn.close()
except Exception as e:
    print(f"Error: {e}")
