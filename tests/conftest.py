# conftest.py — configuração global do pytest
# Garante que a raiz do projeto esteja no sys.path, independente de onde
# o pytest for invocado (raiz ou subpasta tests/).

import sys
import os

# Adiciona a raiz do projeto ao path
sys.path.insert(0, os.path.dirname(__file__))
