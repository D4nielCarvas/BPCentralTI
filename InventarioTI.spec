# -*- mode: python ; coding: utf-8 -*-
# InventarioTI.spec — PyInstaller v3.0.2
# Atualizado em 2026-05-04 para refletir arquitetura modular com Blueprints.

a = Analysis(
    ['app.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('templates', 'templates'),   # Jinja2 templates
        ('blueprints', 'blueprints'), # Pacote de blueprints Flask
        ('.env', '.'),                # Variáveis de ambiente (Supabase URL)
    ],
    hiddenimports=[
        # ── Módulos internos ──────────────────────────────────────
        'id_generator',
        'db_layer',
        # ── Blueprints (rotas modulares) ──────────────────────────
        'blueprints',
        'blueprints.celulares',
        # ── PostgreSQL / psycopg2 ─────────────────────────────────
        'psycopg2',
        'psycopg2.extras',
        'psycopg2.pool',
        'psycopg2._psycopg',
        # ── Flask e dependências ──────────────────────────────────
        'flask',
        'flask.templating',
        'jinja2',
        'jinja2.ext',
        'werkzeug',
        'werkzeug.utils',
        'werkzeug.routing',
        'werkzeug.exceptions',
        'click',
        # ── Variáveis de ambiente ─────────────────────────────────
        'dotenv',
        'python_dotenv',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'unittest', 'test'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='InventarioTI',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,   # console=True para ver erros de inicialização em produção
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='InventarioTI',
)
