# [Linguagem: Python]
import os
import sys

# Garante que os módulos da raiz do projeto sejam encontrados
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from dotenv import load_dotenv
load_dotenv()
from db_layer import acquire_conn
import app as _a

with _a.app.app_context():
    with acquire_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'pedidos_viewer'")
            print('pedidos_viewer columns:', [r['column_name'] for r in cur.fetchall()])
            cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'chamados'")
            print('chamados columns:', [r['column_name'] for r in cur.fetchall()])
