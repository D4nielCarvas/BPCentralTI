# conftest.py — configuração global do pytest
# Garante que a RAIZ do projeto esteja no sys.path, independente de onde
# o pytest for invocado (raiz ou subpasta tests/).
# [FIX-3] Antes apontava para tests/ (dirname(__file__)), causando
# ModuleNotFoundError ao importar 'app', 'utils', 'blueprints' etc.

import sys
import os

# Adiciona a RAIZ do projeto ao path (pasta pai de tests/)
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

