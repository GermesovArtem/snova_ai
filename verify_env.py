import os
from dotenv import load_dotenv

print("\n" + "="*50)
print("🔍 ENVIRONMENT VERIFICATION SCRIPT")
print("="*50)

# 1. Check if .env file exists in the current directory
if os.path.exists(".env"):
    print("✅ .env file found in /app/")
else:
    print("❌ .env file NOT FOUND in /app/!")

# 2. Try to load it
load_dotenv()

# 3. Check variables
vars_to_check = ["DATABASE_URL", "POSTGRES_USER", "POSTGRES_PASSWORD", "POSTGRES_DB"]

for var in vars_to_check:
    val = os.getenv(var)
    if val:
        # Mask password
        if "PASSWORD" in var or "URL" in var:
            import re
            display_val = re.sub(r":([^/@]+)@", ":****@", val) if "@" in val else "****"
            print(f"  {var}: {display_val}")
        else:
            print(f"  {var}: {val}")
    else:
        print(f"  {var}: [NOT SET]")

print("="*50 + "\n")
