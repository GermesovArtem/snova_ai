import asyncio
import os
from sqlalchemy import text
from backend.database import AsyncSessionLocal, engine

async def check():
    print("\n--- DATABASE INSPECTION START ---")
    async with AsyncSessionLocal() as db:
        try:
            # 1. Check Table Structure
            print("\n[STEP 1] Checking 'users' table structure:")
            res = await db.execute(text("""
                SELECT column_name, data_type, is_nullable
                FROM information_schema.columns
                WHERE table_name = 'users';
            """))
            for row in res:
                print(f"Col: {row[0]}, Type: {row[1]}, Nullable: {row[2]}")

            # 2. Check Data
            print("\n[STEP 2] Listing all users in DB:")
            res = await db.execute(text("SELECT id, name FROM users LIMIT 10;"))
            users = res.fetchall()
            if not users:
                print("DB is EMPTY!")
            for u in users:
                print(f"USER -> ID: {u[0]}, NAME: {u[1]}")
                
        except Exception as e:
            print(f"ERROR: {e}")
    print("\n--- INSPECTION END ---")

if __name__ == "__main__":
    asyncio.run(check())
