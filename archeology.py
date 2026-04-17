import asyncio
import json
import os
from sqlalchemy import text
from backend.database import AsyncSessionLocal

async def extract_data():
    print("\n--- DATA ARCHEOLOGY START ---")
    async with AsyncSessionLocal() as db:
        try:
            # 1. Fetch Users
            print("[INFO] Attempting to fetch users from the mounted volume...")
            res = await db.execute(text("SELECT id, name, balance, created_at FROM users;"))
            users = [
                {
                    "id": row[0],
                    "name": row[1],
                    "balance": row[2],
                    "created_at": str(row[3])
                } for row in res
            ]
            
            # 2. Save result
            if users:
                with open("recovered_users.json", "w", encoding="utf-8") as f:
                    json.dump(users, f, indent=4, ensure_ascii=False)
                print(f"[SUCCESS] Found {len(users)} users! Data saved to recovered_users.json")
                for u in users[:5]: # Show first 5 for verification
                    print(f"Found: {u['name']} (ID: {u['id']}, Balance: {u['balance']})")
            else:
                print("[WARNING] No users found in this volume.")

            # 3. Fetch Payments (Optional but good)
            print("\n[INFO] Checking for payments...")
            try:
                p_res = await db.execute(text("SELECT user_id, amount_rub, status FROM payments;"))
                payments = [dict(row._mapping) for row in p_res]
                if payments:
                    with open("recovered_payments.json", "w", encoding="utf-8") as f:
                        json.dump(payments, f, indent=4)
                    print(f"[SUCCESS] Found {len(payments)} payment records!")
            except Exception:
                print("[INFO] No payments table found or it's empty.")

        except Exception as e:
            print(f"[ERROR] Could not read data: {e}")
            print("Check if the database schema in this volume matches the code!")
    
    print("--- ARCHEOLOGY END ---\n")

if __name__ == "__main__":
    asyncio.run(extract_data())
