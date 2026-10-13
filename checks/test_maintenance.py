"""Testes isolados dos utilitarios, sem importar Flask ou acessar banco."""
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]

def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

strip = load('maintenance_strip', ROOT / 'scripts' / 'maintenance' / 'strip_css.py')
audit = load('maintenance_audit', ROOT / 'scripts' / 'maintenance' / 'audit_idor.py')

class MaintenanceTests(unittest.TestCase):
    def test_single_style_preserves_surroundings(self):
        result = strip.transform('ANTES<style>body {color:red}</style>DEPOIS')
        self.assertEqual(result, 'ANTES' + strip.LINK + 'DEPOIS')

    def test_no_style_is_rejected(self):
        with self.assertRaises(ValueError):
            strip.transform('<html></html>')

    def test_multiple_styles_are_rejected(self):
        with self.assertRaises(ValueError):
            strip.transform('<style>a</style><style>b</style>')

    def test_existing_reference_is_rejected(self):
        with self.assertRaises(ValueError):
            strip.transform('css/admin.css<style>a</style>')

    def test_audit_only_lists_matching_functions(self):
        content = 'def get_celular(id_ativo):\n    pass\ndef outro(id_ativo):\n    pass\ndef get_lista():\n    pass\n'
        self.assertEqual(audit.detail_functions(content), [('get_celular', 1)])

if __name__ == '__main__':
    unittest.main()
