import os
import json
import logging
from sqlalchemy.future import select
from sqlalchemy import func, cast, Date
from . import models
from . import models
from .kie_api import create_task, get_task_info
import uuid

logger = logging.getLogger(__name__)

def normalize_model_id(model_id: str) -> str:
    """Corrects model names for KIE API compatibility.
    New models (2, Pro) must NOT have 'google/' prefix.
    Legacy models must HAVE 'google/' prefix.
    """
    if not model_id or not isinstance(model_id, str): return model_id
    
    # 1. Lowercase and strip whitespace
    model_id = model_id.lower().strip()
    
    # 2. Direct models (MUST NOT have prefix)
    direct_models = ["nano-banana-2", "nano-banana-pro"]
    for dm in direct_models:
        if model_id == dm or model_id == f"google/{dm}":
            return dm
            
    # 3. Legacy/Pre-prefixed models (MUST have 'google/' prefix)
    legacy_models = ["nano-banana", "nano-banana-edit"]
    for lm in legacy_models:
        if model_id == lm:
            return f"google/{lm}"
        if model_id == f"google/{lm}":
            return model_id
            
    return model_id

async def fix_all_model_ids(db):
    res = await db.execute(select(models.User))
    users = res.scalars().all()
    any_changed = False
    for user in users:
        norm = normalize_model_id(user.model_preference)
        if norm != user.model_preference:
            user.model_preference = norm
            any_changed = True
    if any_changed:
        await db.commit()
        logger.info("Fixed model IDs for existing users in database.")

def get_model_cost(model_id: str) -> float:
    # Auto-normalize to handle old DB values
    model_id = normalize_model_id(model_id)
    costs_str = os.getenv("CREDITS_PER_MODEL", '{"google/nano-banana-2": 3.0, "google/nano-banana-pro": 4.0}')

    try:
        costs = json.loads(costs_str)
        return float(costs.get(model_id, 1.0))
    except:
        return 1.0

async def get_or_create_user(db, tg_id: int, username: str = None) -> models.User:
    res = await db.execute(select(models.User).filter_by(id=tg_id))
    user = res.scalars().first()
    if not user:
        starting_balance = float(os.getenv("STARTING_BALANCE", "5.0"))
        user = models.User(id=tg_id, name=username, balance=starting_balance, frozen_balance=0.0)
        db.add(user)
        await db.commit()
        await db.refresh(user)
    return user

async def pre_charge_generation(db, user: models.User, model_id: str) -> float:
    """Freezes user balance before generation"""
    cost = get_model_cost(model_id)
    if user.balance < cost:
        raise ValueError("Недостаточно кредитов!")
        
    user.balance -= cost
    user.frozen_balance += cost
    await db.commit()
    return cost

async def refund_frozen_credits(db, user_id: int, cost: float):
    """Refunds credits if generation fails (e.g., 402 code)"""
    res = await db.execute(select(models.User).filter_by(id=user_id))
    user = res.scalars().first()
    if user:
        user.balance += cost
        user.frozen_balance -= cost
        await db.commit()

async def commit_frozen_credits(db, user_id: int, cost: float):
    """Permanently deducts frozen credits upon success"""
    res = await db.execute(select(models.User).filter_by(id=user_id))
    user = res.scalars().first()
    if user:
        user.frozen_balance -= cost
        await db.commit()

async def start_generation_flow(db, user_id: int, prompt: str, image_urls: list, 
                                model_id: str, cost: float, 
                                aspect_ratio: str = "auto", resolution: str = "1K", 
                                output_format: str = "jpg"):
    """Saves task to DB and sends to KIE API"""
    # Final safety normalization
    model_id = normalize_model_id(model_id)
    new_task = models.GenerationTask(
        user_id=user_id,
        tool="image",
        model=model_id,
        prompt=prompt,
        image_url=image_urls[0] if image_urls else None,
        credits_cost=cost
    )
    db.add(new_task)
    await db.commit()
    await db.refresh(new_task)
    
    # Call KIE
    res = await create_task(model_id, prompt, image_urls, aspect_ratio, resolution, output_format)
    if not res["success"]:
        raise Exception(res.get("error", "Unknown API error from KIE"))
        
    return res["taskId"]

async def check_generation_status(task_id: str):
    """Wrapper for KIE recordInfo"""
    return await get_task_info(task_id)

# --- Admin API ---
import datetime

async def get_admin_stats(db) -> dict:
    today = datetime.datetime.now(datetime.timezone.utc).date()
    
    # User stats
    total_users = (await db.execute(select(func.count(models.User.id)))).scalar() or 0
    new_users_today = (await db.execute(
        select(func.count(models.User.id))
        .filter(cast(models.User.created_at, Date) == today)
    )).scalar() or 0
    
    # Gen stats
    total_gens = (await db.execute(select(func.count(models.GenerationTask.id)))).scalar() or 0
    gens_today = (await db.execute(
        select(func.count(models.GenerationTask.id))
        .filter(cast(models.GenerationTask.created_at, Date) == today)
    )).scalar() or 0
    
    return {
        "total_users": total_users,
        "new_users_today": new_users_today,
        "total_gens": total_gens,
        "gens_today": gens_today
    }

async def search_user(db, query: str) -> models.User:
    if query.isdigit():
        res = await db.execute(select(models.User).filter_by(id=int(query)))
        return res.scalars().first()
    else:
        query = query.replace("@", "")
        res = await db.execute(select(models.User).filter(models.User.name.ilike(f"%{query}%")))
        return res.scalars().first()

async def update_user_balance(db, user_id: int, amount: float) -> models.User:
    res = await db.execute(select(models.User).filter_by(id=user_id))
    user = res.scalars().first()
    if user:
        user.balance += amount
        await db.commit()
        await db.refresh(user)
    return user
