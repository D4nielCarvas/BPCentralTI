#!/usr/bin/env bash
# build.sh — Script de build para o Render (Linux/Ubuntu)
# Instalação de dependências nativas ANTES do pip install.
set -o errexit

# ── Dependência nativa requerida por python-magic ────────────────────────────
# python-magic usa ctypes para chamar libmagic1 via dlopen().
# Sem ela, o app.py falha no import com OSError ao subir no Render.
apt-get install -y libmagic1

# ── Instalar dependências Python ─────────────────────────────────────────────
pip install -r requirements.txt
