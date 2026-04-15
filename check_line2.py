import sys
sys.stdout.reconfigure(encoding="utf-8")
content = open("templates/index.html", encoding="utf-8").read()
lines = content.splitlines()
print(f"Total lines: {len(lines)}")
# Print lines around 896 as ASCII-safe
for i in range(893, 900):
    line = lines[i]
    line_ascii = line.encode('ascii', errors='replace').decode('ascii')
    print(f"Line {i+1} ({len(line)} chars): {repr(line_ascii)}")
