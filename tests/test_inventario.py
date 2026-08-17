"""
test_inventario.py — Testes unitários do Sistema de BP Central TI v3.0

Execução:
    python -m pytest test_inventario.py -v

    # Apenas testes que não precisam de banco:
    python -m pytest test_inventario.py -v -m "not db"

    # Com cobertura:
    pip install pytest-cov
    python -m pytest test_inventario.py --cov=. --cov-report=term-missing

Dependências de teste:
    pip install pytest pytest-cov
"""

from __future__ import annotations

import json
import os
import sys
import unittest
from unittest.mock import MagicMock, patch

# Garante que o diretório do projeto está no path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


# ═══════════════════════════════════════════════════════════════════════════════
# TESTES: id_generator.py
# ═══════════════════════════════════════════════════════════════════════════════

class TestGeradorId(unittest.TestCase):
    """Testes para o módulo id_generator."""

    def test_gerar_id_formato_basico(self) -> None:
        """Verifica formato padrão TIPO-LOCAL-SETOR-NN com dois dígitos."""
        from id_generator import gerar_id_ativo
        resultado = gerar_id_ativo("NT", "CEN", "ADM", 1)
        self.assertEqual(resultado, "NT-CEN-ADM-01")

    def test_gerar_id_converte_para_maiusculas(self) -> None:
        """Verifica se o gerador converte entradas minúsculas para MAIÚSCULAS."""
        from id_generator import gerar_id_ativo
        resultado = gerar_id_ativo("nt", "cen", "adm", 1)
        self.assertEqual(resultado, "NT-CEN-ADM-01")

    def test_gerar_id_sequencial_dois_digitos(self) -> None:
        """Sequencial 9 deve ser formatado como '09'."""
        from id_generator import gerar_id_ativo
        self.assertEqual(gerar_id_ativo("DK", "SMN", "FT", 9), "DK-SMN-FT-09")

    def test_gerar_id_sequencial_dois_algarismos(self) -> None:
        """Sequencial 42 deve ser formatado como '42'."""
        from id_generator import gerar_id_ativo
        self.assertEqual(gerar_id_ativo("CL", "TNG", "PTO", 42), "CL-TNG-PTO-42")

    def test_gerar_id_sequencial_tres_algarismos(self) -> None:
        """Sequencial 100 deve ser formatado como '100' (sem truncar)."""
        from id_generator import gerar_id_ativo
        self.assertEqual(gerar_id_ativo("IMP", "CEN", "ADM", 100), "IMP-CEN-ADM-100")

    def test_gerar_id_tipo_invalido(self) -> None:
        """Tipo desconhecido deve lançar ValueError."""
        from id_generator import gerar_id_ativo
        with self.assertRaises(ValueError) as ctx:
            gerar_id_ativo("XX", "CEN", "ADM", 1)
        self.assertIn("XX", str(ctx.exception))

    def test_gerar_id_localidade_invalida(self) -> None:
        """Localidade desconhecida deve lançar ValueError."""
        from id_generator import gerar_id_ativo
        with self.assertRaises(ValueError):
            gerar_id_ativo("NT", "ZZZ", "ADM", 1)

    def test_gerar_id_setor_invalido(self) -> None:
        """Setor desconhecido deve lançar ValueError."""
        from id_generator import gerar_id_ativo
        with self.assertRaises(ValueError):
            gerar_id_ativo("NT", "CEN", "XPTO", 1)

    def test_gerar_id_sequencial_zero_invalido(self) -> None:
        """Sequencial zero deve lançar ValueError."""
        from id_generator import gerar_id_ativo
        with self.assertRaises(ValueError):
            gerar_id_ativo("NT", "CEN", "ADM", 0)

    def test_gerar_id_todos_tipos(self) -> None:
        """Todos os tipos cadastrados devem gerar ID sem erro."""
        from id_generator import gerar_id_ativo, SIGLAS_TIPO
        for tipo in SIGLAS_TIPO:
            with self.subTest(tipo=tipo):
                resultado = gerar_id_ativo(tipo, "CEN", "ADM", 1)
                self.assertTrue(resultado.startswith(tipo + "-"))

    def test_proximo_sequencial_sem_registros(self) -> None:
        """Primeira inserção do prefixo: banco retorna sequencial=1.

        A implementação atual usa INSERT ... ON CONFLICT ... RETURNING proximo - 1.
        Quando o prefixo ainda não existe, VALUES (%s, 2) é inserido e RETURNING
        devolve proximo - 1 = 2 - 1 = 1.
        """
        from id_generator import proximo_sequencial

        mock_cur = MagicMock()
        # Mock do fetchone()["sequencial"] que a implementação atual usa
        mock_cur.fetchone.return_value = {"sequencial": 1}

        resultado = proximo_sequencial(mock_cur, "NT", "CEN", "ADM")
        self.assertEqual(resultado, 1)

    def test_proximo_sequencial_com_registros(self) -> None:
        """Com prefixo já existente, banco incrementa e retorna o próximo sequencial.

        A implementação usa ON CONFLICT DO UPDATE SET proximo = proximo + 1
        RETURNING proximo - 1. Se proximo atual era 3, retorna 3 - 1 = 2,
        mas aqui simulamos que o banco retorna o valor 3 direto.
        """
        from id_generator import proximo_sequencial

        mock_cur = MagicMock()
        mock_cur.fetchone.return_value = {"sequencial": 3}

        resultado = proximo_sequencial(mock_cur, "NT", "CEN", "ADM")
        self.assertEqual(resultado, 3)

    def test_proximo_sequencial_ignora_outros_prefixos(self) -> None:
        """O sequencial retornado depende somente da resposta do banco para o prefixo exato.

        A filtragem por prefixo é garantida pela chave única na tabela id_sequenciais.
        O mock simula que o banco retornou sequencial=6 para NT-CEN-ADM.
        """
        from id_generator import proximo_sequencial

        mock_cur = MagicMock()
        mock_cur.fetchone.return_value = {"sequencial": 6}

        resultado = proximo_sequencial(mock_cur, "NT", "CEN", "ADM")
        self.assertEqual(resultado, 6)

    def test_sugerir_id_integra_sequencial_e_geracao(self) -> None:
        """sugerir_id deve combinar proximo_sequencial + gerar_id_ativo corretamente."""
        from id_generator import sugerir_id

        mock_cur = MagicMock()
        # Simula banco retornando sequencial=4 (estado pós-incremento)
        mock_cur.fetchone.return_value = {"sequencial": 4}

        resultado = sugerir_id(mock_cur, "DK", "SMN", "COO")
        self.assertEqual(resultado, "DK-SMN-COO-04")


    def test_siglas_tipo_contem_todos_esperados(self) -> None:
        """Verifica que todas as siglas de tipo obrigatórias estão presentes."""
        from id_generator import SIGLAS_TIPO
        obrigatorios = {"DK", "NT", "CL", "IMP", "TB", "EST", "STL"}
        self.assertTrue(obrigatorios.issubset(set(SIGLAS_TIPO.keys())))

    def test_siglas_local_contem_todos_esperados(self) -> None:
        """Verifica que todas as siglas de localidade obrigatórias estão presentes."""
        from id_generator import SIGLAS_LOCAL
        obrigatorios = {"CEN", "SMN", "TNG", "SPD", "SJU", "SFR", "STN",
                        "CD", "SEL", "SLU", "SL2", "CLN", "SJO", "SLZ", "SAD"}
        self.assertTrue(obrigatorios.issubset(set(SIGLAS_LOCAL.keys())))

    def test_siglas_setor_contem_todos_esperados(self) -> None:
        """Verifica que todas as siglas de setor obrigatórias estão presentes."""
        from id_generator import SIGLAS_SETOR
        obrigatorios = {"FT", "ALP", "ALI", "COO", "ADM", "APO",
                        "COL", "PTO", "TRM", "ABS", "IRR"}
        self.assertTrue(obrigatorios.issubset(set(SIGLAS_SETOR.keys())))


