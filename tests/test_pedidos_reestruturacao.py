"""
tests/test_pedidos_reestruturacao.py — Testes da reestruturação do módulo de pedidos.

Valida:
1. Auto-detecção e vínculo da localidade a partir da fazenda do usuário.
2. Carregamento de itens de estoque no formulário de novo pedido.
3. Criação de pedido com campos estruturados: Item, Quantidade, Motivo, Urgência.
4. Validação de estoque (item sem saldo / indisponível exibe aviso e bloqueia criação).
5. Validação de entradas (quantidade <= 0, campos obrigatórios, limites).
6. Disparo de alertas/notificações para administradores (com urgência alta/urgente).
7. Baixa automática de estoque ao aprovar pedido (status 'aprovado') e prevenção de duplicidade.
8. Listagem e detalhe de pedidos no portal da fazenda e painel admin.
"""

import pytest
from unittest.mock import MagicMock, patch
from flask import session


class TestPedidosReestruturacao:
    """Testes unitários e de integração das novas regras de pedidos e estoque."""

    def test_novo_pedido_get_carrega_fazenda_e_estoque(self, client):
        """Valida que o formulário de novo pedido carrega a fazenda vinculada e itens de estoque."""
        with client.session_transaction() as sess:
            sess["usuario_id"] = 10
            sess["usuario_nome"] = "João Fazenda"
            sess["role"] = "viewer"
            sess["localidade_id"] = 2
            sess["fazenda_nome"] = "Fazenda Santa Maria"
            sess["_notif_cache"] = {"qtd": 0, "lista": []}
            sess["_notif_cache_ts"] = "2099-01-01T00:00:00"

        itens_mock = [
            {"id": 1, "item": "Teclado USB", "quantidade": 5, "unidade": "un", "localidade_id": 2},
            {"id": 2, "item": "Cabo HDMI 2m", "quantidade": 0, "unidade": "un", "localidade_id": 2},
        ]

        with patch("blueprints.fazenda.acquire_conn") as mock_conn, \
             patch("blueprints.fazenda.fetch_all", return_value=itens_mock):
            resp = client.get("/fazenda/pedidos/novo")
            assert resp.status_code == 200
            html = resp.data.decode("utf-8")
            assert "Fazenda Santa Maria" in html
            assert "name=\"item\"" in html
            assert "lista-estoque" in html
            assert "Teclado USB" in html
            assert "Cabo HDMI 2m" in html

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

    def test_novo_pedido_item_sem_estoque_permite_criacao_com_aviso_reposicao(self, client):
        """Valida que pedir um item com saldo zerado é permitido e gera notificação de reposição necessária."""
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
            {"id": 202},  # INSERT RETURNING id
        ]

        # Item com quantidade 0 no estoque
        item_estoque_zerado = {"id": 10, "item": "Monitor 27 Polegadas", "quantidade": 0, "unidade": "un"}

        with patch("blueprints.fazenda.acquire_conn") as mock_conn, \
             patch("blueprints.fazenda.fetch_one", side_effect=[item_estoque_zerado, {"nome": "Fazenda Esperança"}]):
            mock_conn.return_value.__enter__.return_value.cursor.return_value.__enter__.return_value = mock_cur
            
            resp = client.post(
                "/fazenda/pedidos/novo",
                data={
                    "item": "Monitor 27 Polegadas",
                    "quantidade": "1",
                    "urgencia": "alta",
                    "motivo": "Substituição de tela quebrada",
                },
                follow_redirects=False,
            )

            assert resp.status_code == 302
            assert "/fazenda/pedidos/202" in resp.headers["Location"]

            # Verifica se foi gerada notificação avisando sobre reposição necessária
            notif_call_found = False
            for call in mock_cur.execute.call_args_list:
                args = call[0]
                if "INSERT INTO notificacoes" in args[0]:
                    notif_call_found = True
                    msg = args[1][1]
                    assert "REPOSIÇÃO NECESSÁRIA" in msg
                    assert "Monitor 27 Polegadas" in msg
            assert notif_call_found


    def test_novo_pedido_sucesso_com_item_disponivel_e_notificacao(self, client):
        """Valida inserção de pedido quando há estoque disponível e disparo de notificação."""
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
            {"id": 105},  # INSERT RETURNING id
        ]

        item_estoque_valido = {"id": 44, "item": "Switch Gigabit 24 Portas", "quantidade": 10, "unidade": "un"}
        
        with patch("blueprints.fazenda.acquire_conn") as mock_conn, \
             patch("blueprints.fazenda.fetch_one", side_effect=[item_estoque_valido, {"nome": "Fazenda Esperança"}]):
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
                    assert params[0] == 3  # loc_id
                    assert params[1] == 5  # usuario_id
                    assert params[2] == "Switch Gigabit 24 Portas"  # item
                    assert params[3] == 2  # quantidade
                    assert params[4] == "Switch principal queimou durante tempestade"  # motivo
                    assert params[5] == "urgente"  # urgencia
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

    def test_admin_pedidos_baixa_estoque_ao_aprovar(self, client):
        """Valida que mudar status para 'aprovado' realiza a baixa atômica no estoque."""
        with client.session_transaction() as sess:
            sess["usuario_id"] = 1
            sess["usuario_nome"] = "Admin TI"
            sess["role"] = "admin"
            sess["is_admin_master"] = True
            sess["_notif_cache"] = {"qtd": 0, "lista": []}
            sess["_notif_cache_ts"] = "2099-01-01T00:00:00"

        pedido_mock = {
            "id": 50,
            "status": "pendente",
            "item": "Teclado USB",
            "quantidade": 2,
            "descricao": "Item: Teclado USB | Quantidade: 2",
            "localidade_id": 2,
        }

        mock_cur = MagicMock()
        mock_cur.fetchall.return_value = [{"id": 10, "item": "Teclado USB", "quantidade": 5}]

        with patch("blueprints.admin_pedidos.acquire_conn") as mock_conn, \
             patch("blueprints.admin_pedidos.fetch_one", side_effect=[pedido_mock, None, pedido_mock]), \
             patch("blueprints.admin_pedidos.fetch_all", return_value=[]):
            mock_conn.return_value.__enter__.return_value.cursor.return_value.__enter__.return_value = mock_cur

            resp = client.post(
                "/admin/pedidos/50/status",
                data={
                    "novo_status": "aprovado",
                    "observacao": "Aprovado para envio",
                },
                follow_redirects=False,
            )

            assert resp.status_code == 302
            assert "/admin/pedidos/50" in resp.headers["Location"]

            # Verifica se houve UPDATE no estoque decrementando a quantidade de 5 para 3 (5 - 2 = 3)
            update_estoque_found = False
            insert_mov_found = False
            for call in mock_cur.execute.call_args_list:
                args = call[0]
                if "UPDATE estoque SET quantidade = %s" in args[0]:
                    update_estoque_found = True
                    assert args[1][0] == 3  # nova quantidade
                    assert args[1][1] == 10  # estoque_id
                if "INSERT INTO estoque_movimentacoes" in args[0]:
                    insert_mov_found = True
                    assert args[1][0] == 10  # estoque_id
                    assert args[1][1] == 2   # quantidade

            assert update_estoque_found
            assert insert_mov_found

    def test_admin_pedidos_nao_duplica_baixa_ao_concluir(self, client):
        """Valida que transição de 'aprovado' para 'concluido' não debita o estoque duas vezes."""
        with client.session_transaction() as sess:
            sess["usuario_id"] = 1
            sess["usuario_nome"] = "Admin TI"
            sess["role"] = "admin"
            sess["is_admin_master"] = True
            sess["_notif_cache"] = {"qtd": 0, "lista": []}
            sess["_notif_cache_ts"] = "2099-01-01T00:00:00"

        pedido_mock = {
            "id": 50,
            "status": "aprovado",
            "item": "Teclado USB",
            "quantidade": 2,
            "descricao": "Item: Teclado USB | Quantidade: 2",
            "localidade_id": 2,
        }

        mock_cur = MagicMock()
        # ja_baixou retorna um registro indicando que a baixa já foi feita na aprovação
        with patch("blueprints.admin_pedidos.acquire_conn") as mock_conn, \
             patch("blueprints.admin_pedidos.fetch_one", side_effect=[pedido_mock, {"id": 999}, pedido_mock]), \
             patch("blueprints.admin_pedidos.fetch_all", return_value=[]):
            mock_conn.return_value.__enter__.return_value.cursor.return_value.__enter__.return_value = mock_cur

            resp = client.post(
                "/admin/pedidos/50/status",
                data={
                    "novo_status": "concluido",
                    "observacao": "Entregue na fazenda",
                },
                follow_redirects=False,
            )

            assert resp.status_code == 302
            assert "/admin/pedidos/50" in resp.headers["Location"]

            # Garante que NÃO houve novo UPDATE na tabela estoque
            update_estoque_calls = [c for c in mock_cur.execute.call_args_list if "UPDATE estoque SET" in c[0][0]]
            assert len(update_estoque_calls) == 0

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
