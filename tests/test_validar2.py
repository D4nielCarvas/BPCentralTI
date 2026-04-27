with open('templates/index.html', encoding='utf-8') as f:
    html = f.read()

pt_start = html.find('id="tb-celulares_ponto"')
pt_end = html.find('id="tb-celulares_inspecao"')
ponto_html = html[pt_start:pt_end]

header_start = html.find('id="celulares_ponto"')
header_end = html.find('id="celulares_inspecao"')
ponto_header = html[header_start:header_end]

modal_start = html.find('function openCelularPontoModal')
modal_end = html.find('function openCelularInspecaoModal')
ponto_modal = html[modal_start:modal_end]

pedidos_modal_start = html.find('function openPedidoModal')
pedidos_modal_end = html.find('function openManutencaoModal')
pedidos_modal = html[pedidos_modal_start:pedidos_modal_end]

checks = {
    'ponto_header_ok': 'Turma</th>' not in ponto_header,
    'ponto_row_ok': 'r.num_turma' not in ponto_html,
    'ponto_modal_ok': 'num_turma' not in ponto_modal,
    'pedidos_col_unica': 'grid-template-columns: 1fr' in pedidos_modal.replace('grid-template-columns:1fr', 'grid-template-columns: 1fr'),
}

for k, v in checks.items():
    print('OK' if v else 'FAIL', k)
