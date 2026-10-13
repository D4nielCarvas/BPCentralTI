# -*- mode: python ; coding: utf-8 -*-
# Fonte unica do build. Nao inclui .env, uploads ou relatorios de maquinas.
from pathlib import Path

root = Path(SPECPATH)
packages = ('blueprints', 'utils', 'services', 'handlers')
hiddenimports = ['psycopg2', 'psycopg2.extras', 'psycopg2.pool', 'dotenv', 'magic', 'flask_limiter', 'cryptography.fernet', 'fpdf']
for package in packages:
    for source in (root / package).rglob('*.py'):
        relative = source.relative_to(root).with_suffix('')
        parts = list(relative.parts)
        if parts[-1] == '__init__':
            parts.pop()
        hiddenimports.append('.'.join(parts))

datas = []
for directory in ('templates', 'static'):
    for source in (root / directory).rglob('*'):
        if not source.is_file():
            continue
        relative = source.relative_to(root)
        if 'uploads' in relative.parts or '__pycache__' in relative.parts:
            continue
        if source.name.startswith('.env') or source.suffix.lower() in {'.log', '.sqlite', '.db'}:
            continue
        datas.append((str(source), str(relative.parent)))

a = Analysis(
    [str(root / 'app.py')], pathex=[str(root)], binaries=[],
    datas=datas, hiddenimports=sorted(set(hiddenimports)),
    hookspath=[], hooksconfig={}, runtime_hooks=[],
    excludes=['tkinter'], noarchive=False, optimize=0,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, [], exclude_binaries=True, name='InventarioTI',
    debug=False, bootloader_ignore_signals=False, strip=False, upx=False,
    console=True, disable_windowed_traceback=False, argv_emulation=False,
    target_arch=None, codesign_identity=None, entitlements_file=None,
)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name='InventarioTI')