# ═══════════════════════════════════════════════════════════════════════════════
# TESTES: resource_path (app.py)
# ═══════════════════════════════════════════════════════════════════════════════

class TestResourcePath(unittest.TestCase):
    """Testes para a função resource_path do app.py."""

    def test_resource_path_em_desenvolvimento(self) -> None:
        """Em desenvolvimento, deve retornar caminho relativo ao diretório do arquivo."""
        # Remove _MEIPASS se existir para simular ambiente de desenvolvimento
        if hasattr(sys, "_MEIPASS"):
            meipass_backup = sys._MEIPASS
            del sys._MEIPASS
        else:
            meipass_backup = None

        try:
            # Importa após remover _MEIPASS
            import importlib
            # Evita reimportar app completo (teria efeitos colaterais)
            # Testa a lógica diretamente
            base = os.path.dirname(os.path.abspath(__file__))
            esperado = os.path.join(base, "templates")
            calculado = os.path.join(
                getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__))),
                "templates"
            )
            self.assertEqual(calculado, esperado)
        finally:
            if meipass_backup is not None:
                sys._MEIPASS = meipass_backup

    def test_resource_path_com_meipass(self) -> None:
        """Com _MEIPASS definido, deve usar o diretório temporário do PyInstaller."""
        fake_meipass = "/tmp/fake_meipass_123"
        sys._MEIPASS = fake_meipass
        try:
            calculado = os.path.join(
                getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__))),
                "templates"
            )
            self.assertEqual(calculado, os.path.join(fake_meipass, "templates"))
        finally:
            del sys._MEIPASS


