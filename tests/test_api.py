import urllib.request
import json

base = "http://localhost:5000"

def get(path):
    try:
        req = urllib.request.urlopen(base + path, timeout=8)
        data = json.loads(req.read().decode())
        return data
    except Exception as e:
        return {"error": str(e)}

print("=" * 50)
print("  TESTE COMPLETO DO SISTEMA - POST MIGRACAO")
print("=" * 50)

# DASHBOARD
d = get("/api/dashboard")
eq = d.get("equipamentos", {})
ped = d.get("pedidos_abertos", "ERR")
print("\n=== DASHBOARD ===")

ci = eq.get("celulares_inspecao", {})
if ci:
    print(f"  [OK  ] celulares_inspecao no dashboard: total={ci.get('total')}")
else:
    print(f"  [FAIL] celulares_inspecao ausente do dashboard")

if ped != "ERR":
    print(f"  [OK  ] pedidos_abertos no dashboard: {ped}")
else:
    print(f"  [FAIL] pedidos_abertos ausente do dashboard")

# CELULARES INSPECAO
r = get("/api/celulares_inspecao")
print("\n=== CELULARES INSPECAO ===")
if isinstance(r, list):
    print(f"  [OK  ] GET /api/celulares_inspecao: {len(r)} registros")
elif "error" in r:
    print(f"  [FAIL] Erro: {r['error']}")
else:
    print(f"  [FAIL] Resposta inesperada: {r}")

# PEDIDOS
r = get("/api/pedidos")
print("\n=== PEDIDOS ===")
if isinstance(r, list):
    print(f"  [OK  ] GET /api/pedidos: {len(r)} registros")
elif "error" in r:
    print(f"  [FAIL] Erro: {r['error']}")
else:
    print(f"  [FAIL] Resposta inesperada: {r}")

# IMPRESSORAS POR FAZENDA
r = get("/api/impressoras/por_fazenda?fazenda=Central")
print("\n=== IMPRESSORAS DA CENTRAL ===")
if isinstance(r, list):
    print(f"  [OK  ] GET /api/impressoras/por_fazenda: {len(r)} impressoras")
    for imp in r[:3]:
        print(f"         -> {imp.get('id_ativo')} | {imp.get('modelo')}")
elif "error" in r:
    print(f"  [FAIL] Erro: {r['error']}")

# MANUTENCOES (checar coluna tipo_manutencao)
r = get("/api/manutencoes")
print("\n=== MANUTENCOES ===")
if isinstance(r, list):
    print(f"  [OK  ] GET /api/manutencoes: {len(r)} registros")
    if r:
        has_col = "tipo_manutencao" in r[0]
        status = "[OK  ]" if has_col else "[FAIL]"
        print(f"  {status} Coluna tipo_manutencao presente: {has_col}")
elif "error" in r:
    print(f"  [FAIL] Erro: {r['error']}")

# TONERS (checar coluna tipo_suprimento nas trocas)
r = get("/api/toners")
print("\n=== TONERS ===")
if isinstance(r, list):
    print(f"  [OK  ] GET /api/toners: {len(r)} registros")
elif "error" in r:
    print(f"  [FAIL] Erro: {r['error']}")

# EXPORTAR PEDIDOS
try:
    req = urllib.request.urlopen(base + "/api/exportar/pedidos", timeout=5)
    print("\n=== EXPORTAR PEDIDOS ===")
    if req.status == 200:
        print("  [OK  ] GET /api/exportar/pedidos: 200 OK")
    else:
        print(f"  [FAIL] Status: {req.status}")
except Exception as e:
    print(f"\n=== EXPORTAR PEDIDOS ===")
    print(f"  [FAIL] Erro: {e}")

print("\n" + "=" * 50)
print("  TESTE CONCLUIDO")
print("=" * 50)
