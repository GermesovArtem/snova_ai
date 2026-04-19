import asyncio
from sqlalchemy import text
from backend.database import engine

async def main():
    try:
        async with engine.connect() as conn:
            # Check if column exists
            res = await conn.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name='generation_tasks' AND column_name='status_message_id';"))
            if not res.fetchone():
                print("Adding column status_message_id to generation_tasks...")
                await conn.execute(text("ALTER TABLE generation_tasks ADD COLUMN status_message_id INTEGER;"))
                await conn.commit()
                print("Column added successfully.")
            else:
                print("Column status_message_id already exists.")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
