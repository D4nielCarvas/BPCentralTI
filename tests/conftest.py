# conftest.py — configuração global do pytest
# Garante que a RAIZ do projeto esteja no sys.path, independente de onde
# o pytest for invocado (raiz ou subpasta tests/).

import sys
import os
from unittest.mock import MagicMock, patch
import pytest

# Adiciona a RAIZ do projeto ao path (pasta pai de tests/)
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


@pytest.fixture
def app():
    """Cria instância Flask de teste configurada com pool mockado."""
    with patch("utils.db_layer._pool") as mock_pool:
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_conn.cursor.return_value.__enter__ = lambda s: mock_cur
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        mock_pool.getconn.return_value = mock_conn
        mock_pool.putconn = MagicMock()

        import app as flask_module
        flask_module.app.config["TESTING"] = True
        flask_module.app.config["WTF_CSRF_ENABLED"] = False
        flask_module.app.config["SECRET_KEY"] = "test-secret-key"
        yield flask_module.app


@pytest.fixture
def client(app):
    """Cliente de teste HTTP do Flask."""
    return app.test_client()
