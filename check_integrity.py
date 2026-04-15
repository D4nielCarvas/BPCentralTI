import sys
content = open("templates/index.html", "rb").read()
if b"\xef\xbb\xbf" in content[:3]:
    print("UTF-8 BOM detected!")
else:
    print("No BOM detected.")

# Check for non-breaking space (0xA0) or other weirdness
pos = content.find(b"\xa0")
if pos != -1:
    print(f"Non-breaking space at pos {pos}")
pos = content.find(b"\x00")
if pos != -1:
    print(f"Null byte at pos {pos}")
