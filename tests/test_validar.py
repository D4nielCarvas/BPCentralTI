with open('templates/index.html', encoding='utf-8') as f:
    html = f.read()

checks = {
    'toggleSenha_definida':      'function toggleSenha(' in html,
    'pwdField_definida':         'function pwdField(' in html,
    'cel_senha_toggle':          'cel-senha' in html,
    'cel_pto_senha_toggle':      'cel-pto-senha' in html,
    'cel_inp_senha_toggle':      'cel-inp-senha' in html,
    'cel_trm_senha_toggle':      'cel-trm-senha' in html,
    'comp_senha_toggle':         'comp-senha' in html,
    'stl_senha_toggle':          'stl-senha' in html and 'pwdField' in html,
    'num_turma_removido_header': 'Turma</th>' not in html,
    'num_turma_removido_row':    'r.num_turma' not in html,
    'pdfLink_turma':             'pdfLink(r.termo_pdf)' in html,
    'uploadBtn_turma':           'celular_turma' in html,
    'pedidos_busca_input':       'pedidos-search' in html,
    'loadPedidos_com_q':         'pedidos_q' in html,
    'pedidos_grid_coluna_unica': 'grid-template-columns:1fr' in html,
    'formatarData_rfc2822':      'getUTCDate' in html,
    'tipo_trigger_celular':      'oninput="triggerIdSuggestion()"' in html,
    'typeMap_tablet':            "'tablet' ? 'TB'" in html,
    'typeMap_desktop_lower':     "'desktop' ? 'DK'" in html,
}

all_ok = True
for k, v in checks.items():
    status = 'OK' if v else 'FAIL'
    if not v:
        all_ok = False
    print(f'{status}  {k}')

print()
print('RESULTADO FINAL:', 'TODOS OK' if all_ok else 'HÁ FALHAS')
