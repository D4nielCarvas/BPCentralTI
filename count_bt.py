import sys
sys.stdout.reconfigure(encoding="utf-8")
content = open(r"dist\InventarioTI\_internal\templates\index.html", encoding="utf-8").read()
lines = content.splitlines()

# Find the <script> tag
script_start = 0
for i, line in enumerate(lines):
    if "<script>" in line:
        script_start = i
        break

print(f"Script starts at line {script_start + 1}")

# Count backticks from script start to line 895 (0-indexed), looking for odd count
bt_count = 0
for i in range(script_start, 895):
    line = lines[i]
    for j, c in enumerate(line):
        if c == '`':
            bt_count += 1
            # Print each backtick found
            preview = line[max(0,j-20):j+20].encode('ascii', 'replace').decode()
            print(f"  Backtick #{bt_count} at line {i+1}, col {j}: ...{preview}...")

print(f"\nTotal backticks up to line 895: {bt_count}")
print(f"Parity: {'ODD - template literal is OPEN' if bt_count % 2 == 1 else 'EVEN - all closed'}")
