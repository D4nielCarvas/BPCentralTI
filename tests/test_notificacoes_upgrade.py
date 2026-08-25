"""
tests/test_notificacoes_upgrade.py — Testes das novas funcionalidades de Notificações.

Cobre:
1. Notificação na criação de chamados com nome do usuário e fazenda.
2. Notificação na criação de pedidos com nome do usuário e fazenda.
3. Notificação bidirecional: técnico responde chamado -> autor recebe notificação.
4. Notificação bidirecional: admin altera status do pedido -> autor recebe notificação.
5. Leitura de notificação: marcação como lida e redirecionamento de acordo com o papel (admin/viewer).
6. Rota /api/notificacoes/poll com identificação de urgência.
"""

import pytest
from unittest.mock import patch, MagicMock


class TestNotificacoesUpgrade:

    def test_notificacao_chamado_exibe_usuario_e_fazenda(self, client):
        """Valida que ao abrir um chamado, a notificação para admins contém o nome do solicitante e da fazenda."""
        with client.session_transaction() as sess:
            sess["usuario_id"] = 10
            sess["nome"] = "João Silva"
            sess["role"] = "viewer"
            sess["localidade_id"] = 2
            sess["_notif_cache"] = {"qtd": 0, "lista": []}

        mock_cur = MagicMock()
        mock_cur.fetchone.side_effect = [
            {"id": 88},  # INSERT INTO chamados RETURNING id
        ]

        with patch("blueprints.chamados.acquire_conn") as mock_conn, \
             patch("blueprints.chamados.fetch_one", side_effect=[{"nome": "Fazenda Boa Vista"}]):
            mock_conn.return_value.__enter__.return_value.cursor.return_value.__enter__.return_value = mock_cur

            resp = client.post(
                "/fazenda/chamados/novo",
                data={
                    "titulo": "Impressora sem conectar na rede",
                    "descricao": "Não imprime relatórios",
                    "prioridade": "urgente",
                    "localidade_id": "2",
                },
                follow_redirects=False,
            )

            assert resp.status_code == 302
            
            # Checa se o insert na tabela notificacoes recebeu a mensagem com João Silva e Fazenda Boa Vista
            notif_encontrada = False
            for call in mock_cur.execute.call_args_list:
                args = call[0]
                if "INSERT INTO notificacoes" in args[0]:
                    notif_encontrada = True
                    params = args[1]
                    msg = params[1]
                    assert "João Silva" in msg
                    assert "Fazenda Boa Vista" in msg
                    assert "[URGENTE]" in msg
            assert notif_encontrada

    def test_notificacao_pedido_exibe_usuario_e_fazenda(self, client):
        """Valida que ao abrir um pedido, a notificação para admins contém o solicitante e fazenda."""
        with client.session_transaction() as sess:
            sess["usuario_id"] = 12
            sess["nome"] = "Maria Oliveira"
            sess["role"] = "viewer"
            sess["localidade_id"] = 4
            sess["fazenda_nome"] = "Fazenda Santa Rita"
            sess["_notif_cache"] = {"qtd": 0, "lista": []}

        mock_cur = MagicMock()
        mock_cur.fetchone.side_effect = [
            {"id": 99},  # INSERT INTO pedidos_viewer RETURNING id
        ]

        item_estoque = {"id": 1, "item": "Mouse USB", "quantidade": 5, "unidade": "un"}

        with patch("blueprints.fazenda.acquire_conn") as mock_conn, \
             patch("blueprints.fazenda.fetch_one", side_effect=[item_estoque, {"nome": "Fazenda Santa Rita"}]):
            mock_conn.return_value.__enter__.return_value.cursor.return_value.__enter__.return_value = mock_cur

            resp = client.post(
                "/fazenda/pedidos/novo",
                data={
                    "item": "Mouse USB",
                    "quantidade": "1",
                    "urgencia": "alta",
                    "motivo": "Mouse quebrou",
                },
                follow_redirects=False,
            )

            assert resp.status_code == 302

            notif_encontrada = False
            for call in mock_cur.execute.call_args_list:
                args = call[0]
                if "INSERT INTO notificacoes" in args[0]:
                    notif_encontrada = True
                    params = args[1]
                    msg = params[1]
                    assert "Maria Oliveira" in msg
                    assert "Fazenda Santa Rita" in msg
                    assert "[URGENTE]" in msg
            assert notif_encontrada

    def test_tecnico_responde_chamado_notifica_autor(self, client):
        """Valida que quando o técnico admin envia resposta no chat, o criador do chamado é notificado."""
        with client.session_transaction() as sess:
            sess["usuario_id"] = 1  # Admin ID
            sess["nome"] = "Técnico TI"
            sess["role"] = "admin"
            sess["is_admin_master"] = True

        chamado_existente = {
            "id": 50,
            "status": "aberto",
            "criado_por": 15,  # Solicitante
            "localidade_nome": "Fazenda Central",
            "criado_por_nome": "Carlos Fazenda",
        }

        mock_cur = MagicMock()
        mock_cur.fetchone.side_effect = [
            chamado_existente,  # fetch_one chamado inicial
            {"id": 201},        # INSERT chamado_mensagens RETURNING id
        ]

        with patch("blueprints.admin_chamados.acquire_conn") as mock_conn, \
             patch("blueprints.admin_chamados.fetch_one", side_effect=[chamado_existente, None]), \
             patch("blueprints.admin_chamados.fetch_all", return_value=[]):
            mock_conn.return_value.__enter__.return_value.cursor.return_value.__enter__.return_value = mock_cur

            resp = client.post(
                "/admin/chamados/50",
                data={
                    "mensagem": "Estamos verificando o link de internet.",
                    "novo_status": "em_atendimento",
                },
                follow_redirects=False,
            )

            assert resp.status_code == 302

            notif_autor_chamada = False
            for call in mock_cur.execute.call_args_list:
                args = call[0]
                if "INSERT INTO notificacoes" in args[0]:
                    params = args[1]
                    if params[0] == 15:  # ID do criador
                        notif_autor_chamada = True
                        assert "Chamado #50" in params[2]
            assert notif_autor_chamada

    def test_admin_atualiza_status_pedido_notifica_autor(self, client):
        """Valida que quando o admin altera status do pedido, o solicitante original recebe notificação."""
        with client.session_transaction() as sess:
            sess["usuario_id"] = 1  # Admin
            sess["role"] = "admin"
            sess["is_admin_master"] = True

        pedido_existente = {
            "id": 33,
            "status": "pendente",
            "item": "Teclado",
            "quantidade": 1,
            "descricao": "Teclado",
            "localidade_id": 2,
            "usuario_id": 22,  # Solicitante original
        }

        mock_cur = MagicMock()

        with patch("blueprints.admin_pedidos.acquire_conn") as mock_conn, \
             patch("blueprints.admin_pedidos.fetch_one", side_effect=[pedido_existente, None]):
            mock_conn.return_value.__enter__.return_value.cursor.return_value.__enter__.return_value = mock_cur

            resp = client.post(
                "/admin/pedidos/33/status",
                data={"novo_status": "aprovado", "observacao": "Aprovado pela gerencia"},
                follow_redirects=False,
            )

            assert resp.status_code == 302

            notif_encontrada = False
            for call in mock_cur.execute.call_args_list:
                args = call[0]
                if "INSERT INTO notificacoes" in args[0]:
                    params = args[1]
                    if params[0] == 22:  # Solicitante
                        notif_encontrada = True
                        assert "Pedido #33" in params[2]
                        assert "Aprovado" in params[2]
            assert notif_encontrada

    def test_ler_notificacao_redireciona_viewer_para_painel_fazenda(self, client):
        """Valida que um usuário comum ao ler notificação de pedido é redirecionado para a tela de pedidos da fazenda."""
        with client.session_transaction() as sess:
            sess["usuario_id"] = 22
            sess["role"] = "viewer"

        notificacao_db = {"chamado_id": None, "pedido_id": 77}

        with patch("blueprints.admin_chamados.acquire_conn") as mock_conn, \
             patch("blueprints.admin_chamados.fetch_one", return_value=notificacao_db):
            mock_cur = MagicMock()
            mock_conn.return_value.__enter__.return_value.cursor.return_value.__enter__.return_value = mock_cur

            resp = client.get("/admin/chamados/notificacao/10/ler", follow_redirects=False)

            assert resp.status_code == 302
            assert "/fazenda/pedidos/77" in resp.headers["Location"]

    def test_poll_notificacoes_retorna_is_urgente(self, client):
        """Valida que a rota /api/notificacoes/poll retorna lista com flag is_urgente."""
        with client.session_transaction() as sess:
            sess["usuario_id"] = 1
            sess["role"] = "admin"

        mock_notifs = [
            {"id": 1, "chamado_id": 10, "pedido_id": None, "mensagem": "🚨 [URGENTE] Novo Chamado #10 - Daniel (Fazenda 1): Cabo rompido", "criado_em": "2026-08-25T10:00:00"},
            {"id": 2, "chamado_id": None, "pedido_id": 5, "mensagem": "📦 Pedido #5: Status atualizado para 'Aprovado'", "criado_em": "2026-08-25T10:05:00"},
        ]

        with patch("blueprints.core.acquire_conn") as mock_conn, \
             patch("blueprints.core.fetch_all", return_value=mock_notifs):
            mock_cur = MagicMock()
            mock_conn.return_value.__enter__.return_value.cursor.return_value.__enter__.return_value = mock_cur

            resp = client.get("/api/notificacoes/poll")

            assert resp.status_code == 200
            data = resp.get_json()
            assert data["ok"] is True
            assert len(data["notificacoes"]) == 2
            assert data["notificacoes"][0]["is_urgente"] is True
            assert data["notificacoes"][1]["is_urgente"] is False
