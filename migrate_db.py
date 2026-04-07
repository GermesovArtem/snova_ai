import asyncio
import os
import sys
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
from dotenv import load_dotenv

async def migrate():
    print("--- Starting Database Migration ---")
    
    # Load environment variables
    load_dotenv()
    
    # Try using DATABASE_URL from .env
    db_url = os.getenv("DATABASE_URL")
    
    # Fallback to defaults common in Docker-Compose
    if not db_url or "${" in db_url:
        user = os.getenv("POSTGRES_USER", "postgres")
        pw = os.getenv("POSTGRES_PASSWORD", "postgres")
        host = os.getenv("POSTGRES_HOST", "localhost") # Host machine connects via localhost if port 5432 is mapped
        name = os.getenv("POSTGRES_DB", "nanobanana")
        db_url = f"postgresql+asyncpg://{user}:{pw}@{host}:5432/{name}"
    
    print(f"Connecting to: {db_url.split('@')[1]}...")
    
    try:
        engine = create_async_engine(db_url)
        
        async with engine.begin() as conn:
            # Check if column already exists
            res = await conn.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name='generation_tasks' AND column_name='prompt_images_json';
            """))
            exists = res.scalar()
            
            if not exists:
                print("Adding 'prompt_images_json' column to 'generation_tasks' table...")
                await conn.execute(text("ALTER TABLE generation_tasks ADD COLUMN prompt_images_json VARCHAR;"))
                print("--- Migration Successful! ---")
            else:
                print("--- Column already exists, skipping migration ---")
                
        await engine.dispose()
    except Exception as e:
        print(f"!!! Error during migration: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(migrate())
