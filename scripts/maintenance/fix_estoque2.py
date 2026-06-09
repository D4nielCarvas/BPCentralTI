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
    print("Corrigindo estoque...")
    with acquire_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, nome FROM localidades")
            loc_map = {normalize_str(loc['nome']): loc['id'] for loc in cur.fetchall()}
            
            # Update historic data
            cur.execute("SELECT id, localizacao FROM estoque WHERE localidade_id IS NULL AND localizacao IS NOT NULL")
            rows = cur.fetchall()
            updated = 0
            for r in rows:
                loc_id = loc_map.get(normalize_str(r['localizacao']))
                if loc_id:
                    cur.execute("UPDATE estoque SET localidade_id = %s WHERE id = %s", (loc_id, r['id']))
                    updated += 1
            print(f"[estoque] {updated} registros antigos corrigidos.")
            
            # Create trigger function specifically for estoque
            cur.execute("""
            CREATE OR REPLACE FUNCTION set_localidade_id_from_localizacao()
            RETURNS TRIGGER AS $$
            BEGIN
                IF NEW.localizacao IS NOT NULL THEN
                    SELECT id INTO NEW.localidade_id 
                    FROM localidades 
                    WHERE unaccent(lower(nome)) = unaccent(lower(NEW.localizacao));
                END IF;
                RETURN NEW;
            END;
            $$ LANGUAGE plpgsql;
            """)
            
            # Apply trigger
            cur.execute("DROP TRIGGER IF EXISTS trg_set_loc_id_estoque ON estoque")
            cur.execute("""
            CREATE TRIGGER trg_set_loc_id_estoque
            BEFORE INSERT OR UPDATE ON estoque
            FOR EACH ROW
            EXECUTE FUNCTION set_localidade_id_from_localizacao();
            """)
            print("[estoque] Trigger adicionado com sucesso.")
            
        conn.commit()
    print("Tudo concluido!")

if __name__ == '__main__':
    from app import app
    with app.app_context():
        fix_estoque()
