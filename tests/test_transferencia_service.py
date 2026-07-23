"""
tests/test_transferencia_service.py — Testes unitários do sistema de transferências.

Cobertura:
    - Validação de payload (TransferenciaService._validar)
    - Todos os 4 tipos de transferência via handlers isolados
    - IdRenameService (lógica pura, sem banco)
    - Exceções de domínio (TransferenciaError, AtivoNaoEncontradoError, StatusBloqueadoError)

Estratégia:
    Todos os testes são UNITÁRIOS — sem dependência de banco ou Flask.
    O banco é substituído por Mock/MagicMock onde necessário.
    Os handlers recebem um cursor mockado e seus SQL são verificados via assert_called.

Complexidade dos testes: O(1) — sem I/O real.
"""

from __future__ import annotations

import unittest
from datetime import date, timedelta
from unittest.mock import MagicMock, patch, call


# ═══════════════════════════════════════════════════════════════════════════════
# TESTES: Validação de payload (TransferenciaService._validar)
# ═══════════════════════════════════════════════════════════════════════════════

class TestTransferenciaServiceValidacao(unittest.TestCase):
    """Testa todas as regras de validação de negócio — sem banco de dados."""

    def setUp(self):
        from services.transferencia_service import TransferenciaService
        self.service = TransferenciaService()

    def _validar(self, payload: dict):
        """Helper: chama _validar e retorna (ok: bool, msg: str)."""
        from services.transferencia_service import TransferenciaError
        try:
            self.service._validar(payload)
            return True, "ok"
        except TransferenciaError as exc:
            return False, str(exc)

    # ── Tipo de equipamento ────────────────────────────────────────────────────

    def test_tipo_equipamento_invalido_rejeitado(self):
        ok, msg = self._validar({"tipo_equipamento": "Geladeira", "id_ativo": "X"})
        self.assertFalse(ok)
        self.assertIn("inválido", msg)

    def test_tipo_equipamento_valido_aceito(self):
        ok, _ = self._validar({
            "tipo_equipamento": "Celular",
            "id_ativo": "CL-CEN-ADM-01",
            "tipo_transferencia": "Estoque para Usuario",
            "responsavel_destino": "João Silva",
        })
        self.assertTrue(ok)

    # ── Data de transferência ──────────────────────────────────────────────────

    def test_data_futura_rejeitada(self):
        ok, msg = self._validar({
            "tipo_equipamento": "Celular",
            "id_ativo": "X",
            "data_transferencia": "2099-12-31",
        })
        self.assertFalse(ok)
        self.assertIn("futura", msg)

    def test_data_hoje_aceita(self):
        ok, _ = self._validar({
            "tipo_equipamento": "Celular",
            "id_ativo": "X",
            "data_transferencia": date.today().isoformat(),
            "tipo_transferencia": "Estoque para Usuario",
            "responsavel_destino": "Maria",
        })
        self.assertTrue(ok)

    def test_data_passada_aceita(self):
        ontem = (date.today() - timedelta(days=1)).isoformat()
        ok, _ = self._validar({
            "tipo_equipamento": "Celular",
            "id_ativo": "X",
            "data_transferencia": ontem,
            "tipo_transferencia": "Estoque para Usuario",
            "responsavel_destino": "Maria",
        })
        self.assertTrue(ok)

    def test_data_invalida_rejeitada(self):
        ok, msg = self._validar({
            "tipo_equipamento": "Celular",
            "id_ativo": "X",
            "data_transferencia": "nao-e-uma-data",
        })
        self.assertFalse(ok)
        self.assertIn("inválida", msg)

    def test_data_ausente_usa_hoje_sem_erro(self):
        """data_transferencia ausente deve usar today() e não rejeitar."""
        ok, _ = self._validar({
            "tipo_equipamento": "Celular",
            "id_ativo": "X",
            "tipo_transferencia": "Estoque para Usuario",
            "responsavel_destino": "João",
        })
        self.assertTrue(ok)

    # ── Estoque para Usuario ───────────────────────────────────────────────────

    def test_estoque_usuario_sem_responsavel_rejeitado(self):
        ok, msg = self._validar({
            "tipo_equipamento": "Celular",
            "id_ativo": "X",
            "tipo_transferencia": "Estoque para Usuario",
        })
        self.assertFalse(ok)
        self.assertIn("responsavel_destino", msg)

    def test_estoque_usuario_com_responsavel_aceito(self):
        ok, _ = self._validar({
            "tipo_equipamento": "Celular",
            "id_ativo": "X",
            "tipo_transferencia": "Estoque para Usuario",
            "responsavel_destino": "João Silva",
        })
        self.assertTrue(ok)

    # ── Usuario para Estoque ───────────────────────────────────────────────────

    def test_usuario_estoque_sem_data_devolucao_rejeitado(self):
        ok, msg = self._validar({
            "tipo_equipamento": "Celular",
            "id_ativo": "X",
            "tipo_transferencia": "Usuario para Estoque",
        })
        self.assertFalse(ok)
        self.assertIn("data_devolucao", msg)

    def test_usuario_estoque_com_data_aceito(self):
        ok, _ = self._validar({
            "tipo_equipamento": "Celular",
            "id_ativo": "X",
            "tipo_transferencia": "Usuario para Estoque",
            "data_devolucao": date.today().isoformat(),
        })
        self.assertTrue(ok)

    # ── Usuario para Usuario ───────────────────────────────────────────────────

    def test_usuario_usuario_sem_responsavel_rejeitado(self):
        ok, msg = self._validar({
            "tipo_equipamento": "Celular",
            "id_ativo": "X",
            "tipo_transferencia": "Usuario para Usuario",
        })
        self.assertFalse(ok)
        self.assertIn("responsavel_destino", msg)

    def test_usuario_usuario_com_responsavel_aceito(self):
        ok, _ = self._validar({
            "tipo_equipamento": "Celular",
            "id_ativo": "X",
            "tipo_transferencia": "Usuario para Usuario",
            "responsavel_destino": "Maria",
        })
        self.assertTrue(ok)

    # ── Usuario para Turma ─────────────────────────────────────────────────────

    def test_usuario_turma_sem_turma_destino_rejeitado(self):
        ok, msg = self._validar({
            "tipo_equipamento": "Celular",
            "id_ativo": "X",
            "tipo_transferencia": "Usuario para Turma",
        })
        self.assertFalse(ok)
        self.assertIn("turma_destino", msg)

    def test_usuario_turma_com_turma_aceito(self):
        ok, _ = self._validar({
            "tipo_equipamento": "Celular",
            "id_ativo": "X",
            "tipo_transferencia": "Usuario para Turma",
            "turma_destino": "Turma A",
        })
        self.assertTrue(ok)

    # ── Status bloqueados ──────────────────────────────────────────────────────

    def test_status_bloqueados_definidos_corretamente(self):
        from services.transferencia_service import _STATUS_BLOQUEADOS
        self.assertIn("Manutenção", _STATUS_BLOQUEADOS)
        self.assertIn("Descartado", _STATUS_BLOQUEADOS)
        self.assertNotIn("Ativo", _STATUS_BLOQUEADOS)
        self.assertNotIn("Estoque", _STATUS_BLOQUEADOS)


