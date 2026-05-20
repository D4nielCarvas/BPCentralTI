#!/usr/bin/env python3
"""
scripts/build_exe.py — Script de build para gerar o executável .exe via PyInstaller.

Uso (a partir da RAIZ do projeto):
    python scripts/build_exe.py

O executável será gerado em: dist/InventarioTI/InventarioTI.exe

Pré-requisitos:
    pip install pyinstaller==6.11.1

Estrutura do projeto:
    inventario-ti-v3/
    ├── app.py               ← entry point
    ├── db_layer.py
    ├── id_generator.py
    ├── blueprints/
    ├── templates/
    ├── database/
    ├── scripts/
    │   ├── build_exe.py     ← este arquivo
    │   └── COLETAR_PC.bat
    └── migrations/
"""

import os
import shutil
import subprocess
import sys


# ── Comando PyInstaller ───────────────────────────────────────────────────────
# Equivalente ao comando abaixo executado manualmente:
#
# pyinstaller \
#   --name InventarioTI \
#   --onedir \
#   --noconsole \
#   --add-data "templates;templates" \
#   --hidden-import psycopg2 \
#   --hidden-import dotenv \
#   app.py
#
# Notas:
#   --onedir     : Gera pasta (mais rápido para iniciar que --onefile)
#   --noconsole  : Sem janela de terminal (use --console para debug)
#   --add-data   : Inclui a pasta templates no bundle
#   Separador    : Windows usa ; | Linux/Mac usam :

def main() -> None:
    """Executa o build do executável via PyInstaller."""
    # Garante que o cwd é sempre a RAIZ do projeto, independente de onde
    # o script foi invocado (scripts/ ou raiz)
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    os.chdir(root)

    sep = ";" if sys.platform == "win32" else ":"

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--name", "InventarioTI",
        "--onedir",
        "--noconsole",
        f"--add-data=templates{sep}templates",
        "--hidden-import=id_generator",
        "--hidden-import=db_layer",
        "--hidden-import=blueprints.celulares",
        "--hidden-import=psycopg2",
        "--hidden-import=psycopg2.extras",
        "--hidden-import=psycopg2.pool",
        "--hidden-import=dotenv",
        "--hidden-import=werkzeug.utils",
        "--hidden-import=flask",
        "--hidden-import=jinja2",
        "--hidden-import=click",
        "--clean",
        "-y",
        "app.py",
    ]

    print("=" * 60)
    print(f"  BUILD: BP Central TI v3.0  (cwd: {root})")
    print("=" * 60)
    print(f"\nComando:\n  {' '.join(cmd)}\n")

    resultado = subprocess.run(cmd, check=False)

    if resultado.returncode == 0:
        exe_path = os.path.join("dist", "InventarioTI", "InventarioTI.exe")
        dist_dir = os.path.join("dist", "InventarioTI")
        
        env_file = ".env"
        env_copiado = False
        if os.path.exists(env_file):
            shutil.copy2(env_file, os.path.join(dist_dir, env_file))
            env_copiado = True

        print("\n" + "=" * 60)
        print("  Build concluído com sucesso!")
        print(f"  Executável: {exe_path}")
        if env_copiado:
            print("\n  O arquivo .env foi copiado automaticamente")
            print("  para a pasta do executável.")
        else:
            print("\n  ⚠️ IMPORTANTE:")
            print("  O arquivo .env não foi encontrado neste diretório.")
            print("  Crie-o ou copie-o para a mesma pasta do .exe")
            print("  antes de distribuir aos usuários.")
        print("=" * 60)
    else:
        print("\n[ERRO] Falha no build. Verifique os erros acima.")
        sys.exit(1)


if __name__ == "__main__":
    main()
