"""Diagnostico somente leitura; nao corrige nem certifica protecao contra IDOR."""
import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

def detail_functions(content):
    tree = ast.parse(content)
    return [(node.name, node.lineno) for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name.startswith('get_')
            and any(argument.arg == 'id_ativo' for argument in node.args.args)]

def main():
    target = ROOT / 'blueprints' / 'celulares.py'
    for name, line in detail_functions(target.read_text(encoding='utf-8')):
        print(f'{target.name}:{line}: {name} - revisar autenticacao, autorizacao e isolamento por localidade.')
    print('Nenhum arquivo foi alterado. A antiga reescrita por regex foi desativada.')
    print('Esta listagem nao e uma auditoria completa. Valide rotas com testes entre usuarios e localidades diferentes.')

if __name__ == '__main__':
    main()
