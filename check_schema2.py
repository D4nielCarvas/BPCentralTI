import sys; sys.path.insert(0, '.')
from db_layer import acquire_conn
from app import app

with app.app_context():
    with acquire_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name='manutencoes' ORDER BY ordinal_position")
            print("manutencoes:", [r['column_name'] for r in cur.fetchall()])
            cur.execute("SELECT column_name, data_type FROM information_schema.columns WHERE table_name='usuarios' ORDER BY ordinal_position")
            print("usuarios:", [(r['column_name'], r['data_type']) for r in cur.fetchall()])
