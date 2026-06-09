# [Linguagem: Python]
import os
import sys

# Garante que os módulos da raiz do projeto sejam encontrados
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

import traceback
from utils.db_layer import acquire_conn
import app as _a

_a.app.app_context().push()

try:
    with acquire_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO chamados (localidade_id, criado_por, titulo, descricao, prioridade, status) VALUES (1, 1, 'teste', 'teste', 'media', 'aberto') RETURNING id")
            novo_id = cur.fetchone()['id']
            print('Chamado criado', novo_id)
            conn.rollback()
except Exception as e:
    traceback.print_exc()
