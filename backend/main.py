from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Form, Request, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
import os
import uuid
import logging
import json

from backend.database import get_db, Base, engine, AsyncSessionLocal
from backend import models, schemas, auth, services, s3_service
from backend.routers import admin, payments

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="S•NOVA AI Backend")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root_health_check():
    return {"status": "ok", "message": "S•NOVA AI API is running"}

from sqlalchemy import text, select
# --- DB INIT ---
@app.on_event("startup")
async def startup():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        
        # Migration: Add prompt_images_json if missing
        try:
            # Check if column exists
            res = await conn.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name='generation_tasks' AND column_name='prompt_images_json';
            """))
            if not res.scalar():
                logger.info("Migration: Adding prompt_images_json column to generation_tasks")
                await conn.execute(text("ALTER TABLE generation_tasks ADD COLUMN prompt_images_json VARCHAR;"))
        except Exception as e:
            logger.error(f"Migration error: {e}")

    # Database Migration: TG ID separation
    async with engine.begin() as conn:
        try:
            # 1. Add telegram_id column if it doesn't exist
            # Note: We use raw text for direct SQL control
            logger.info("Migration: Checking for telegram_id column...")
            try:
                await conn.execute(text("ALTER TABLE users ADD COLUMN telegram_id BIGINT UNIQUE;"))
                logger.info("Migration: Added telegram_id column.")
            except Exception:
                # Column likely already exists
                pass

            # 2. Add vk_id column if it doesn't exist
            try:
                await conn.execute(text("ALTER TABLE users ADD COLUMN vk_id BIGINT UNIQUE;"))
                logger.info("Migration: Added vk_id column.")
            except Exception: pass

            # 3. Synchronize old data: Move 'id' to 'telegram_id' for existing users who don't have it set
            # This ensures old users (where ID = TG ID) are still findable by the bot.
            res = await conn.execute(text("SELECT COUNT(*) FROM users WHERE telegram_id IS NULL"))
            count = res.scalar()
            if count and count > 0:
                logger.info(f"Migration: Migrating {count} users to new telegram_id column...")
                await conn.execute(text("UPDATE users SET telegram_id = id WHERE telegram_id IS NULL"))
                await conn.commit()

            # 4. Postgres Specific: Ensure 'id' column uses a sequence for AUTOINCREMENT
            # Since the original model had autoincrement=False, SqlAlchemy might not have created a sequence.
            try:
                # Check current ID max to set sequence start
                max_id_res = await conn.execute(text("SELECT MAX(id) FROM users"))
                max_id = max_id_res.scalar() or 0
                
                # Check for existing sequence or create it
                await conn.execute(text("CREATE SEQUENCE IF NOT EXISTS users_id_seq;"))
                await conn.execute(text(f"SELECT setval('users_id_seq', {max_id});"))
                await conn.execute(text("ALTER TABLE users ALTER COLUMN id SET DEFAULT nextval('users_id_seq');"))
                logger.info(f"Migration: Reset id sequence to {max_id}")
            except Exception as e:
                logger.warning(f"Migration: Sequence setup skipped/failed (likely SQLite or already set): {e}")

        except Exception as e:
            logger.error(f"Critical Migration error: {e}")

    # Ensure starting models are normalized
    async with AsyncSessionLocal() as db:
        await services.fix_all_model_ids(db)
        
    # Migration: Enforce unique constraint on provider_payment_id
    async with engine.begin() as conn:
        try:
            logger.info("Migration: Enforcing uniqueness on provider_payment_id")
            # This might fail if duplicates already exist, deleting duplicates first
            await conn.execute(text("""
                DELETE FROM payments WHERE id NOT IN (
                    SELECT MIN(id) FROM payments GROUP BY provider_payment_id
                );
            """))
            await conn.execute(text("ALTER TABLE payments ADD CONSTRAINT unique_provider_payment_id UNIQUE (provider_payment_id);"))
        except Exception:
            # Maybe constraint already exists or something else, it's fine for simple migration
            pass

app.include_router(admin.router, prefix="/api/v1")
app.include_router(payments.router, prefix="/api/v1")

# --- AUTH ---
@app.post("/api/v1/auth/telegram")
async def auth_telegram(data: schemas.TelegramAuth, db: AsyncSession = Depends(get_db)):
    if not auth.verify_telegram_auth(data.dict()):
        logger.warning(f"Telegram auth failed for user {data.id}")
        # return {"success": False, "error": "Invalid auth token"}
    
    user, _ = await services.get_or_create_user(db, data.id, data.first_name, data.username)
    token = auth.create_access_token({"sub": str(user.id)})
    return {"success": True, "access_token": token, "token_type": "bearer"}

# --- CONFIG ---
@app.get("/api/v1/config/models")
async def get_config_models():
    """Returns AVAILABLE_MODELS and CREDITS_PER_MODEL from .env"""
    try:
        avail_str = os.getenv("AVAILABLE_MODELS", "{}")
        prices_str = os.getenv("CREDITS_PER_MODEL", "{}")
        packs_str = os.getenv("CREDIT_PACKS", '{"149": 10, "299": 25, "899": 100}')
        
        return {
            "success": True,
            "data": {
                "available_models": json.loads(avail_str),
                "credits_per_model": json.loads(prices_str),
                "credit_packs": json.loads(packs_str)
            }
        }
    except Exception as e:
        logger.error(f"Error parsing config: {e}")
        return {"success": False, "error": str(e)}

async def get_current_user(request: Request, db: AsyncSession = Depends(get_db)):
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Unauthorized")
    token = auth_header.split(" ")[1]
    user_id = auth.verify_access_token(token)
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token")
    user = await services.get_user_by_id(db, int(user_id))
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user

# --- USER & HISTORY ---
@app.get("/api/v1/user/me")
async def get_me(user: models.User = Depends(get_current_user)):
    return {"success": True, "data": user}

@app.get("/api/v1/user/history")
async def get_history(user: models.User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    history = await services.get_user_history(db, user.id)
    return {"success": True, "data": history}

@app.post("/api/v1/user/upload")
async def upload_file(
    image: UploadFile = File(...),
    user: models.User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    try:
        content = await image.read()
        ext = os.path.splitext(image.filename)[1]
        public_url = await s3_service.upload_file_to_s3(content, ext)
        return {"success": True, "data": {"url": public_url}}
    except Exception as e:
        logger.error(f"Upload error: {e}")
        return {"success": False, "error": str(e)}

@app.get("/api/v1/user/active-tasks")
async def get_active_tasks(user: models.User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Check for pending/processing tasks to restore session state."""
    tasks = await services.get_active_generation_tasks(db, user.id)
    return {"success": True, "data": tasks}

