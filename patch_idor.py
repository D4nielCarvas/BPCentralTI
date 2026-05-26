import re

with open("blueprints/celulares.py", "r", encoding="utf-8") as f:
    content = f.read()

# Procura as funções get_celular... e insere o check
pattern = re.compile(
    r'(def get_[a-z_]+\(id_ativo: str\).*?with conn\.cursor\(\) as cur:\n\s+)(row = fetch_one\(cur, "SELECT \* FROM ([a-z_]+) WHERE id_ativo=%s", \(id_ativo,\)\))',
    re.DOTALL
)

def replacer(match):
    prefix = match.group(1)
    table = match.group(3)
    
    replacement = f"""from auth_utils import get_fazenda_nome_filter
            fazenda_nome = get_fazenda_nome_filter()
            if fazenda_nome:
                row = fetch_one(cur, "SELECT * FROM {table} WHERE id_ativo=%s AND fazenda=%s", (id_ativo, fazenda_nome))
            else:
                row = fetch_one(cur, "SELECT * FROM {table} WHERE id_ativo=%s", (id_ativo,))"""
                
    return prefix + replacement

new_content, count = pattern.subn(replacer, content)

print(f"Substituídas {count} funções de detalhe em celulares.py.")

with open("blueprints/celulares.py", "w", encoding="utf-8") as f:
    f.write(new_content)