# ═══════════════════════════════════════════════════════════════════════════════
# TESTES: Handlers (Strategy Pattern)
# ═══════════════════════════════════════════════════════════════════════════════

class TestHandlerUsuarioEstoque(unittest.TestCase):
    """Handler: Usuário → Estoque."""

    def test_executar_faz_update_correto(self):
        from handlers.handler_usuario_estoque import UsuarioParaEstoqueHandler
        handler = UsuarioParaEstoqueHandler()
        cur = MagicMock()

        id_retornado = handler.executar(
            cur,
            id_ativo="CL-CEN-ADM-01",
            tabela="celulares",
            ativo_atual={"responsavel": "João Silva"},
            payload={"data_devolucao": "2026-07-23"},
        )

        self.assertEqual(id_retornado, "CL-CEN-ADM-01")
        sql_executado = cur.execute.call_args[0][0]
        self.assertIn("status", sql_executado)
        self.assertIn("Estoque", sql_executado)
        self.assertIn("responsavel", sql_executado)

    def test_executar_retorna_mesmo_id(self):
        from handlers.handler_usuario_estoque import UsuarioParaEstoqueHandler
        handler = UsuarioParaEstoqueHandler()
        cur = MagicMock()
        id_ret = handler.executar(cur, "QUALQUER-ID", "celulares", {}, {"data_devolucao": "2026-07-01"})
        self.assertEqual(id_ret, "QUALQUER-ID")


