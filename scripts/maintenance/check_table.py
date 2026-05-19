# [Linguagem: Python]
import os
import sys

# Garante que os módulos da raiz do projeto sejam encontrados
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from app import app
from flask import session

app.config['TESTING'] = True
app.config['WTF_CSRF_ENABLED'] = False
app.config['PROPAGATE_EXCEPTIONS'] = True

with app.test_client() as client:
    with client.session_transaction() as sess:
        sess['usuario_id'] = 1
        sess['role'] = 'admin'
        sess['localidade_id'] = 1
    
    response_pedido = client.post('/fazenda/pedidos/novo', data={
        'descricao': 'Teste de criar pedido válido',
        'localidade_id': '1'
    })
    print('Pedido POST Status:', response_pedido.status_code)

    response_chamado = client.post('/fazenda/chamados/novo', data={
        'titulo': 'Teste Chamado',
        'descricao': 'Teste de abrir chamado',
        'prioridade': 'media',
        'localidade_id': '1'
    })
    print('Chamado POST Status:', response_chamado.status_code)
