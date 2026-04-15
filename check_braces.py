content = open("templates/index.html", encoding="utf-8").read()
script_content = content.split("<script>")[1].split("</script>")[0]
lines = script_content.split("\n")
stack = []
for i, line in enumerate(lines):
    for char in line:
        if char == "{": stack.append(i+1)
        elif char == "}":
            if stack: stack.pop()
            else: print(f"Extra closing brace at line {i+1}")
if stack:
    print(f"Unclosed braces opened at lines: {stack}")