class TestHandlerEstoqueUsuario(unittest.TestCase):
    """Handler: Estoque → Usuário."""

    def test_executar_usa_data_do_payload(self):
        """FIX: data_entrega deve vir de data_transferencia, não de date.today()."""
        from handlers.handler_estoque_usuario import EstoqueParaUsuarioHandler
        handler = EstoqueParaUsuarioHandler()
        cur = MagicMock()

        handler.executar(
            cur,
            id_ativo="CL-CEN-ADM-01",
            tabela="celulares",
            ativo_atual={"responsavel": None},
            payload={
                "responsavel_destino": "Maria",
                "fazenda_destino": "Central",
                "setor_destino": "Administrativo",
                "data_transferencia": "2026-07-01",  # data retroativa
            },
        )

        params = cur.execute.call_args[0][1]
        # data_transferencia deve ser o 4º parâmetro (data_entrega)
        self.assertEqual(params[3], "2026-07-01")

    def test_executar_seta_status_ativo(self):
        from handlers.handler_estoque_usuario import EstoqueParaUsuarioHandler
        handler = EstoqueParaUsuarioHandler()
        cur = MagicMock()
        handler.executar(cur, "X", "celulares", {}, {
            "responsavel_destino": "X",
            "data_transferencia": "2026-07-23",
        })
        sql = cur.execute.call_args[0][0]
        self.assertIn("'Ativo'", sql)
        self.assertIn("data_devolucao   = NULL", sql)


class TestHandlerUsuarioUsuario(unittest.TestCase):
    """Handler: Usuário → Usuário."""

    def test_executar_atualiza_responsavel(self):
        from handlers.handler_usuario_usuario import UsuarioParaUsuarioHandler
        handler = UsuarioParaUsuarioHandler()
        cur = MagicMock()

        id_ret = handler.executar(
            cur,
            id_ativo="CL-CEN-ADM-01",
            tabela="celulares",
            ativo_atual={"responsavel": "João"},
            payload={
                "responsavel_destino": "Maria",
                "fazenda_destino": "São Manoel",
                "setor_destino": "Agrícola",
                "data_transferencia": "2026-07-23",
            },
        )
        self.assertEqual(id_ret, "CL-CEN-ADM-01")
        params = cur.execute.call_args[0][1]
        self.assertEqual(params[0], "Maria")         # responsavel
        self.assertEqual(params[1], "São Manoel")    # fazenda
        self.assertEqual(params[-1], "CL-CEN-ADM-01")  # WHERE id_ativo


class TestHandlerUsuarioTurmaUpdateSimples(unittest.TestCase):
    """Handler: Usuário → Turma (ativo já é celular_turma/ponto)."""

    def test_update_simples_em_celulares_turma(self):
        from handlers.handler_usuario_turma import UsuarioParaTurmaHandler
        handler = UsuarioParaTurmaHandler()
        cur = MagicMock()

        id_ret = handler.executar(
            cur,
            id_ativo="CL-TRM-01",
            tabela="celulares_turma",
            ativo_atual={"responsavel": "Turma Velha"},
            payload={
                "turma_destino": "Turma B",
                "fazenda_destino": "Central",
                "setor_destino": "Turma",
                "data_transferencia": "2026-07-23",
            },
        )
        self.assertEqual(id_ret, "CL-TRM-01")
        sql = cur.execute.call_args[0][0]
        self.assertIn("num_turma", sql)


# ═══════════════════════════════════════════════════════════════════════════════
# TESTES: IdRenameService (lógica pura, sem banco)
# ═══════════════════════════════════════════════════════════════════════════════

