import sys
sys.stdout.reconfigure(encoding="utf-8")
content = open("templates/index.html", encoding="utf-8").read()
lines = content.splitlines()
print(f"Total lines: {len(lines)}")
for i in range(892, 902):
    line = lines[i]
    print(f"Line {i+1} ({len(line)} chars): {line}")
