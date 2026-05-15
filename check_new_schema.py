from dotenv import load_dotenv
load_dotenv()
from db_layer import acquire_conn
import app as _a

with _a.app.app_context():
    with acquire_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT table_name, column_name 
                FROM information_schema.columns 
                WHERE table_name IN ('estoque', 'chamado_anexos', 'chamado_modelos')
                ORDER BY table_name, ordinal_position
            """)
            rows = cur.fetchall()
            if not rows:
                print("Nenhuma das tabelas encontradas.")
            else:
                for r in rows:
                    print(f"{r['table_name']}.{r['column_name']}")