class TestIdRenameService(unittest.TestCase):
    """Testa a lógica de decisão de renomeação — sem banco real."""

    def setUp(self):
        from services.id_rename_service import IdRenameService
        self.svc = IdRenameService()

    def test_nao_renomeia_usuario_para_estoque(self):
        """Tipo 'Usuario para Estoque' nunca deve renomear o id."""
        cur = MagicMock()
        resultado = self.svc.renomear_se_necessario(
            cur, "CL-CEN-ADM-01", "Celular", "celulares",
            {"tipo_transferencia": "Usuario para Estoque",
             "fazenda_destino": "São Manoel", "setor_destino": "Agrícola"},
            transf_id=99,
        )
        self.assertEqual(resultado, "CL-CEN-ADM-01")
        cur.execute.assert_not_called()

    def test_nao_renomeia_celular_turma(self):
        """Celulares Turma (CL-TRM-*) nunca têm ID renomeado."""
        cur = MagicMock()
        resultado = self.svc.renomear_se_necessario(
            cur, "CL-TRM-01", "Celular Turma", "celulares_turma",
            {"tipo_transferencia": "Usuario para Usuario",
             "fazenda_destino": "Central", "setor_destino": "Turma"},
            transf_id=99,
        )
        self.assertEqual(resultado, "CL-TRM-01")
        cur.execute.assert_not_called()

    def test_nao_renomeia_sem_fazenda_destino(self):
        """Sem fazenda_destino, não há base para gerar novo ID."""
        cur = MagicMock()
        resultado = self.svc.renomear_se_necessario(
            cur, "CL-CEN-ADM-01", "Celular", "celulares",
            {"tipo_transferencia": "Usuario para Usuario",
             "fazenda_destino": "", "setor_destino": "Agrícola"},
            transf_id=99,
        )
        self.assertEqual(resultado, "CL-CEN-ADM-01")

    def test_sigla_tipo_mapa_sem_typo(self):
        """Garante que 'Celular Inspeção' (com ç) está no mapa — sem o bug do typo."""
        from services.id_rename_service import _SIGLA_TIPO_MAP
        self.assertIn("Celular Inspeção", _SIGLA_TIPO_MAP)
        self.assertNotIn("Celular Inspecão", _SIGLA_TIPO_MAP)  # typo antigo

    def test_guards_de_colisao_passam(self):
        """Os asserts de colisão em SIGLAS_LOCAL/SETOR não devem falhar."""
        # Se chegou aqui sem AssertionError, os guards passaram no import
        import services.id_rename_service  # noqa: F401


# ═══════════════════════════════════════════════════════════════════════════════
# TESTES: Exceções de domínio
# ═══════════════════════════════════════════════════════════════════════════════

class TestExcecoesDeDominio(unittest.TestCase):
    """Garante que as exceções customizadas são subclasses corretas."""

    def test_transferencia_error_e_exception(self):
        from services.transferencia_service import TransferenciaError
        self.assertTrue(issubclass(TransferenciaError, Exception))

    def test_ativo_nao_encontrado_e_lookup_error(self):
        from services.transferencia_service import AtivoNaoEncontradoError
        self.assertTrue(issubclass(AtivoNaoEncontradoError, LookupError))

    def test_status_bloqueado_e_exception(self):
        from services.transferencia_service import StatusBloqueadoError
        self.assertTrue(issubclass(StatusBloqueadoError, Exception))


# ═══════════════════════════════════════════════════════════════════════════════
# TESTES: Legado — mantidos para não quebrar CI
# ═══════════════════════════════════════════════════════════════════════════════

class TestValidacoesTransferenciaLegado(unittest.TestCase):
    """
    Mantém compatibilidade com os testes originais de test_inventario.py.
    Usa o novo TransferenciaService em vez da lógica inline.
    """

    def setUp(self):
        from services.transferencia_service import TransferenciaService, TransferenciaError
        self.service = TransferenciaService()
        self.TransferenciaError = TransferenciaError

    def _validar(self, d: dict):
        try:
            self.service._validar(d)
            return True, "ok"
        except self.TransferenciaError as e:
            return False, str(e)

    def test_data_futura_rejeitada(self):
        ok, msg = self._validar({
            "tipo_equipamento": "Celular",
            "id_ativo": "X",
            "tipo_transferencia": "Usuario para Usuario",
            "data_transferencia": "2099-12-31",
        })
        self.assertFalse(ok)
        self.assertIn("futura", msg)

    def test_data_invalida_rejeitada(self):
        ok, msg = self._validar({
            "tipo_equipamento": "Celular",
            "id_ativo": "X",
            "tipo_transferencia": "Usuario para Usuario",
            "data_transferencia": "nao-e-uma-data",
        })
        self.assertFalse(ok)
        self.assertIn("inválida", msg)


if __name__ == "__main__":
    unittest.main(verbosity=2)
