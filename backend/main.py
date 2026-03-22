from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from .database import get_db, engine, Base
from . import models
from . import services
from pydantic import BaseModel
from typing import List, Optional
import os

app = FastAPI(title="Bananix Clone API Engine")

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

# --- Auth Dependency ---
async def get_current_user(db: AsyncSession = Depends(get_db)):
    # Simple mock user
    user = await services.get_or_create_user(db, 209, "WebUserMock")
    return user


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

@app.post("/api/v1/payments/credit-pack")
async def buy_credit_pack(data: CreditPack, user: models.User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return {
        "success": True, 
        "data": {
            "payment_id": "test_dummy_payment_id", 
            "payment_url": "https://yoomoney.ru/checkout"
        }
    }