@app.post("/api/v1/user/model")
async def update_model(model: schemas.ModelUpdate, user: models.User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    user.model_preference = services.normalize_model_id(model.model_id)
    await db.commit()
    return {"success": True}

# --- WEB CHAT MESSAGES ---
@app.get("/api/v1/user/messages")
async def get_messages(user: models.User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    msgs = await services.get_web_messages(db, user.id)
    return {"success": True, "data": msgs}

@app.post("/api/v1/user/messages")
async def add_message(msg: schemas.MessageCreate, user: models.User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    new_msg = await services.save_web_message(db, user.id, msg.role, msg.text, msg.image_url, msg.meta)
    return {"success": True, "data": new_msg}

@app.patch("/api/v1/user/messages/{msg_id}")
async def patch_message(msg_id: int, data: schemas.MessageUpdate, user: models.User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    updated = await services.update_web_message(db, user.id, msg_id, data.text, data.meta)
    if not updated: raise HTTPException(status_code=404, detail="Message not found")
    return {"success": True, "data": updated}

@app.delete("/api/v1/user/messages/{msg_id}")
async def remove_message(msg_id: int, user: models.User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    success = await services.delete_web_message(db, user.id, msg_id)
    if not success: raise HTTPException(status_code=404, detail="Message not found")
    return {"success": True}

# --- PAYMENTS ---
@app.post("/api/v1/payments/create")
async def create_payment(pack_id: str, user: models.User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    packs_str = os.getenv("CREDIT_PACKS", '{"149": 30, "299": 65, "990": 270}')
    try:
        packs = json.loads(packs_str)
        if pack_id not in packs:
            raise HTTPException(status_code=400, detail="Invalid pack")
        
        amount = float(pack_id)
        description = f"S•NOVA AI: Пополнение на {packs[pack_id]} кр."
        url = await services.create_yookassa_payment(db, user.id, amount, description)
        return {"success": True, "data": {"payment_url": url}}
    except Exception as e:
        logger.error(f"Payment error: {e}")
        return {"success": False, "error": str(e)}

# --- STATIC FILES ---
UPLOAD_DIR = os.path.join("backend", "static", "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)
app.mount("/static", StaticFiles(directory="backend/static"), name="static")

# --- GENERATION ---
@app.post("/api/v1/generate/edit")
async def generate_edit(
    background_tasks: BackgroundTasks,
    prompt: str = Form(...),
    images: List[UploadFile] = File([]),
    model_id: str = Form(None),
    aspect_ratio: str = Form("1:1"),
    resolution: str = Form("1K"),
    output_format: str = Form("png"),
    status_message_id: int = Form(None),
    s3_url: str = Form(None), # Accepts already uploaded URL
    user: models.User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    try:
        # 1. Upload files and get URLs (Using Direct Public URLs for KIE AI stability)
        image_urls = []
        if s3_url:
            # Use already uploaded S3 URL (assumed to be public)
            image_urls.append(s3_url)
        
        for img in images:
            content = await img.read()
            ext = os.path.splitext(img.filename)[1]
            public_url = await s3_service.upload_file_to_s3(content, ext)
            image_urls.append(public_url)
            
        # 2. Get cost
        model = services.normalize_model_id(model_id or user.model_preference)
        cost = services.get_model_cost(model)
        
        # 3. Start flow
        task_uuid = await services.start_generation_flow(
            db, user.id, prompt, image_urls, model, cost, 
            aspect_ratio, resolution, output_format,
            status_message_id=status_message_id
        )
        
        # 4. Launch background polling (Parity with Bot)
        background_tasks.add_task(
            services.background_poll_kie_task, 
            AsyncSessionLocal, user.id, task_uuid, status_message_id
        )
        
        return {"success": True, "data": {"task_uuid": task_uuid}}
    except Exception as e:
        logger.error(f"Generation error: {e}", exc_info=True)
        return {"success": False, "error": services.translate_error(str(e))}

@app.get("/api/v1/generations/{task_uuid}")
async def get_generation(task_uuid: str, user: models.User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    info = await services.check_generation_status(task_uuid)
    
    # Persistence: Save result URL to DB when finished
    if info.get("success") and info.get("state") in ["success", "completed"] and info.get("image_url"):
        res = await db.execute(select(models.GenerationTask).filter_by(task_uuid=task_uuid))
        task = res.scalars().first()
        if task and not task.image_url:
            task.image_url = info["image_url"]
            task.status = "completed"
            await db.commit()
            logger.info(f"Task {task_uuid} persisted to DB with URL {info['image_url']}")

    return {
        "success": True,
        "data": info
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
