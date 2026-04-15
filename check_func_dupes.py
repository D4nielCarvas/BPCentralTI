import re
from collections import Counter
content = open("templates/index.html", encoding="utf-8").read()
funcs = re.findall(r"function\s+([a-zA-Z0-9_]+)", content)
dupes = [k for k, v in Counter(funcs).items() if v > 1]
print(f"Duplicate functions: {dupes}")
