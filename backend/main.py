from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Form, Request
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
import os
import uuid
import logging
import json

from backend.database import get_db, Base, engine
from backend import models, schemas, auth, services
from backend.routers import admin

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

# --- DB INIT ---
@app.on_event("startup")
async def startup():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    # Ensure starting models are normalized
    async with AsyncSession(engine) as db:
        await services.fix_all_model_ids(db)

app.include_router(admin.router, prefix="/api/v1")

# --- AUTH ---
@app.post("/api/v1/auth/telegram")
async def auth_telegram(data: schemas.TelegramAuth, db: AsyncSession = Depends(get_db)):
    if not auth.verify_telegram_auth(data.dict()):
        logger.warning(f"Telegram auth failed for user {data.id}")
        # return {"success": False, "error": "Invalid auth token"}
    
    user = await services.get_or_create_user(db, data.id, data.first_name, data.username)
    token = auth.create_access_token({"sub": str(user.id)})
    return {"success": True, "access_token": token, "token_type": "bearer"}

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
    hist = await services.get_user_history(db, user.id)
    return {"success": True, "data": hist}

@app.post("/api/v1/user/model")
async def update_model(model: schemas.ModelUpdate, user: models.User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    user.model_preference = services.normalize_model_id(model.model_id)
    await db.commit()
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
        url = await services.create_yookassa_payment(user.id, amount, description)
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
    request: Request,
    prompt: str = Form(...),
    images: List[UploadFile] = File(default=[]),
    user: models.User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    # Determine public URL for images
    env_public = os.getenv("PUBLIC_URL")
    if not env_public:
        env_public = str(request.base_url).rstrip("/")
        
    filenames = []
    for img in images:
        ext = os.path.splitext(img.filename)[1] or ".jpg"
        name = f"{uuid.uuid4()}{ext}"
        path = os.path.join(UPLOAD_DIR, name)
        with open(path, "wb") as f:
            f.write(await img.read())
        filenames.append(name)
    
    image_urls = [f"{env_public}/static/uploads/{name}" for name in filenames]
    logger.info(f"KIE Generation: prompt='{prompt}', images={image_urls}")

    try:
        cost = await services.pre_charge_generation(db, user, user.model_preference)
    except ValueError as e:
        return {"success": False, "error": str(e)}

    try:
        task_id = await services.start_generation_flow(
            db, user.id, prompt, image_urls, user.model_preference, cost
        )
        return {"success": True, "data": {"task_uuid": task_id}}
    except Exception as e:
        logger.error(f"Generation error: {e}")
        await services.refund_frozen_credits(db, user.id, cost)
        return {"success": False, "error": str(e)}

@app.get("/api/v1/generations/{task_uuid}")
async def get_generation(task_uuid: str, user: models.User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    info = await services.check_generation_status(task_uuid)
    return {
        "success": True,
        "data": info
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
