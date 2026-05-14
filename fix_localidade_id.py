import psycopg2
import unicodedata

from db_layer import acquire_conn

def normalize_str(s):
    if not s:
        return ""
    # Remove acentos
    s = unicodedata.normalize('NFKD', s).encode('ASCII', 'ignore').decode('utf-8')
    return s.strip().lower()

def fix_all():
    print("Iniciando correção de localidade_id...")
    with acquire_conn() as conn:
        with conn.cursor() as cur:
            # Pega localidades
            cur.execute("SELECT id, nome FROM localidades")
            locs = cur.fetchall()
            
            # Map normalizado -> id
            loc_map = {normalize_str(loc['nome']): loc['id'] for loc in locs}
            
            # Tabelas
            tabelas = [
                "celulares", "celulares_ponto", "celulares_turma", "celulares_inspecao",
                "computadores", "impressoras", "estabilizadores", "starlink"
            ]
            
            for tab in tabelas:
                cur.execute(f"SELECT id_ativo, fazenda FROM {tab} WHERE localidade_id IS NULL AND fazenda IS NOT NULL")
                rows = cur.fetchall()
                updated = 0
                for r in rows:
                    id_ativo = r['id_ativo']
                    fazenda = r['fazenda']
                    n_fazenda = normalize_str(fazenda)
                    
                    loc_id = loc_map.get(n_fazenda)
                    if loc_id:
                        cur.execute(f"UPDATE {tab} SET localidade_id = %s WHERE id_ativo = %s", (loc_id, id_ativo))
                        updated += 1
                print(f"Tabela {tab}: {updated} registros atualizados.")
                
            conn.commit()
    print("Concluído!")

if __name__ == '__main__':
    from app import app
    with app.app_context():
        fix_all()
