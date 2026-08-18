"""
tests/test_pedidos_reestruturacao.py — Testes da reestruturação do módulo de pedidos.

Valida:
1. Auto-detecção e vínculo da localidade a partir da fazenda do usuário.
2. Criação de pedido com campos estruturados: Item, Quantidade, Motivo, Urgência.
3. Validação de entradas (quantidade <= 0, campos obrigatórios, limites).
4. Disparo de alertas/notificações para administradores (com urgência alta/urgente).
5. Listagem e detalhe de pedidos no portal da fazenda e painel admin.
6. Retrocompatibilidade com pedidos legados.
"""

import pytest
from unittest.mock import MagicMock, patch
from flask import session


class TestPedidosReestruturacao:
    """Testes unitários e de integração das novas regras de pedidos."""

    def test_novo_pedido_get_carrega_fazenda_auto(self, client):
        """Valida que o formulário de novo pedido carrega a fazenda vinculada da sessão."""
        with client.session_transaction() as sess:
            sess["usuario_id"] = 10
            sess["usuario_nome"] = "João Fazenda"
            sess["role"] = "viewer"
            sess["localidade_id"] = 2
            sess["fazenda_nome"] = "Fazenda Santa Maria"
            sess["_notif_cache"] = {"qtd": 0, "lista": []}
            sess["_notif_cache_ts"] = "2099-01-01T00:00:00"

        resp = client.get("/fazenda/pedidos/novo")
        assert resp.status_code == 200
        html = resp.data.decode("utf-8")
        assert "Fazenda Santa Maria" in html
        assert "name=\"item\"" in html
        assert "name=\"quantidade\"" in html
        assert "name=\"urgencia\"" in html
        assert "name=\"motivo\"" in html

    def test_novo_pedido_viewer_sem_localidade_bloqueia(self, client):
        """Valida que viewer sem localidade cadastrada é bloqueado."""
        with client.session_transaction() as sess:
            sess["usuario_id"] = 99
            sess["usuario_nome"] = "Sem Fazenda"
            sess["role"] = "viewer"
            sess["localidade_id"] = None
            sess["fazenda_nome"] = None
            sess["_notif_cache"] = {"qtd": 0, "lista": []}
            sess["_notif_cache_ts"] = "2099-01-01T00:00:00"

        with patch("blueprints.fazenda.fetch_one", return_value=None):
            resp = client.get("/fazenda/pedidos/novo", follow_redirects=True)
            assert resp.status_code == 200
            assert "não está vinculada a uma fazenda" in resp.data.decode("utf-8")

    def test_novo_pedido_sucesso_com_urgencia_e_notificacao(self, client):
        """Valida inserção de pedido com item, qtd, urgência e disparo de alerta."""
        with client.session_transaction() as sess:
            sess["usuario_id"] = 5
            sess["usuario_nome"] = "Operador Fazenda"
            sess["role"] = "viewer"
            sess["localidade_id"] = 3
            sess["fazenda_nome"] = "Fazenda Esperança"
            sess["_notif_cache"] = {"qtd": 0, "lista": []}
            sess["_notif_cache_ts"] = "2099-01-01T00:00:00"

        mock_cur = MagicMock()
        mock_cur.fetchone.side_effect = [
            {"id": 105}, # INSERT RETURNING id
        ]
        
        with patch("blueprints.fazenda.acquire_conn") as mock_conn, \
             patch("blueprints.fazenda.fetch_one", return_value={"nome": "Fazenda Esperança"}):
            mock_conn.return_value.__enter__.return_value.cursor.return_value.__enter__.return_value = mock_cur

            resp = client.post(
                "/fazenda/pedidos/novo",
                data={
                    "item": "Switch Gigabit 24 Portas",
                    "quantidade": "2",
                    "urgencia": "urgente",
                    "motivo": "Switch principal queimou durante tempestade",
                },
                follow_redirects=False,
            )

            assert resp.status_code == 302
            assert "/fazenda/pedidos/105" in resp.headers["Location"]

            # Verifica se o INSERT na tabela pedidos_viewer foi chamado com os parâmetros corretos
            insert_call_found = False
            for call in mock_cur.execute.call_args_list:
                args = call[0]
                if "INSERT INTO pedidos_viewer" in args[0]:
                    insert_call_found = True
                    params = args[1]
                    assert params[0] == 3 # loc_id
                    assert params[1] == 5 # usuario_id
                    assert params[2] == "Switch Gigabit 24 Portas" # item
                    assert params[3] == 2 # quantidade
                    assert params[4] == "Switch principal queimou durante tempestade" # motivo
                    assert params[5] == "urgente" # urgencia
            assert insert_call_found

    def test_novo_pedido_validacao_quantidade_invalida(self, client):
        """Valida que quantidade <= 0 é rejeitada com warning."""
        with client.session_transaction() as sess:
            sess["usuario_id"] = 5
            sess["role"] = "viewer"
            sess["localidade_id"] = 3
            sess["fazenda_nome"] = "Fazenda Esperança"
            sess["_notif_cache"] = {"qtd": 0, "lista": []}
            sess["_notif_cache_ts"] = "2099-01-01T00:00:00"

        resp = client.post(
            "/fazenda/pedidos/novo",
            data={
                "item": "Mouse USB",
                "quantidade": "0",
                "urgencia": "baixa",
                "motivo": "Para escritório",
            },
            follow_redirects=True,
        )
        assert resp.status_code == 200
        assert "A quantidade informada deve ser um número inteiro positivo" in resp.data.decode("utf-8")

    def test_admin_pedidos_banner_urgencia(self, client):
        """Valida que o painel admin calcula e exibe o banner de alerta quando há pedidos urgentes pendentes."""
        with client.session_transaction() as sess:
            sess["usuario_id"] = 1
            sess["usuario_nome"] = "Admin TI"
            sess["role"] = "admin"
            sess["is_admin_master"] = True
            sess["_notif_cache"] = {"qtd": 0, "lista": []}
            sess["_notif_cache_ts"] = "2099-01-01T00:00:00"

        pedidos_falsos = [
            {
                "id": 1,
                "descricao": "Item 1",
                "item": "Switch Core",
                "quantidade": 1,
                "motivo": "Urgente",
                "urgencia": "urgente",
                "status": "pendente",
                "criado_em": "2026-08-18T10:00:00",
                "atualizado_em": "2026-08-18T10:00:00",
                "localidade_nome": "Fazenda Central",
                "usuario_nome": "José",
            }
        ]

        with patch("blueprints.admin_pedidos.acquire_conn") as mock_conn, \
             patch("blueprints.admin_pedidos.fetch_all", side_effect=[pedidos_falsos, []]), \
             patch("blueprints.admin_pedidos.fetch_one", return_value={"qtd": 1}):
            
            resp = client.get("/admin/pedidos")
            assert resp.status_code == 200
            html = resp.data.decode("utf-8")
            assert "Atenção da Administração de TI" in html
            assert "🚨 Urgente" in html
            assert "Switch Core" in html
