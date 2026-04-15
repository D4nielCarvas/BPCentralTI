import re
content = open("templates/index.html", encoding="utf-8").read()
script = re.search(r"<script>(.*?)</script>", content, re.DOTALL).group(1)
for i, char in enumerate(script):
    if ord(char) > 127:
        # Permite emojis comuns e caracteres PT-BR se estiverem em strings ou comentários
        # Mas vamos apenas listar para conferir
        context = script[max(0, i-20):i+20]
        print(f"Non-ASCII at pos {i}: '{char}' (ord {ord(char)}) context: {context}")
