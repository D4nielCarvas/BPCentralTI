# -*- mode: python ; coding: utf-8 -*-
# InventarioTI.spec — PyInstaller v3.0.2
# Atualizado em 2026-05-04 para refletir arquitetura modular com Blueprints.

a = Analysis(
    ['app.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('templates', 'templates'),   # Jinja2 templates
        ('static', 'static'),         # Arquivos estáticos (CSS, JS, imagens, uploads)
        ('blueprints', 'blueprints'), # Pacote de blueprints Flask
        ('utils', 'utils'),           # Pacote de utils
        ('.env', '.'),                # Variáveis de ambiente (Supabase URL)
    ],
    hiddenimports=[
        # ── Módulos internos ──────────────────────────────────────
        'utils',
        'utils.id_generator',
        'utils.db_layer',
        'utils.auth_utils',
        'utils.api_utils',
        'utils.crypto_utils',
        # ── Blueprints (rotas modulares) ──────────────────────────
        'blueprints',
        'blueprints.core',
        'blueprints.api_dashboard',
        'blueprints.api_descartes',
        'blueprints.api_transferencias',
        'blueprints.api_historico',
        'blueprints.api_import_export',
        'blueprints.api_busca',
        'blueprints.api_ativos',
        'blueprints.api_estoque',
        'blueprints.api_pedidos',
        'blueprints.api_manutencoes',
        'blueprints.celulares',
        'blueprints.auth',
        'blueprints.fazenda',
        'blueprints.admin_pedidos',
        'blueprints.admin',
        'blueprints.chamados',
        'blueprints.admin_chamados',
        'blueprints.apoio',
        'blueprints.remessas',
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
        'werkzeug.security',   # generate_password_hash / check_password_hash
        'click',
        # ── Variáveis de ambiente ─────────────────────────────────
        'dotenv',
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
