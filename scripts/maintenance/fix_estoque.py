# [Linguagem: Python]
import os
import sys

# Garante que os módulos da raiz do projeto sejam encontrados
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

import psycopg2
import unicodedata
from utils.db_layer import acquire_conn

def normalize_str(s):
    if not s: return ""
    return unicodedata.normalize('NFKD', s).encode('ASCII', 'ignore').decode('utf-8').strip().lower()

def fix_estoque():
    with acquire_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, nome FROM localidades")
            loc_map = {normalize_str(loc['nome']): loc['id'] for loc in cur.fetchall()}
            
            tabelas = ["estoque", "estoque_equipamentos", "toners"]
            
            # 1) Fix past data
            for tab in tabelas:
                cur.execute(f"SELECT id, fazenda FROM {tab} WHERE localidade_id IS NULL AND fazenda IS NOT NULL")
                rows = cur.fetchall()
                updated = 0
                for r in rows:
                    loc_id = loc_map.get(normalize_str(r['fazenda']))
                    if loc_id:
                        cur.execute(f"UPDATE {tab} SET localidade_id = %s WHERE id = %s", (loc_id, r['id']))
                        updated += 1
                print(f"[{tab}] {updated} registros antigos corrigidos.")
                
            # 2) Add Triggers
            for tab in tabelas:
                cur.execute(f"DROP TRIGGER IF EXISTS trg_set_loc_id ON {tab}")
                cur.execute(f"""
                CREATE TRIGGER trg_set_loc_id
                BEFORE INSERT OR UPDATE ON {tab}
                FOR EACH ROW
                EXECUTE FUNCTION set_localidade_id_from_fazenda();
                """)
                print(f"[{tab}] Trigger adicionado.")
        conn.commit()
    print("Estoque corrigido!")

if __name__ == '__main__':
    from app import app
    with app.app_context():
        fix_estoque()
