import asyncio
import os
import sys

# Add the current directory to sys.path so we can import backend
sys.path.append(os.getcwd())

from backend.database import AsyncSessionLocal
from sqlalchemy import select, func
from backend import models

async def main():
    async with AsyncSessionLocal() as db:
        # Count all tasks
        count_res = await db.execute(select(func.count(models.GenerationTask.id)))
        total_count = count_res.scalar()
        print(f"Total tasks in DB: {total_count}")
        
        # Count completed tasks
        comp_res = await db.execute(select(func.count(models.GenerationTask.id)).where(models.GenerationTask.status == "completed"))
        comp_count = comp_res.scalar()
        print(f"Completed tasks in DB: {comp_count}")
        
        # List last 5 tasks with details
        res = await db.execute(select(models.GenerationTask).order_by(models.GenerationTask.id.desc()).limit(5))
        tasks = res.scalars().all()
        for t in tasks:
            print(f"ID={t.id} User={t.user_id} Status={t.status} UUID={t.task_uuid} HasURL={t.image_url is not None}")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        print(f"Error: {e}")
