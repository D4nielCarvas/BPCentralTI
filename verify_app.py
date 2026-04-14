import re, sys

src = open(r'c:\Users\Daniel Carvas - TI\Desktop\inventario-ti-v3\app.py', encoding='utf-8').read()

checks = {
    # Bug fixes
    'BUG FIX: usuario_anterior no UPDATE celulares':    'usuario_anterior' in src and 'd.get("imei_1")' in src,
    'BUG FIX: imei_1/imei_2 no UPDATE celulares':       'd.get("imei_1"), d.get("imei_2")' in src,
    # Novos setores
    'STR = Sestr':                  '"STR": "Sestr"' in src,
    'AGR = Agricola':               '"AGR"' in src,
    'CDP = CD':                     '"CDP"' in src,
    'INP = Inspecao':               '"INP"' in src,
    'LDR = Lideres':                '"LDR"' in src,
    # celulares_inspecao no _TABELA_POR_TIPO
    'CLI em _TABELA_POR_TIPO':      '"CLI": "celulares_inspecao"' in src,
    # Upload
    'celular_inspecao no upload_termo': '"celular_inspecao": "celulares_inspecao"' in src,
    # Dashboard
    'celulares_inspecao no dashboard loop': '"celulares_inspecao"' in src and 'celulares_inspecao' in src,
    'pedidos_abertos no dashboard':         'pedidos_abertos' in src,
    # Rotas celulares_inspecao
    '/api/celulares_inspecao GET':          'def listar_celulares_inspecao' in src,
    '/api/celulares_inspecao POST':         'def criar_celular_inspecao' in src,
    '/api/celulares_inspecao PUT':          'def atualizar_celular_inspecao' in src,
    # Rotas pedidos
    '/api/pedidos GET':                     'def listar_pedidos' in src,
    '/api/pedidos POST':                    'def criar_pedido' in src,
    '/api/pedidos PUT':                     'def atualizar_pedido' in src,
    'Desconto estoque ao finalizar pedido': 'Finalizado' in src and 'nova_qtd = item_est' in src,
    # Impressoras por fazenda
    '/api/impressoras/por_fazenda':         'def impressoras_por_fazenda' in src,
    # Manutencoes
    'tipo_manutencao no INSERT manut':      'tipo_manutencao,pecas_utilizadas,subtipo' in src,
    'tipo_manutencao no UPDATE manut':      'tipo_manutencao=%s,pecas_utilizadas=%s,subtipo=%s' in src,
    # Toners
    'tipo_suprimento no INSERT toner_trocas': 'tipo_suprimento' in src,
    # Busca global + exportar
    'celulares_inspecao na busca_global':   '"Celular Inspe' in src,
    'pedidos no exportar':                  '"pedidos"' in src and 'tabelas_validas' in src,
    'celulares_inspecao no exportar':       '"celulares_inspecao"' in src and 'tabelas_validas' in src,
}

ok_count = fail_count = 0
for name, result in checks.items():
    status = 'OK  ' if result else 'FAIL'
    if not result:
        fail_count += 1
    else:
        ok_count += 1
    print(f'  [{status}] {name}')

print()
print(f'Resultado: {ok_count} checks OK / {fail_count} FALHAS')
sys.exit(0 if fail_count == 0 else 1)
