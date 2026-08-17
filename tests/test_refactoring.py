"""
tests/test_refactoring.py — Testes para as Fases 1, 2 e 3 da refatoração.

Execução: pytest tests/test_refactoring.py -v
Requer: pytest, unittest.mock (stdlib), variável SUPABASE_DATABASE_URL no .env
"""

from __future__ import annotations

import concurrent.futures
import threading
from unittest.mock import MagicMock, patch, call

import pytest


# ═══════════════════════════════════════════════════════════════════════════════
# FIXTURES
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def app():
    """Cria instância Flask de teste com pool mockado."""
    import sys, os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

    with patch("db_layer._pool") as mock_pool:
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_conn.cursor.return_value.__enter__ = lambda s: mock_cur
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        mock_pool.getconn.return_value = mock_conn
        mock_pool.putconn = MagicMock()

        import app as flask_app
        flask_app.app.config["TESTING"] = True
        flask_app.app.config["WTF_CSRF_ENABLED"] = False
        yield flask_app.app, mock_pool, mock_conn, mock_cur


@pytest.fixture
def client(app):
    flask_app, *_ = app
    return flask_app.test_client()


# ═══════════════════════════════════════════════════════════════════════════════
# FASE 1 — db_layer (Connection Pool)
# ═══════════════════════════════════════════════════════════════════════════════

class TestDbLayer:
    """Testa o comportamento do pool de conexões."""

    def test_acquire_conn_raises_without_init(self):
        """RuntimeError se pool não foi inicializado."""
        from db_layer import acquire_conn
        import db_layer
        original = db_layer._pool
        db_layer._pool = None
        try:
            with pytest.raises(RuntimeError, match="Pool não inicializado"):
                with acquire_conn():
                    pass
        finally:
            db_layer._pool = original

    def test_acquire_conn_commit_on_success(self):
        """Conexão deve ser commitada ao término normal."""
        from db_layer import acquire_conn
        import db_layer

        mock_conn = MagicMock()
        mock_pool = MagicMock()
        mock_pool.getconn.return_value = mock_conn

        original = db_layer._pool
        db_layer._pool = mock_pool
        try:
            with acquire_conn() as conn:
                assert conn is mock_conn
            mock_conn.commit.assert_called_once()
            mock_conn.rollback.assert_not_called()
            mock_pool.putconn.assert_called_once_with(mock_conn)
        finally:
            db_layer._pool = original

    def test_acquire_conn_rollback_on_exception(self):
        """Rollback deve ocorrer se o bloco levantar exceção."""
        from db_layer import acquire_conn
        import db_layer

        mock_conn = MagicMock()
        mock_pool = MagicMock()
        mock_pool.getconn.return_value = mock_conn

        original = db_layer._pool
        db_layer._pool = mock_pool
        try:
            with pytest.raises(ValueError):
                with acquire_conn():
                    raise ValueError("erro de teste")
            mock_conn.rollback.assert_called_once()
            mock_conn.commit.assert_not_called()
            mock_pool.putconn.assert_called_once_with(mock_conn)
        finally:
            db_layer._pool = original

    def test_putconn_always_called(self):
        """Pool.putconn deve ser chamado mesmo em caso de exceção (finally)."""
        from db_layer import acquire_conn
        import db_layer

        mock_conn = MagicMock()
        mock_pool = MagicMock()
        mock_pool.getconn.return_value = mock_conn

        original = db_layer._pool
        db_layer._pool = mock_pool
        try:
            with pytest.raises(RuntimeError):
                with acquire_conn():
                    raise RuntimeError("falha")
            mock_pool.putconn.assert_called_once()
        finally:
            db_layer._pool = original


# ═══════════════════════════════════════════════════════════════════════════════
# FASE 2 — Race Condition (SELECT FOR UPDATE)
# ═══════════════════════════════════════════════════════════════════════════════

