src = open(r'c:\Users\Daniel Carvas - TI\Desktop\inventario-ti-v3\id_generator.py', encoding='utf-8').read()
checks = {
    'STR = Sestr':   '"STR": "Sestr"' in src,
    'AGR = Agricola': '"AGR"' in src,
    'CDP = CD':      '"CDP": "CD"' in src,
    'INP = Inspecao': '"INP"' in src,
    'LDR = Lideres': '"LDR"' in src,
    'CLI em _TABELA_POR_TIPO': '"CLI": "celulares_inspecao"' in src,
    'SIGLAS_TIPO exportado': 'SIGLAS_TIPO' in src,
    'SIGLAS_LOCAL exportado': 'SIGLAS_LOCAL' in src,
    'SIGLAS_SETOR exportado': 'SIGLAS_SETOR' in src,
}
ok = fail = 0
for k, v in checks.items():
    status = 'OK  ' if v else 'FAIL'
    if not v: fail += 1
    else: ok += 1
    print(f'  [{status}] {k}')
print(f'\nResultado: {ok} OK / {fail} FALHAS no id_generator.py')
