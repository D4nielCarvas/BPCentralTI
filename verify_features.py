import sys
html = open(r'c:\Users\Daniel Carvas - TI\Desktop\inventario-ti-v3\templates\index.html', encoding='utf-8').read()

checks = {
    'Nav - Cel. Inspe??o':          'Cel. Inspe' in html,
    'Nav - Pedidos':                'data-page="pedidos"' in html,
    'FAZENDAS array':               'const FAZENDAS' in html,
    'FAZENDA_SIGLA map':            'const FAZENDA_SIGLA' in html,
    'fazendaFld helper':            'const fazendaFld' in html,
    'Sestr (STR)':                  'Sestr' in html,
    'Agr?cola (AGR)':               'AGR' in html,
    'CD (CDP)':                     'CDP' in html,
    'INP':                          'INP' in html,
    'LDR':                          'LDR' in html,
    'formatPhone func':             'function formatPhone' in html,
    'triggerIdSuggestion':          'function triggerIdSuggestion' in html,
    'TRM/PTO logic':                'TRM' in html and 'numTurmaVal' in html,
    'openCelularInspecaoModal':     'openCelularInspecaoModal' in html,
    'openPedidoModal':              'openPedidoModal' in html,
    'onTipoTransfChange':           'onTipoTransfChange' in html,
    '6 tipos transferencia':        'Estoque para Fazenda' in html and 'Usuario para Usuario' in html,
    'onTipoManutChange':            'onTipoManutChange' in html,
    'Manut de 3 grau':              'tipo_manutencao' in html,
    'Pecas Utilizadas':             'pecas_utilizadas' in html,
    'Subtipo field':                'subtipo' in html,
    'Tipo Suprimento Cilindro':     'Cilindro' in html,
    'registrarTroca':               'function registrarTroca' in html,
    'loadCelularesInspecao':        'loadCelularesInspecao' in html,
    'loadPedidos':                  'function loadPedidos' in html,
    'id_sistema field':             'id_sistema' in html,
    'badge-pendente':               'badge-pendente' in html,
    'badge-finalizado':             'badge-finalizado' in html,
    'page-pedidos':                 'id="page-pedidos"' in html,
    'page-celulares_inspecao':      'id="page-celulares_inspecao"' in html,
    'tb-celulares_inspecao':        'id="tb-celulares_inspecao"' in html,
    'tb-pedidos':                   'id="tb-pedidos"' in html,
    'filterPedidos func':           'function filterPedidos' in html,
    'filterManut func':             'function filterManut' in html,
    'Impressoras por fazenda':      'impressoras/por_fazenda' in html,
    'SIGLAS_SETOR_JS':              'SIGLAS_SETOR_JS' in html,
    'setorSelect func':             'const setorSelect' in html,
}

ok_count = 0
fail_count = 0
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