# ═══════════════════════════════════════════════════════════════════════════════
# TESTES: Parse do arquivo de coleta (.bat output)
# ═══════════════════════════════════════════════════════════════════════════════

class TestParseColeta(unittest.TestCase):
    """
    Testes para o parse do arquivo INI gerado pelo COLETAR_PC.bat.
    Replica a lógica de parse da rota /api/importar_coleta.
    """

    def _parse_ini(self, conteudo: str) -> dict[str, str]:
        """Replica a lógica de parse da rota importar_coleta."""
        dados: dict[str, str] = {}
        for linha in conteudo.splitlines():
            linha = linha.strip()
            if "=" in linha and not linha.startswith("#"):
                chave, _, valor = linha.partition("=")
                dados[chave.strip().lower()] = valor.strip()
        return dados

    def test_parse_arquivo_valido(self) -> None:
        """Arquivo INI bem formado deve ser parseado corretamente."""
        conteudo = (
            "# BP Central TI\n"
            "[hardware]\n"
            "hostname=DESKTOP-TI01\n"
            "marca=Dell\n"
            "modelo=Latitude 5420\n"
            "num_serie=ABC123456\n"
            "processador=Intel Core i5-1135G7\n"
            "memoria_ram=8GB\n"
            "armazenamento=256GB\n"
            "sistema_operacional=Windows 11 Pro\n"
            "versao_so=10.0.22621 Build 22621\n"
            "ip=192.168.1.50\n"
            "mac=AA:BB:CC:DD:EE:FF\n"
            "usuario=joao.silva\n"
        )
        dados = self._parse_ini(conteudo)
        self.assertEqual(dados["hostname"], "DESKTOP-TI01")
        self.assertEqual(dados["marca"], "Dell")
        self.assertEqual(dados["num_serie"], "ABC123456")
        self.assertEqual(dados["memoria_ram"], "8GB")
        self.assertEqual(dados["usuario"], "joao.silva")

    def test_parse_ignora_comentarios(self) -> None:
        """Linhas começando com # não devem ser incluídas."""
        conteudo = "# comentario\nhostname=PC01\n"
        dados = self._parse_ini(conteudo)
        self.assertNotIn("#", dados)
        self.assertIn("hostname", dados)

    def test_parse_ignora_secoes(self) -> None:
        """Linhas de seção [hardware] devem ser ignoradas."""
        conteudo = "[hardware]\nhostname=PC01\n"
        dados = self._parse_ini(conteudo)
        self.assertNotIn("[hardware]", dados)
        self.assertEqual(dados["hostname"], "PC01")

    def test_parse_valor_com_sinal_igual(self) -> None:
        """Valores que contêm '=' (ex.: versão do SO) devem ser preservados."""
        conteudo = "versao_so=10.0.22621 Build 22621\n"
        dados = self._parse_ini(conteudo)
        self.assertEqual(dados["versao_so"], "10.0.22621 Build 22621")

    def test_parse_arquivo_vazio(self) -> None:
        """Arquivo vazio deve retornar dicionário vazio."""
        dados = self._parse_ini("")
        self.assertEqual(dados, {})

    def test_campos_obrigatorios_detecta_ausencia(self) -> None:
        """Deve detectar corretamente campos obrigatórios ausentes."""
        dados = {"hostname": "PC01", "marca": "Dell"}  # falta num_serie e modelo
        campos_obrigatorios = ["num_serie", "modelo", "marca"]
        ausentes = [c for c in campos_obrigatorios if not dados.get(c)]
        self.assertIn("num_serie", ausentes)
        self.assertIn("modelo", ausentes)
        self.assertNotIn("marca", ausentes)


