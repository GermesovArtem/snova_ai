import asyncio
from backend.database import AsyncSessionLocal
from sqlalchemy import select
from backend import models

async def main():
    async with AsyncSessionLocal() as db:
        res = await db.execute(select(models.GenerationTask).order_by(models.GenerationTask.id.desc()).limit(10))
        tasks = res.scalars().all()
        for t in tasks:
            print(f"ID={t.id} User={t.user_id} Status={t.status} UUID={t.task_uuid} URL={t.image_url}")

if __name__ == "__main__":
    asyncio.run(main())