class TestMovimentarEstoque:
    """Testa a correção da race condition em movimentar_estoque."""

    def _set_admin_session(self, client):
        """Injeta sessão de admin no cliente de teste para passar pelo @admin_required."""
        with client.session_transaction() as sess:
            sess["usuario_id"] = 1
            sess["role"] = "admin"
            sess["is_admin_master"] = True

    def test_usa_for_update_na_query(self, client):
        """A query SQL deve conter FOR UPDATE."""
        self._set_admin_session(client)

        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_conn.__enter__ = lambda s: mock_conn
        mock_conn.__exit__ = MagicMock(return_value=False)
        mock_conn.cursor.return_value.__enter__ = lambda s: mock_cur
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        mock_cur.fetchone.return_value = {"id": 1, "quantidade": 10}

        with patch("blueprints.api_estoque.get_db") as mock_get_db:
            mock_get_db.return_value = mock_conn
            response = client.post(
                "/api/estoque/1/movimentar",
                json={"tipo": "saida", "quantidade": 3, "motivo": "teste"},
            )

        assert response.status_code == 200
        # Verifica que FOR UPDATE foi usado em alguma das chamadas a execute()
        calls_sql = [str(c) for c in mock_cur.execute.call_args_list]
        assert any("FOR UPDATE" in sql for sql in calls_sql), (
            f"SELECT deve usar FOR UPDATE para evitar race condition. "
            f"Calls registradas: {calls_sql}"
        )


    def test_rejeita_tipo_invalido(self, client):
        """tipo diferente de 'entrada'/'saida' deve retornar 400.

        [FIX] Injeta sessão de admin — sem isso @admin_required retorna 302.
        A validação do payload ocorre ANTES da query ao banco, portanto
        este teste não precisa mockar o pool.
        """
        self._set_admin_session(client)
        response = client.post(
            "/api/estoque/1/movimentar",
            json={"tipo": "cancelar", "quantidade": 1},
        )
        assert response.status_code == 400
        assert "tipo" in response.get_json()["msg"].lower()

    def test_rejeita_quantidade_zero(self, client):
        """quantidade=0 deve retornar 400."""
        self._set_admin_session(client)
        response = client.post(
            "/api/estoque/1/movimentar",
            json={"tipo": "saida", "quantidade": 0},
        )
        assert response.status_code == 400

    def test_rejeita_quantidade_negativa(self, client):
        """quantidade negativa deve retornar 400."""
        self._set_admin_session(client)
        response = client.post(
            "/api/estoque/1/movimentar",
            json={"tipo": "saida", "quantidade": -5},
        )
        assert response.status_code == 400

    def test_rejeita_quantidade_nao_numerica(self, client):
        """quantidade não numérica deve retornar 400."""
        self._set_admin_session(client)
        response = client.post(
            "/api/estoque/1/movimentar",
            json={"tipo": "entrada", "quantidade": "abc"},
        )
        assert response.status_code == 400


# ═══════════════════════════════════════════════════════════════════════════════
# FASE 3 — Blueprint celulares_bp
# ═══════════════════════════════════════════════════════════════════════════════

