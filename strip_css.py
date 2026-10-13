"""Entrada legada; implementacao em scripts/maintenance/strip_css.py."""
from pathlib import Path
import runpy

if __name__ == '__main__':
    print('AVISO: use python scripts/maintenance/strip_css.py. Sem --apply, apenas simula.')
    runpy.run_path(str(Path(__file__).resolve().parent / 'scripts' / 'maintenance' / 'strip_css.py'), run_name='__main__')
