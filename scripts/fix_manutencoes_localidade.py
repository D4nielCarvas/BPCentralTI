import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.db_layer import init_pool, acquire_conn, fetch_all, fetch_one, close_pool

def run():
    init_pool()
    try:
        with acquire_conn() as conn:
            with conn.cursor() as cur:
                manutencoes = fetch_all(cur, "SELECT id, id_ativo, tipo_equipamento FROM manutencoes WHERE localidade_id IS NULL AND tipo_equipamento IS NOT NULL AND id_ativo IS NOT NULL")
                
                tabela_map = {
                    "Celular": "celulares",
                    "Celular Ponto": "celulares_ponto",
                    "Celular Inspeção": "celulares_inspecao",
                    "Celular Turma": "celulares_turma",
                    "Computador": "computadores",
                    "Impressora": "impressoras",
                    "Estabilizador": "estabilizadores",
                    "Starlink": "starlink"
                }

                updated = 0
                for man in manutencoes:
                    tabela = tabela_map.get(man["tipo_equipamento"])
                    if tabela:
                        try:
                            equip = fetch_one(cur, f"SELECT localidade_id FROM {tabela} WHERE id_ativo = %s", (man["id_ativo"],))
                            if equip and equip["localidade_id"]:
                                cur.execute("UPDATE manutencoes SET localidade_id = %s WHERE id = %s", (equip["localidade_id"], man["id"]))
                                updated += 1
                        except Exception as e:
                            print(f"Error querying {tabela} for {man['id_ativo']}: {e}")
                            conn.rollback() 
                            # Continue silently
                            
                print(f"Updated {updated} records.")
    except Exception as e:
        print(f"Global Error: {e}")
    finally:
        close_pool()

if __name__ == "__main__":
    run()
