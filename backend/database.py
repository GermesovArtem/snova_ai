import os
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import declarative_base
from dotenv import load_dotenv

# --- EXTREME DEBUG START ---
print("\n" + "#"*40)
print(">>> BOT STARTUP: LOADING NEW CODE v3.1 <<<")
load_dotenv()

def parse_db_url(url: str) -> str:
    """Strips ${...} and expands if possible, ensuring a clean URL."""
    if not url: return url
    import re
    # Strip any shell-style variables like ${VAR} or $VAR if they leaked into the string
    cleaned = re.sub(r'\$\{?[\w_]+\}?', lambda m: os.getenv(m.group(0).strip("${}"), ""), url)
    # Ensure it's not empty after cleaning
    return cleaned if cleaned and "://" in cleaned else None

# DB Credentials and fallback
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL or "${" in DATABASE_URL:
    DB_USER = os.getenv("POSTGRES_USER", "postgres")
    DB_PASS = os.getenv("POSTGRES_PASSWORD", "postgres")
    DB_HOST = os.getenv("POSTGRES_HOST", "db")
    DB_NAME = os.getenv("POSTGRES_DB", "nanobanana")
    DATABASE_URL = f"postgresql+asyncpg://{DB_USER}:{DB_PASS}@{DB_HOST}:5432/{DB_NAME}"
else:
    DATABASE_URL = parse_db_url(DATABASE_URL)
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
