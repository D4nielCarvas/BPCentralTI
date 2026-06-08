import re

file_path = 'templates/index.html'

with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Substituir o bloco <style> ... </style> pela tag <link>
pattern = re.compile(r'<style>.*?</style>', re.DOTALL)
new_content = pattern.sub('<link rel="stylesheet" href="{{ url_for(\'static\', filename=\'css/admin.css\') }}">', content)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(new_content)

print('CSS removido com sucesso de index.html!')
