import re
content = open("templates/index.html", encoding="utf-8").read()
script = re.search(r"<script>(.*?)</script>", content, re.DOTALL).group(1)
# Encontra definições de variáveis
declared = set(re.findall(r"(?:const|let|var|function)\s+([a-zA-Z0-9_]+)", script))
# Encontra usos de variáveis (simplificado)
used = set(re.findall(r"\b([a-zA-Z_][a-zA-Z0-9_]*)\b", script))

known = {"window", "document", "console", "fetch", "JSON", "alert", "setTimeout", "clearTimeout", "setInterval", "clearInterval", "encodeURIComponent", "Array", "Object", "String", "Number", "Math", "navigator", "location", "localStorage"}
undeclared = []
for u in used:
    if u not in declared and u not in known and not u.startswith("load") and not u.startswith("open") and not u.startswith("edit") and not u.startswith("fld") and u not in ["FAZENDAS", "FAZENDA_SIGLA", "SIGLAS_SETOR_JS", "currentPage", "modalCtx", "filterState", "globalSearchFilter"]:
        # Filtra palavras comuns do JS e nomes que sabemos que existem
        if u not in ["r", "d", "el", "items", "item", "rows", "tb", "msg", "type", "ok", "res", "q", "opts", "method", "body", "path", "headers", "ct", "fmData", "fileInput", "fieldName", "label", "ctx", "showSave", "title", "bodyHtml", "mode", "id", "form", "data", "manual", "searchInput", "searchResults", "searchTimeout", "results", "map", "idAtivo", "tabela", "icons", "filename", "s", "iso", "parts", "baixo", "cls", "b", "bp", "eq", "tiBadge", "mn", "optsImp", "impressoras"]:
            undeclared.append(u)

print(f"Potentially undeclared/missing: {undeclared}")