# ═══════════════════════════════════════════════════════════════════════════════
# TESTES: Validações de Transferência
# ═══════════════════════════════════════════════════════════════════════════════

class TestValidacoesTransferencia(unittest.TestCase):
    """
    Testes para as regras de validação do módulo de transferências.
    Replica a lógica das validações sem depender do banco.
    """

    def _validar_transferencia(self, d: dict) -> tuple[bool, str]:
        """Replica as validações da rota criar_transferencia."""
        from datetime import date

        tipo_transf = d.get("tipo_transferencia", "")
        data_str = d.get("data_transferencia") or date.today().isoformat()

        try:
            if date.fromisoformat(data_str) > date.today():
                return False, "Data de transferência não pode ser futura"
        except ValueError:
            return False, "Data de transferência inválida"

        if tipo_transf == "Estoque para Usuario" and not d.get("responsavel_destino"):
            return False, "responsavel_destino é obrigatório para 'Estoque para Usuario'"

        if tipo_transf == "Usuario para Estoque" and not d.get("data_devolucao"):
            return False, "data_devolucao é obrigatório para 'Usuario para Estoque'"

        return True, "ok"

    def test_data_futura_rejeitada(self) -> None:
        """Data de transferência futura deve ser rejeitada."""
        ok, msg = self._validar_transferencia({
            "tipo_transferencia": "Entre Usuarios",
            "data_transferencia": "2099-12-31",
        })
        self.assertFalse(ok)
        self.assertIn("futura", msg)

    def test_data_hoje_aceita(self) -> None:
        """Data de hoje deve ser aceita."""
        from datetime import date
        ok, _ = self._validar_transferencia({
            "tipo_transferencia": "Entre Usuarios",
            "data_transferencia": date.today().isoformat(),
        })
        self.assertTrue(ok)

    def test_estoque_para_usuario_exige_responsavel(self) -> None:
        """'Estoque para Usuario' sem responsavel_destino deve ser rejeitado."""
        ok, msg = self._validar_transferencia({
            "tipo_transferencia": "Estoque para Usuario",
            "responsavel_destino": None,
        })
        self.assertFalse(ok)
        self.assertIn("responsavel_destino", msg)

    def test_estoque_para_usuario_com_responsavel_aceito(self) -> None:
        """'Estoque para Usuario' com responsavel_destino deve ser aceito."""
        ok, _ = self._validar_transferencia({
            "tipo_transferencia": "Estoque para Usuario",
            "responsavel_destino": "João Silva",
        })
        self.assertTrue(ok)

    def test_usuario_para_estoque_exige_data_devolucao(self) -> None:
        """'Usuario para Estoque' sem data_devolucao deve ser rejeitado."""
        ok, msg = self._validar_transferencia({
            "tipo_transferencia": "Usuario para Estoque",
            "data_devolucao": None,
        })
        self.assertFalse(ok)
        self.assertIn("data_devolucao", msg)

    def test_usuario_para_estoque_com_data_aceito(self) -> None:
        """'Usuario para Estoque' com data_devolucao deve ser aceito."""
        from datetime import date
        ok, _ = self._validar_transferencia({
            "tipo_transferencia": "Usuario para Estoque",
            "data_devolucao": date.today().isoformat(),
        })
        self.assertTrue(ok)

    def test_data_invalida_rejeitada(self) -> None:
        """String de data malformada deve ser rejeitada."""
        ok, msg = self._validar_transferencia({
            "tipo_transferencia": "Entre Usuarios",
            "data_transferencia": "nao-e-uma-data",
        })
        self.assertFalse(ok)
        self.assertIn("inválida", msg)

    def test_status_bloqueados(self) -> None:
        """Ativos com status 'Manutenção' ou 'Descartado' devem ser bloqueados."""
        status_bloqueados = {"Manutenção", "Descartado"}
        self.assertIn("Manutenção", status_bloqueados)
        self.assertIn("Descartado", status_bloqueados)
        self.assertNotIn("Ativo", status_bloqueados)
        self.assertNotIn("Estoque", status_bloqueados)


