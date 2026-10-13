"""Entrada legada desativada: nao reescreve mais codigo de autorizacao."""
from pathlib import Path
import runpy

if __name__ == '__main__':
    print('AVISO: patch_idor foi aposentado; executando somente diagnostico de leitura.')
    runpy.run_path(str(Path(__file__).resolve().parent / 'scripts' / 'maintenance' / 'audit_idor.py'), run_name='__main__')
