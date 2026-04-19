import sys

filename = "frontend/src/pages/Admin.tsx"

with open(filename, "r", encoding="utf-8", errors="surrogateescape") as f:
    lines = f.readlines()

# Line 420 is:             )}
# Line 421 is: 
# Line 422 is:               <motion.div ...
# We want to insert the condition before the motion.div

# Find the start of the users motion.div
for i, line in enumerate(lines):
    if i > 410 and '<motion.div key="users"' in line:
        # Insert the condition before this line
        lines.insert(i, "            {activeTab === 'users' && (\n")
        break

with open(filename, "w", encoding="utf-8", errors="surrogateescape") as f:
    f.writelines(lines)

print("Fixed condition opening!")