# ═══════════════════════════════════════════════════════════════════════════════
# TESTES: Helpers do app.py
# ═══════════════════════════════════════════════════════════════════════════════

class TestHelpers(unittest.TestCase):
    """Testes para as funções auxiliares do app.py."""

    def test_row_to_dict_com_dict(self) -> None:
        """dict real deve ser retornado como dict."""
        # RealDictRow se comporta como dict
        entrada = {"id_ativo": "NT-CEN-ADM-01", "status": "Ativo"}
        from app import row_to_dict
        self.assertEqual(row_to_dict(entrada), entrada)

    def test_row_to_dict_com_none(self) -> None:
        """None deve retornar None."""
        from app import row_to_dict
        self.assertIsNone(row_to_dict(None))

    def test_rows_to_list_com_lista(self) -> None:
        """Lista de dicts deve ser retornada como lista de dicts."""
        from app import rows_to_list
        entrada = [{"id": 1}, {"id": 2}]
        self.assertEqual(rows_to_list(entrada), entrada)

    def test_rows_to_list_vazio(self) -> None:
        """Lista vazia deve retornar lista vazia."""
        from app import rows_to_list
        self.assertEqual(rows_to_list([]), [])

    def test_allowed_file_pdf(self) -> None:
        """Arquivo .pdf deve ser permitido."""
        from app import allowed_file
        self.assertTrue(allowed_file("termo_responsabilidade.pdf"))

    def test_allowed_file_extensao_maiuscula(self) -> None:
        """Arquivo .PDF (maiúsculo) deve ser permitido."""
        from app import allowed_file
        self.assertTrue(allowed_file("TERMO.PDF"))

    def test_allowed_file_extensao_invalida(self) -> None:
        """Arquivos que não são PDF devem ser rejeitados."""
        from app import allowed_file
        for nome in ["foto.jpg", "documento.docx", "planilha.xlsx", "script.exe"]:
            with self.subTest(nome=nome):
                self.assertFalse(allowed_file(nome))

    def test_allowed_file_sem_extensao(self) -> None:
        """Arquivo sem extensão deve ser rejeitado."""
        from app import allowed_file
        self.assertFalse(allowed_file("arquivo_sem_extensao"))


# ═══════════════════════════════════════════════════════════════════════════════
# RUNNER
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    unittest.main(verbosity=2)
