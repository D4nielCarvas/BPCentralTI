# [Linguagem: Python]
"""
tests/test_apelido_equipamentos.py — Testes para funcionalidade de Apelido no Portal Fazenda.
"""

from unittest.mock import MagicMock, patch
import pytest


def test_fazenda_itens_renderiza_apelido(client):
    """Verifica se a página /fazenda/itens renderiza o Apelido no cabeçalho e na tabela."""
    with client.session_transaction() as sess:
        sess["usuario_id"] = 1
        sess["usuario_nome"] = "Usuario Fazenda"
        sess["role"] = "viewer"
        sess["localidade_id"] = 1
        sess["fazenda_nome"] = "Santana"
        sess["permissoes"] = {"ver_equipamentos": True, "editar_equipamentos": True}
        sess["_notif_cache"] = {"qtd": 0, "lista": []}
        sess["_notif_cache_ts"] = "2099-01-01T00:00:00"

    mock_itens = [
        {
            "id_ativo": "CL-STN-01",
            "apelido": "Celular Trator 01",
            "fazenda": "Santana",
            "setor": "Agrícola",
            "responsavel": "João Silva",
            "modelo": "Galaxy A14",
            "status": "Ativo",
            "numero": "16999990001",
            "termo_pdf": None,
        }
    ]

    with patch("blueprints.fazenda.acquire_conn"), \
         patch("blueprints.fazenda.fetch_all", return_value=mock_itens), \
         patch("blueprints.fazenda.has_permission", return_value=True):
        
        resp = client.get("/fazenda/itens")
        assert resp.status_code == 200
        html = resp.data.decode("utf-8")
        assert "<th>Apelido</th>" in html
        assert "Celular Trator 01" in html


def test_atualizar_celular_com_apelido(client):
    """Verifica se a rota PUT /api/celulares/<id_ativo> persiste o apelido."""
    with client.session_transaction() as sess:
        sess["usuario_id"] = 1
        sess["role"] = "viewer"
        sess["permissoes"] = {"editar_equipamentos": True}
        sess["_notif_cache"] = {"qtd": 0, "lista": []}
        sess["_notif_cache_ts"] = "2099-01-01T00:00:00"

    mock_cur = MagicMock()
    
    def mock_fetch_one(cur, query, params=None):
        if "SELECT id_ativo" in query:
            return {"id_ativo": "CL-STN-01", "numero": "16999990001"}
        if "SELECT id FROM funcionarios" in query:
            return {"id": 1}
        if "SELECT id FROM linhas_celular" in query:
            return {"id": 10}
        if "SELECT id, linha_id, funcionario_id FROM atribuicoes_linha" in query:
            return None
        return None

    with patch("blueprints.celulares.acquire_conn") as mock_acquire, \
         patch("blueprints.celulares.fetch_one", side_effect=mock_fetch_one):
        
        mock_conn = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cur
        mock_conn.cursor.return_value.__exit__.return_value = False
        mock_acquire.return_value.__enter__.return_value = mock_conn
        mock_acquire.return_value.__exit__.return_value = False
        
        payload = {
            "apelido": "Novo Apelido do Celular",
            "modelo": "Galaxy A14",
            "status": "Ativo",
            "fazenda": "Santana",
            "setor": "Agrícola",
            "responsavel": "João Silva",
            "numero": "16999990001"
        }
        
        resp = client.put("/api/celulares/CL-STN-01", json=payload)
        assert resp.status_code == 200
        assert resp.json["ok"] is True
        
        # Verifica se 'apelido' foi passado no UPDATE
        update_calls = [c for c in mock_cur.execute.call_args_list if "UPDATE celulares SET" in str(c)]
        assert len(update_calls) > 0
        args, kwargs = update_calls[0]
        assert "apelido=%s" in args[0]
        assert args[1][0] == "Novo Apelido do Celular"
