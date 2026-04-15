"""Script de verificação dos endpoints implementados nas 9 melhorias."""
import urllib.request
import json

BASE = "http://localhost:5000"

TESTS = [
    ("GET /api/utils/gerar-id-turma", f"{BASE}/api/utils/gerar-id-turma"),
    ("GET /api/celulares_turma",       f"{BASE}/api/celulares_turma"),
    ("GET /api/dashboard",             f"{BASE}/api/dashboard"),
    ("GET /api/starlink",              f"{BASE}/api/starlink"),
    ("GET /api/pedidos",               f"{BASE}/api/pedidos"),
    ("GET /api/transferencias",        f"{BASE}/api/transferencias"),
    ("GET /api/busca?q=CL",            f"{BASE}/api/busca?q=CL"),
    ("GET /api/exportar/celulares_turma", f"{BASE}/api/exportar/celulares_turma"),
]

ok = 0
fail = 0

for name, url in TESTS:
    try:
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=6) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            data = json.loads(raw)
            extra = ""
            if isinstance(data, dict) and "id_sugerido" in data:
                extra = f"  ->  id_sugerido: {data['id_sugerido']}"
            elif isinstance(data, dict) and "ok" in data and not data["ok"]:
                extra = f"  ->  msg: {data.get('msg', '')}"
            print(f"OK   {name}{extra}")
            ok += 1
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")[:200]
        print(f"HTTP {e.code}  {name}  ->  {body}")
        fail += 1
    except Exception as exc:
        print(f"FAIL  {name}  ->  {exc}")
        fail += 1

print(f"\nResultado: {ok} OK  /  {fail} falha(s)")
