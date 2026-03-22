import os
import json
import logging
from sqlalchemy.future import select
from . import models
from .kie_api import create_task, get_task_info
import uuid

logger = logging.getLogger(__name__)

def get_model_cost(model_id: str) -> float:
    costs_str = os.getenv("CREDITS_PER_MODEL", '{"google/nano-banana": 1.0, "google/nano-banana-edit": 1.0, "nano-banana-2": 3.0, "nano-banana-pro": 4.0}')
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

async def start_generation_flow(db, user_id: int, prompt: str, image_urls: list, model_id: str, cost: float):
    """Saves task to DB and sends to KIE API"""
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
    res = await create_task(model_id, prompt, image_urls)
    if not res["success"]:
        raise Exception(res.get("error", "Unknown API error from KIE"))
        
    return res["taskId"]

async def check_generation_status(task_id: str):
    """Wrapper for KIE recordInfo"""
    return await get_task_info(task_id)
