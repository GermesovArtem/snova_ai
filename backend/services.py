import logging
import os
import json
from dotenv import load_dotenv
import datetime
from sqlalchemy import func, cast, Date, desc, select
from . import models
from .kie_api import create_task, get_task_info
import uuid

load_dotenv()

logger = logging.getLogger(__name__)

# Russian Error Translations for Kie AI
ERRORS_RU = {
    "Could not generate images": "Не удалось создать изображение с этими данными. Попробуйте изменить текст или фото.",
    "UndefinedColumnError": "Техническая ошибка: база данных устарела. Обратитесь к админу.",
    "ProgrammingError": "Техническая ошибка в запросе к базе данных.",
    "Internal Server Error": "Внутренняя ошибка сервера. Мы уже работаем над этим!",
    "timeout": "Время ожидания истекло. Пожалуйста, попробуйте еще раз через минуту.",
    "ConnectionError": "Ошибка соединения с сервером. Проверьте интернет или подождите.",
    "violated Google's Generative AI Prohibited Use policy": "Ваш запрос был отклонен фильтром безопасности ИИ (нарушение политики использования). Пожалуйста, измените описание или фото на более нейтральные.",
    "No images found in AI response": "Изображение не было создано ИИ. Попробуйте изменить запрос.",
    "insufficient_funds": "Недостаточно средств на балансе сервиса генерации."
}

def translate_error(error_msg: str) -> str:
    """Translates technical error messages to user-friendly Russian."""
    if not error_msg:
        return "Произошла неизвестная ошибка."
    
    error_msg_lower = str(error_msg).lower()
    for key, val in ERRORS_RU.items():
        if key.lower() in error_msg_lower:
            return val
            
    if "db" in error_msg_lower or "database" in error_msg_lower:
        return "Ошибка базы данных. Повторите попытку позже."
        
    return f"Ошибка: {error_msg}"


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
    legacy_models = ["nano-banana", "nano-banana-edit", "nanobanana"]
    for lm in legacy_models:
        if model_id == lm:
            return f"google/{lm}"
        if model_id == f"google/{lm}":
            return model_id
            
    return model_id

def get_model_limit(model_id: str) -> int:
    """Returns official limit for image_input: 8 for PRO, 14 for v2"""
    if "pro" in str(model_id).lower():
        return 8
    return 14

def get_available_models():
    models_str = os.getenv("AVAILABLE_MODELS", '{"NanoBanana 2": "nano-banana-2", "NanoBanana PRO": "nano-banana-pro"}')
    try:
        return json.loads(models_str)
    except:
        return {"NanoBanana 2": "nano-banana-2", "NanoBanana PRO": "nano-banana-pro"}

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
    # Default fallback prices without 'google/' prefix to match normalization
    costs_str = os.getenv("CREDITS_PER_MODEL", '{"nano-banana-2": 3.0, "nano-banana-pro": 4.0}')

    try:
        costs = json.loads(costs_str)
        normalized_costs = {normalize_model_id(k): v for k, v in costs.items()}
        return float(normalized_costs.get(model_id, 3.0))
    except (json.JSONDecodeError, TypeError, ValueError):
        fallback = {"nano-banana-2": 3.0, "nano-banana-pro": 4.0}
        return float(fallback.get(model_id, 3.0))

async def get_user_by_id(db, user_id: int):
    res = await db.execute(select(models.User).filter(models.User.id == user_id))
    return res.scalar_one_or_none()

async def get_user_by_yandex_id(db, yandex_id: str):
    res = await db.execute(select(models.User).filter(models.User.yandex_id == yandex_id))
    return res.scalar_one_or_none()

async def get_user_by_vk_id(db, vk_id: str):
    res = await db.execute(select(models.User).filter(models.User.vk_id == vk_id))
    return res.scalar_one_or_none()

async def get_or_create_user(db, user_id: int, name: str = None, username: str = None):
    # Try by internal/telegram ID first
    user = await get_user_by_id(db, user_id)
    if not user:
        # Initial balance and model for new users
        starting_balance = float(os.getenv("STARTING_BALANCE", 5.0))
        default_model = os.getenv("DEFAULT_MODEL", "nano-banana-2")
        user = models.User(
            id=user_id, 
            name=name or username, 
            balance=starting_balance,
            model_preference=default_model
        )
        db.add(user)
        # Handle referral case if needed (not implemented here for web yet)
        await db.commit()
        await db.refresh(user)
        logger.info(f"Created new user: {user_id} ({name}) with {starting_balance} cr.")
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
        image_url=None, # This is the result URL, keep empty until success
        prompt_image_url=image_urls[0] if image_urls else None, # Store the first input image as prompt reference
        prompt_images_json=json.dumps(image_urls) if image_urls else None, # Store all images as JSON
        credits_cost=cost
    )
    try:
        db.add(new_task)
        await db.commit()
        await db.refresh(new_task)
    except Exception as e:
        logger.error(f"Error saving task to DB: {e}")
        raise ValueError(translate_error(str(e)))
    
    # Call KIE
    res = await create_task(model_id, prompt, image_urls, aspect_ratio, resolution, output_format)
    if not res["success"]:
        raise Exception(res.get("error", "Unknown API error from KIE"))
        
    return res["taskId"]

