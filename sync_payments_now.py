import asyncio
import logging
from dotenv import load_dotenv

# Инициализируем переменные окружения и логирование
load_dotenv()
logging.basicConfig(level=logging.INFO)

from backend.database import AsyncSessionLocal
from backend import services

async def main():
    print("🚀 Запуск ручной синхронизации неоплаченных счетов YooKassa...")
    async with AsyncSessionLocal() as db:
        await services.sync_pending_payments(db)
    print("✅ Синхронизация завершена!")

if __name__ == "__main__":
    asyncio.run(main())
