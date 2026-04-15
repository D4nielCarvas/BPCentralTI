import re
from collections import Counter
content = open("templates/index.html", encoding="utf-8").read()
script = re.search(r"<script>(.*?)</script>", content, re.DOTALL).group(1)
# Encontra declarações de variáveis
decls = re.findall(r"(?:const|let|var|function)\s+([a-zA-Z0-9_]+)", script)
dupes = [k for k, v in Counter(decls).items() if v > 1]
print(f"Duplicate declarations: {dupes}")
