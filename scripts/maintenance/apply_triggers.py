# [Linguagem: Python]
import os
import sys

# Garante que os módulos da raiz do projeto sejam encontrados
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

import psycopg2
from utils.db_layer import acquire_conn

def create_triggers():
    print("Criando triggers no banco...")
    with acquire_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
            CREATE OR REPLACE FUNCTION set_localidade_id_from_fazenda()
            RETURNS TRIGGER AS $$
            BEGIN
                IF NEW.fazenda IS NOT NULL THEN
                    SELECT id INTO NEW.localidade_id 
                    FROM localidades 
                    WHERE unaccent(lower(nome)) = unaccent(lower(NEW.fazenda));
                END IF;
                RETURN NEW;
            END;
            $$ LANGUAGE plpgsql;
            """)
            
            tabelas = [
                "celulares", "celulares_ponto", "celulares_turma", "celulares_inspecao",
                "computadores", "impressoras", "estabilizadores", "starlink"
            ]
            for tab in tabelas:
                cur.execute(f"DROP TRIGGER IF EXISTS trg_set_loc_id ON {tab}")
                cur.execute(f"""
                CREATE TRIGGER trg_set_loc_id
                BEFORE INSERT OR UPDATE ON {tab}
                FOR EACH ROW
                EXECUTE FUNCTION set_localidade_id_from_fazenda();
                """)
                print(f"Trigger ativado: {tab}")
        conn.commit()
    print("Sucesso!")

if __name__ == '__main__':
    from app import app
    with app.app_context():
        create_triggers()
