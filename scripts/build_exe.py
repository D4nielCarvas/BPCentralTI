"""Build Windows usando InventarioTI.spec, sem copiar credenciais."""
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]

def main():
    if sys.platform != 'win32':
        raise SystemExit('Gere o executavel Windows em uma maquina Windows.')
    command = [sys.executable, '-m', 'PyInstaller', '--clean', '--noconfirm', str(ROOT / 'InventarioTI.spec')]
    subprocess.run(command, cwd=ROOT, check=True)
    destination = ROOT / 'dist' / 'InventarioTI'
    forbidden = [p for p in destination.rglob('*') if p.is_file() and (p.name == '.env' or p.name.startswith('.env.'))]
    if forbidden:
        raise SystemExit('Build bloqueado: arquivo de ambiente encontrado na distribuicao. Remova os segredos antes de distribuir.')
    executable = destination / 'InventarioTI.exe'
    if not executable.is_file():
        raise SystemExit('Build terminou sem gerar o executavel esperado.')
    print(f'Executavel: {executable}')
    print('Nenhuma credencial foi copiada. Configure o ambiente no destino; nao distribua .env real.')

if __name__ == '__main__':
    main()