class TestCelularesBlueprint:
    """Testa as rotas do blueprint celulares_bp."""

    def _mock_db(self, mock_rows=None, mock_row=None):
        """Helper: cria mock da acquire_conn para o blueprint."""
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_conn.__enter__ = lambda s: mock_conn
        mock_conn.__exit__ = MagicMock(return_value=False)
        mock_conn.cursor.return_value.__enter__ = lambda s: mock_cur
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        mock_cur.fetchall.return_value = mock_rows or []
        mock_cur.fetchone.return_value = mock_row
        return mock_conn, mock_cur

    def test_listar_celulares_retorna_200(self, client):
        """GET /api/celulares deve retornar 200."""
        mock_conn, mock_cur = self._mock_db(mock_rows=[])
        with patch("blueprints.celulares.acquire_conn") as m:
            m.return_value = mock_conn
            response = client.get("/api/celulares")
        assert response.status_code == 200

    def test_listar_celulares_aceita_paginacao(self, client):
        """GET /api/celulares?page=2&per_page=10 deve ser aceito sem erro."""
        mock_conn, mock_cur = self._mock_db(mock_rows=[])
        with patch("blueprints.celulares.acquire_conn") as m:
            m.return_value = mock_conn
            response = client.get("/api/celulares?page=2&per_page=10")
        assert response.status_code == 200
        # Verifica que LIMIT/OFFSET foram passados na query
        sql_calls = [str(c) for c in mock_cur.execute.call_args_list]
        assert any("LIMIT" in s and "OFFSET" in s for s in sql_calls)

    def test_criar_celular_sem_id_retorna_400(self, client):
        """POST /api/celulares sem id_ativo deve retornar 400."""
        response = client.post(
            "/api/celulares",
            json={"modelo": "iPhone", "responsavel": "João"},
            content_type="application/json",
        )
        assert response.status_code == 400
        assert response.get_json()["ok"] is False

    def test_criar_celular_happy_path(self, client):
        """POST /api/celulares com id_ativo deve retornar 200 e ok=True."""
        mock_conn, mock_cur = self._mock_db()
        with patch("blueprints.celulares.acquire_conn") as m:
            m.return_value = mock_conn
            response = client.post(
                "/api/celulares",
                json={"id_ativo": "CL-CEN-TI-01", "modelo": "Galaxy A32"},
                content_type="application/json",
            )
        assert response.status_code == 200
        assert response.get_json()["ok"] is True

    def test_get_celular_nao_encontrado(self, client):
        """GET /api/celulares/<id> sem resultado deve retornar 404."""
        mock_conn, mock_cur = self._mock_db(mock_row=None)
        with patch("blueprints.celulares.acquire_conn") as m:
            m.return_value = mock_conn
            with patch("blueprints.celulares.fetch_one", return_value=None):
                response = client.get("/api/celulares/CL-XXX-99")
        assert response.status_code == 404

    def test_put_celular_nao_encontrado(self, client):
        """PUT /api/celulares/<id> sem ativo deve retornar 404."""
        mock_conn, mock_cur = self._mock_db(mock_row=None)
        with patch("blueprints.celulares.acquire_conn") as m:
            m.return_value = mock_conn
            with patch("blueprints.celulares.fetch_one", return_value=None):
                response = client.put(
                    "/api/celulares/CL-XXX-99",
                    json={"modelo": "novo"},
                    content_type="application/json",
                )
        assert response.status_code == 404

    def test_endpoints_celulares_turma_existem(self, client):
        """Rotas de celulares_turma devem estar registradas."""
        mock_conn, mock_cur = self._mock_db(mock_rows=[])
        with patch("blueprints.celulares.acquire_conn") as m:
            m.return_value = mock_conn
            response = client.get("/api/celulares_turma")
        assert response.status_code == 200

    def test_endpoints_celulares_ponto_existem(self, client):
        """Rotas de celulares_ponto devem estar registradas."""
        mock_conn, mock_cur = self._mock_db(mock_rows=[])
        with patch("blueprints.celulares.acquire_conn") as m:
            m.return_value = mock_conn
            response = client.get("/api/celulares_ponto")
        assert response.status_code == 200

    def test_per_page_maximo_500(self, client):
        """per_page>500 deve ser limitado a 500 (sem erro)."""
        mock_conn, mock_cur = self._mock_db(mock_rows=[])
        with patch("blueprints.celulares.acquire_conn") as m:
            m.return_value = mock_conn
            response = client.get("/api/celulares?per_page=9999")
        assert response.status_code == 200
        sql_calls = [str(c) for c in mock_cur.execute.call_args_list]
        # 500 deve aparecer nos params, não 9999
        assert not any("9999" in s for s in sql_calls)