async def check_generation_status(task_id: str):
    """Wrapper for KIE recordInfo with Russian error translation"""
    info = await get_task_info(task_id)
    kie_status = info.get("state", "").lower()
    if kie_status in ["failed", "error", "cancelled", "rejected", "blocked"] or info.get("success") is False:
        err_text = info.get("error", "Неизвестная ошибка на стороне нейросети.")
        raise Exception(err_text)
    
    if not info.get("success"):
        err = info.get("error", "Unknown error")
        # Try to find a translation
        for key, val in ERRORS_RU.items():
            if key.lower() in err.lower():
                info["error"] = val
                break
        else:
            info["error"] = f"Ошибка ({err})"
    return info


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
    
    # Payment stats
    total_revenue = (await db.execute(
        select(func.sum(models.Payment.amount_rub))
        .filter(models.Payment.status == "succeeded")
    )).scalar() or 0.0
    
    revenue_today = (await db.execute(
        select(func.sum(models.Payment.amount_rub))
        .filter(models.Payment.status == "succeeded")
        .filter(cast(models.Payment.created_at, Date) == today)
    )).scalar() or 0.0
    
    # Revenue chart (last 7 days)
    chart_data = []
    for i in range(6, -1, -1):
        day = today - datetime.timedelta(days=i)
        day_rev = (await db.execute(
            select(func.sum(models.Payment.amount_rub))
            .filter(models.Payment.status == "succeeded")
            .filter(cast(models.Payment.created_at, Date) == day)
        )).scalar() or 0.0
        
        day_users = (await db.execute(
            select(func.count(models.User.id))
            .filter(cast(models.User.created_at, Date) == day)
        )).scalar() or 0
        
        chart_data.append({
            "date": day.strftime("%d.%m"),
            "revenue": day_rev,
            "new_users": day_users
        })

    return {
        "total_users": total_users,
        "new_users_today": new_users_today,
        "total_gens": total_gens,
        "gens_today": gens_today,
        "total_revenue": total_revenue,
        "revenue_today": revenue_today,
        "chart_data": chart_data
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

async def get_user_history(db, user_id: int):
    # Fetch last 50 tasks for this user
    res = await db.execute(
        select(models.GenerationTask)
        .filter(models.GenerationTask.user_id == user_id)
        .order_by(models.GenerationTask.created_at.desc())
        .limit(50)
    )
    return res.scalars().all()

async def create_yookassa_payment(db, user_id: int, amount: float, description: str):
    import aiohttp
    import uuid
    
    shop_id = os.getenv("YOOKASSA_SHOP_ID")
    secret_key = os.getenv("YOOKASSA_SECRET_KEY")
    frontend_url = os.getenv("FRONTEND_URL", "http://localhost:3000")
    
    if not shop_id or not secret_key:
        raise Exception("YooKassa credentials are not set in .env")

    url = "https://api.yookassa.ru/v3/payments"
    idempotence_key = str(uuid.uuid4())
    headers = {
        "Idempotence-Key": idempotence_key,
        "Content-Type": "application/json"
    }
    auth = aiohttp.BasicAuth(shop_id, secret_key)
    
    payload = {
        "amount": {"value": f"{amount:.2f}", "currency": "RUB"},
        "confirmation": {"type": "redirect", "return_url": frontend_url},
        "description": description,
        "capture": True,
        "metadata": {"user_id": str(user_id)}
    }
    
    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=payload, headers=headers, auth=auth) as resp:
            data = await resp.json()
            if resp.status == 200:
                payment_url = data["confirmation"]["confirmation_url"]
                provider_id = data["id"]
                
                # SAVE TO DB
                new_payment = models.Payment(
                    user_id=user_id,
                    amount_rub=amount,
                    status="pending",
                    payment_url=payment_url,
                    provider_payment_id=provider_id
                )
                db.add(new_payment)
                await db.commit()
                
                return payment_url
            else:
                logger.error(f"YooKassa API Error: {data}")
                raise Exception(data.get("description", "YooKassa error"))
