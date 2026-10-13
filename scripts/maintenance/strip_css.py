"""Extracao pontual de CSS: simula por padrao, aplica com backup."""
import argparse
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]
LINK = """<link rel="stylesheet" href="{{ url_for('static', filename='css/admin.css') }}">"""

def transform(content):
    matches = list(re.finditer(r'<style\b[^>]*>.*?</style\s*>', content, re.IGNORECASE | re.DOTALL))
    if len(matches) != 1:
        raise ValueError('Esperado exatamente um bloco style; nenhuma alteracao realizada.')
    if 'css/admin.css' in content:
        raise ValueError('A referencia ao CSS ja existe; revise manualmente.')
    match = matches[0]
    return content[:match.start()] + LINK + content[match.end():]

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true', help='Grava a alteracao apos criar backup.')
    args = parser.parse_args(argv)
    target = ROOT / 'templates' / 'index.html'
    css = ROOT / 'static' / 'css' / 'admin.css'
    if not css.is_file():
        raise SystemExit('CSS de destino ausente; operacao cancelada.')
    try:
        original = target.read_bytes()
        updated = transform(original.decode('utf-8'))
    except (OSError, UnicodeError, ValueError) as error:
        raise SystemExit(str(error)) from error
    if not args.apply:
        print('Simulacao: um bloco style seria substituido. Confira se admin.css contem TODAS as regras desse bloco antes de usar --apply.')
        return
    backup = target.with_name(target.name + '.before-strip-css.bak')
    try:
        with backup.open('xb') as stream:
            stream.write(original)
    except FileExistsError:
        raise SystemExit('Backup ja existe; operacao cancelada para nao sobrescreve-lo.')
    target.write_bytes(updated.encode('utf-8'))
    print(f'Alteracao aplicada; backup preservado em {backup}.')

if __name__ == '__main__':
    main()
