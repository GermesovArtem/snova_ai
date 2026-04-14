import asyncio
import os
import logging
from sqlalchemy import select, update, text
from dotenv import load_dotenv

load_dotenv()

# Инициализируем БД и сервисы после загрузки env
from backend.database import AsyncSessionLocal
from backend.s3_service import upload_file_to_s3

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

UPLOAD_DIR = os.path.join("backend", "static", "uploads")
ENV_PUBLIC = os.getenv("PUBLIC_URL", "https://fragmentx.tech") # Дефолт из .env как запасной вариант

async def migrate_files():
    if not os.path.exists(UPLOAD_DIR):
        logger.info(f"Directory {UPLOAD_DIR} does not exist. Nothing to migrate.")
        return

    files = [f for f in os.listdir(UPLOAD_DIR) if os.path.isfile(os.path.join(UPLOAD_DIR, f))]
    if not files:
        logger.info(f"Directory {UPLOAD_DIR} is empty. Nothing to migrate.")
        return

    logger.info(f"Found {len(files)} files to migrate to S3.")

    # Для массовой замены урлов в БД, лучше держать кэш: старый урл -> новый S3 урл
    url_mapping = {}

    for filename in files:
        filepath = os.path.join(UPLOAD_DIR, filename)
        ext = os.path.splitext(filename)[1] or ".jpg"
        
        try:
            with open(filepath, "rb") as f:
                file_bytes = f.read()

            logger.info(f"Uploading {filename} to S3...")
            s3_url = await upload_file_to_s3(file_bytes, ext)
            
            old_url = f"{ENV_PUBLIC}/static/uploads/{filename}"
            url_mapping[old_url] = s3_url
            
            # Удаляем локальный файл
            os.remove(filepath)
            logger.info(f"Deleted local file: {filepath}")

        except Exception as e:
            logger.error(f"Error migrating {filename}: {e}")
            continue

    if not url_mapping:
        logger.info("No successful uploads. Database will not be updated.")
        return

    logger.info("Files uploaded to S3. Updating database references...")
    
    # Теперь нужно пройтись по таблице generation_tasks и заменить ссылки в prompt_images_json
    async with AsyncSessionLocal() as db:
        try:
            # Делаем сырой запрос, так как prompt_images_json - текстовое поле с JSON
            res = await db.execute(text("SELECT id, prompt_images_json FROM generation_tasks WHERE prompt_images_json IS NOT NULL AND prompt_images_json != '[]'"))
            tasks = res.fetchall()
            
            updates = 0
            for task in tasks:
                task_id = task[0]
                images_json = task[1]
                
                if not images_json:
                    continue
                
                modified = False
                for old_url, new_url in url_mapping.items():
                    if old_url in images_json:
                        images_json = images_json.replace(old_url, new_url)
                        modified = True
                
                if modified:
                    await db.execute(
                        text("UPDATE generation_tasks SET prompt_images_json = :json WHERE id = :id"),
                        {"json": images_json, "id": task_id}
                    )
                    updates += 1
            
            await db.commit()
            logger.info(f"Updated {updates} tasks in database.")

        except Exception as e:
            logger.error(f"Failed to update database: {e}")

    logger.info("Migration complete!")

if __name__ == "__main__":
    asyncio.run(migrate_files())
