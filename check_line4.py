import sys
sys.stdout.reconfigure(encoding="utf-8")
content = open(r"dist\InventarioTI\_internal\templates\index.html", encoding="utf-8").read()
lines = content.splitlines()
print(f"Total lines: {len(lines)}")
print(f"\n=== Linha 896 ===")
print(repr(lines[895]))
print(f"\n=== Linhas 888-910 ===")
for i in range(887, 910):
    print(f"  {i+1}: {lines[i][:100]}")
