import sys

filename = "frontend/src/pages/Admin.tsx"

with open(filename, "r", encoding="utf-8", errors="surrogateescape") as f:
    lines = f.readlines()

new_lines = lines[:422] + lines[431:]

with open(filename, "w", encoding="utf-8", errors="surrogateescape") as f:
    f.writelines(new_lines)

print("Fixed!")
