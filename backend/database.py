import os
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import declarative_base
from dotenv import load_dotenv

# --- EXTREME DEBUG START ---
print("\n" + "#"*40)
print(">>> BOT STARTUP: LOADING NEW CODE v3.1 <<<")
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
if DATABASE_URL:
    import re
    masked = re.sub(r":([^/@]+)@", ":****@", DATABASE_URL)
    print(f"DEBUG: Found DATABASE_URL: {masked}")
else:
    print("DEBUG: DATABASE_URL not found in env!")

# Check individual components
print(f"DEBUG: POSTGRES_USER in env: {os.getenv('POSTGRES_USER')}")
print(f"DEBUG: POSTGRES_PASSWORD set: {'Yes' if os.getenv('POSTGRES_PASSWORD') else 'No'}")
print("#"*40 + "\n")

# DB Credentials and fallback
if not DATABASE_URL or "${" in DATABASE_URL:
    DB_USER = os.getenv("POSTGRES_USER", "postgres")
    DB_PASS = os.getenv("POSTGRES_PASSWORD", "postgres")
    DB_HOST = os.getenv("POSTGRES_HOST", "db")
    DB_NAME = os.getenv("POSTGRES_DB", "nanobanana")
    DATABASE_URL = f"postgresql+asyncpg://{DB_USER}:{DB_PASS}@{DB_HOST}:5432/{DB_NAME}"
# --- EXTREME DEBUG END ---

# Create Async Engine
engine = create_async_engine(DATABASE_URL, echo=False)

# Create session factory
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    expire_on_commit=False,
    class_=AsyncSession
)

Base = declarative_base()

async def get_db():
    """Dependency for getting async database sessions"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
