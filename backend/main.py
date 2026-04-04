from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from .database import get_db, engine, Base
from . import models
from . import services
from pydantic import BaseModel
from typing import List, Optional
from aiogram import Bot
import json
from dotenv import load_dotenv
import os
from fastapi.middleware.cors import CORSMiddleware
from . import auth

load_dotenv()

app = FastAPI(title="S•NOVA AI Admin & API Engine")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # В продакшене ограничить конкретными доменами
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Admin Config
ADMIN_PATH = os.getenv("ADMIN_PATH", "/admin_panel").strip("/")
ADMIN_USER = os.getenv("ADMIN_USER", "admin")
ADMIN_PASS = os.getenv("ADMIN_PASS", "changeme")
BOT_TOKEN = os.getenv("BOT_TOKEN")

bot = Bot(token=BOT_TOKEN) if BOT_TOKEN else None

@app.on_event("startup")
async def startup():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

# --- Pydantic Schemas ---
class UserModelConfig(BaseModel):
    model: str

class GenerateEditUrl(BaseModel):
    prompt: str
    model: str = "nanobanana"
    image_urls: List[str]

class CreditPack(BaseModel):
    rub: int

# --- Admin Auth ---
from fastapi.security import HTTPBasic, HTTPBasicCredentials
import secrets

security = HTTPBasic()

def admin_auth(credentials: HTTPBasicCredentials = Depends(security)):
    is_user_ok = secrets.compare_digest(credentials.username, ADMIN_USER)
    is_pass_ok = secrets.compare_digest(credentials.password, ADMIN_PASS)
    if not (is_user_ok and is_pass_ok):
        raise HTTPException(
            status_code=401,
            detail="Incorrect login or password",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username

# --- Auth Dependency ---
from .auth import get_current_user

class AuthData(BaseModel):
    id: int
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    username: Optional[str] = None
    photo_url: Optional[str] = None
    auth_date: int
    hash: str

@app.post("/api/v1/auth/telegram")
async def auth_telegram(data: AuthData, db: AsyncSession = Depends(get_db)):
    # 1. Verify Telegram Hash
    if not auth.verify_telegram_data(data.dict()):
        raise HTTPException(status_code=400, detail="Invalid telegram auth data")
    
    # 2. Get or Create User
    user = await services.get_or_create_user(
        db, 
        data.id, 
        name=f"{data.first_name or ''} {data.last_name or ''}".strip(), 
        username=data.username
    )
    
    # Update profile if needed
    if data.photo_url:
        user.photo_url = data.photo_url
        await db.commit()

    # 3. Create Token
    token = auth.create_access_token(data={"sub": str(user.id)})
    return {"success": True, "access_token": token, "token_type": "bearer"}


# --- Endpoints ---
@app.get("/api/v1/user/me")
async def get_me(user: models.User = Depends(get_current_user)):
    return {
        "success": True,
        "data": {
            "id": user.id,
            "name": user.name,
            "role": user.role,
            "balance": user.balance,
            "model_preference": user.model_preference
        }
    }

@app.put("/api/v1/user/me/model")
async def update_model_preference(config: UserModelConfig, user: models.User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    user.model_preference = config.model
    await db.commit()
    return {"success": True, "data": {"model": config.model}}

@app.post("/api/v1/generate/edit")
async def generate_edit(
    prompt: str = Form(...), 
    image: UploadFile = File(None),
    user: models.User = Depends(get_current_user), 
    db: AsyncSession = Depends(get_db)):
    
    try:
        cost = await services.pre_charge_generation(db, user, user.model_preference)
        kie_task_id = await services.start_generation_flow(db, user.id, prompt, [], user.model_preference, cost)
        return {"success": True, "data": {"task_uuid": kie_task_id}}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        await services.refund_frozen_credits(db, user.id, cost)
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/v1/generate/edit-url")
async def generate_edit_url(data: GenerateEditUrl, user: models.User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    try:
        cost = await services.pre_charge_generation(db, user, data.model)
        kie_task_id = await services.start_generation_flow(db, user.id, data.prompt, data.image_urls, data.model, cost)
        return {"success": True, "data": {"task_uuid": kie_task_id}}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        await services.refund_frozen_credits(db, user.id, cost)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/generations/{task_uuid}")
async def get_generation(task_uuid: str, user: models.User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    info = await services.check_generation_status(task_uuid)
    return {
        "success": True,
        "data": info
    }

# --- Admin Endpoints ---
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles

@app.get(f"/{ADMIN_PATH}", response_class=HTMLResponse)
async def get_admin_ui(admin: str = Depends(admin_auth)):
    # Create static directory if not exists
    static_dir = os.path.join(os.path.dirname(__file__), "static")
    if not os.path.exists(static_dir):
        os.makedirs(static_dir)
    return FileResponse(os.path.join(static_dir, "admin.html"))

@app.get(f"/{ADMIN_PATH}/api/stats")
async def get_admin_stats(db: AsyncSession = Depends(get_db), admin: str = Depends(admin_auth)):
    stats = await services.get_admin_stats(db)
    return {"success": True, "data": stats}

@app.get(f"/{ADMIN_PATH}/api/users")
async def list_users(page: int = 1, query: Optional[str] = None, db: AsyncSession = Depends(get_db), admin: str = Depends(admin_auth)):
    # Simple user listing with limit
    limit = 50
    offset = (page - 1) * limit
    if query:
        res = await db.execute(select(models.User).filter(
            (models.User.id.cast(models.String).ilike(f"%{query}%")) | 
            (models.User.name.ilike(f"%{query}%"))
        ).limit(limit).offset(offset))
    else:
        res = await db.execute(select(models.User).order_by(models.User.created_at.desc()).limit(limit).offset(offset))
    
    users = res.scalars().all()
    return {"success": True, "data": users}

@app.post(f"/{ADMIN_PATH}/api/update_balance")
async def admin_update_balance(user_id: int, amount: float, db: AsyncSession = Depends(get_db), admin: str = Depends(admin_auth)):
    user = await services.update_user_balance(db, user_id, amount)
    return {"success": True, "data": {"new_balance": user.balance}}

@app.post(f"/{ADMIN_PATH}/api/broadcast")
async def admin_broadcast(text: str = Form(...), db: AsyncSession = Depends(get_db), admin: str = Depends(admin_auth)):
    if not bot:
        return {"success": False, "error": "Bot not initialized"}
        
    res = await db.execute(select(models.User.id))
    user_ids = [row[0] for row in res.fetchall()]
    
    success_count = 0
    for uid in user_ids:
        try:
            await bot.send_message(uid, text, parse_mode="Markdown")
            success_count += 1
        except: pass
    
    return {"success": True, "data": {"sent": success_count}}
