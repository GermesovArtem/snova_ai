import logging
import os
import json
import traceback
from typing import List
from dotenv import load_dotenv
import datetime
from sqlalchemy import func, cast, Date, desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from . import models
from .kie_api import create_task, get_task_info
import uuid

load_dotenv()

logger = logging.getLogger(__name__)

ERRORS_RU = {
    "Could not generate images": "Не удалось создать изображение с этими данными. Попробуйте изменить текст или фото.",
    "UndefinedColumnError": "Техническая ошибка: база данных устарела. Обратитесь к админу.",
    "ProgrammingError": "Техническая ошибка в запросе к базе данных.",
    "Internal Server Error": "Внутренняя ошибка сервера. Мы уже работаем над этим!",
    "timeout": "Время ожидания истекло. Пожалуйста, попробуйте еще раз через минуту.",
    "ConnectionError": "Ошибка соединения с сервером. Проверьте интернет или подождите.",
    "violated Google's Generative AI Prohibited Use policy": "Ваш запрос был отклонен фильтром безопасности ИИ (нарушение политики использования). Пожалуйста, измените описание или фото на более нейтральные.",
    "No images found in AI response": "Изображение не было создано ИИ. Попробуйте изменить запрос.",
    "insufficient_funds": "Недостаточно средств на балансе сервиса генерации.",
    "high demand": "Нейросеть временно перегружена запросами со всего мира. Пожалуйста, подождите минутку и попробуйте снова.",
    "e003": "Нейросеть временно занята из-за высокой нагрузки (Код: E003). Попробуйте еще раз через минуту.",
    "unavailable": "Сервис временно недоступен. Ведутся технические работы или нагрузка слишком высока.",
    "rate limit": "Вы отправляете запросы слишком часто. Пожалуйста, немного подождите."
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
    """Нормализация ID моделей для внутренней логики (цены, UI)."""
    if not model_id or not isinstance(model_id, str): return model_id
    
    m = model_id.lower().strip()
    
    # Резолюционные варианты (внутренние ID)
    variants = ["nano-banana-2-1k", "nano-banana-2-4k", "nano-banana-pro-2k", "nano-banana-pro-4k"]
    if m in variants:
        return m

    # Маппинг полных путей KIE в наши внутренние варианты
    if "nano-banana-pro" in m:
        return "nano-banana-pro-4k" if "4k" in m else "nano-banana-pro-2k"
    if "nano-banana-2" in m:
        return "nano-banana-2-4k" if "4k" in m else "nano-banana-2-1k"
    if "nano-banana" in m and "edit" not in m:
        return "nano-banana-2-1k"
        
    return m

def get_model_limit(model_id: str) -> int:
    """Returns official limit for image_input: 8 for PRO, 14 for v2"""
    if "pro" in str(model_id).lower():
        return 8
    return 14

def get_available_models():
    default_models = {
        "Nano Banana 2 (1K)": "nano-banana-2-1k",
        "Nano Banana 2 (4K)": "nano-banana-2-4k",
        "Nano Banana PRO (2K)": "nano-banana-pro-2k",
        "Nano Banana PRO (4K)": "nano-banana-pro-4k"
    }
    models_str = os.getenv("AVAILABLE_MODELS")
    if not models_str:
        return default_models
    try:
        return json.loads(models_str)
    except:
        return default_models

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
    
    # New variant costs
    variant_costs = {
        "nano-banana-2-1k": 1.0,
        "nano-banana-2-4k": 2.0,
        "nano-banana-pro-2k": 2.0,
        "nano-banana-pro-4k": 3.0
    }
    if model_id in variant_costs:
        return variant_costs[model_id]

    # Default fallback prices without 'google/' prefix to match normalization
    costs_str = os.getenv("CREDITS_PER_MODEL")
    if costs_str:
        try:
            costs = json.loads(costs_str)
            normalized_costs = {normalize_model_id(k): v for k, v in costs.items()}
            if model_id in normalized_costs:
                return float(normalized_costs[model_id])
        except (json.JSONDecodeError, TypeError, ValueError):
            pass
            
    fallback = {"nano-banana-2": 2.0, "nano-banana-pro": 3.0, "google/nano-banana": 1.0}
    return float(fallback.get(model_id, 2.0))

async def get_user_by_id(db, user_id: int):
    res = await db.execute(select(models.User).filter(models.User.id == user_id))
    return res.scalar_one_or_none()

async def get_user_by_yandex_id(db, yandex_id: str):
    res = await db.execute(select(models.User).filter(models.User.yandex_id == yandex_id))
    return res.scalar_one_or_none()

async def get_user_by_vk_id(db, vk_id: str):
    res = await db.execute(select(models.User).filter(models.User.vk_id == vk_id))
    return res.scalar_one_or_none()

async def get_active_generation_tasks(db: AsyncSession, user_id: int):
    """Finds tasks that are currently waiting for KIE AI result."""
    res = await db.execute(
        select(models.GenerationTask)
        .where(models.GenerationTask.user_id == user_id)
        .where(models.GenerationTask.status.in_(["pending", "processing"]))
        .order_by(desc(models.GenerationTask.created_at))
    )
    return res.scalars().all()

async def get_or_create_user(db, user_id: int, name: str = None, username: str = None):
    # Try by internal/telegram ID first
    user = await get_user_by_id(db, user_id)
    created = False
    if not user:
        # Initial balance and model for new users
        starting_balance = float(os.getenv("STARTING_BALANCE", 5.0))
        default_model = os.getenv("DEFAULT_MODEL", "nano-banana-2-1k")
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
        logger.info(f"Created new user: {user_id} ({name}) with {starting_balance} ⚡.")
        created = True
    return user, created

async def pre_charge_generation(db, user: models.User, model_id: str) -> float:
    """Freezes user balance before generation"""
    cost = get_model_cost(model_id)
    if user.balance < cost:
        raise ValueError("Недостаточно ⚡!")
        
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

async def commit_frozen_credits(db: AsyncSession, user_id: int, cost: float):
    """Permanently deducts frozen credits upon success"""
    res = await db.execute(select(models.User).filter_by(id=user_id))
    user = res.scalars().first()
    if user:
        user.frozen_balance -= cost
        await db.commit()

async def start_generation_flow(
    db: AsyncSession, 
    user_id: int, 
    prompt: str, 
    image_paths: List[str] = [], 
    model_id: str = "nano-banana-2", 
    cost: float = 1.0,
    aspect_ratio: str = "1:1",
    resolution: str = "1K",
    output_format: str = "png",
    status_message_id: int = None
) -> str:
    """
    Initializes generation task in DB, freezes credits, and calls KIE AI.
    Returns the task_uuid.
    """
    # 1. Normalize model
    model_id = normalize_model_id(model_id)
    
    # 2. Check balance
    user = await get_user_by_id(db, user_id)
    if not user or (user.balance - user.frozen_balance) < cost:
        raise Exception("insufficient_funds")

    # 3. Freeze credits
    user.frozen_balance += cost
    db.add(user)
    
    # 4. Create Task record
    new_task = models.GenerationTask(
        user_id=user_id,
        model=model_id,
        prompt=prompt,
        credits_cost=cost,
        status_message_id=status_message_id,
        prompt_image_url=image_paths[0] if image_paths else None,
        prompt_images_json=json.dumps(image_paths) if image_paths else None
    )
    db.add(new_task)
    await db.commit()
    await db.refresh(new_task)

    # 5. Call KIE AI
    try:
        kie_task_id = await create_task(
            prompt=prompt, 
            image_urls=image_paths, 
            model=model_id, 
            aspect_ratio=aspect_ratio, 
            resolution=resolution,
            output_format=output_format
        )
        # Link UUIDs
        new_task.task_uuid = kie_task_id
        await db.commit()
        return kie_task_id
    except Exception as e:
        # Refund on failure
        user.frozen_balance -= cost
        new_task.status = "failed"
        await db.commit()
        raise e

async def background_poll_kie_task(db_factory, user_id: int, task_uuid: str, status_message_id: int = None):
    """
    Background task to poll KIE AI and finalize the task. 
    Just like start_generation_wrapper in bot/main.py but for Web.
    """
    import asyncio # Ensure it's imported
    try:
        # Loop for 10 minutes
        for i in range(120):
            await asyncio.sleep(5)
            info = await check_generation_status(task_uuid)
            status = info.get("state")
            
            if status in ["success", "completed"] and info.get("image_url"):
                async with db_factory() as db:
                    # Finalize credits
                    res = await db.execute(select(models.GenerationTask).filter_by(task_uuid=task_uuid))
                    task = res.scalars().first()
                    if not task: return
                    
                    cost = task.credits_cost
                    await commit_frozen_credits(db, user_id, cost)
                    
                    # Update task
                    task.status = "completed"
                    task.image_url = info.get("image_url")
                    
                    # Update status bubble if web message ID provided
                    if status_message_id:
                        msg_res = await db.execute(select(models.WebChatMessage).filter_by(id=status_message_id))
                        msg = msg_res.scalars().first()
                        if msg:
                            msg.role = "bot-result"
                            msg.text = "🔥 **Результат готов!**"
                            msg.image_url = info.get("image_url")
                    
                    await db.commit()
                return
            
            elif status in ["failed", "error", "cancelled"]:
                async with db_factory() as db:
                    res = await db.execute(select(models.GenerationTask).filter_by(task_uuid=task_uuid))
                    task = res.scalars().first()
                    if task:
                        await refund_frozen_credits(db, user_id, task.credits_cost)
                        task.status = "failed"
                        
                        if status_message_id:
                            msg_res = await db.execute(select(models.WebChatMessage).filter_by(id=status_message_id))
                            msg = msg_res.scalars().first()
                            if msg:
                                err_text = translate_error(info.get("error", ""))
                                msg.text = f"❌ **Ошибка:** {err_text or 'Генерация не удалась'}"
                        
                    await db.commit()
                return
                
        # Timeout
        async with db_factory() as db:
            res = await db.execute(select(models.GenerationTask).filter_by(task_uuid=task_uuid))
            task = res.scalars().first()
            if task:
                await refund_frozen_credits(db, user_id, task.credits_cost)
                task.status = "failed"
                if status_message_id:
                    msg_res = await db.execute(select(models.WebChatMessage).filter_by(id=status_message_id))
                    msg = msg_res.scalars().first()
                    if msg:
                        msg.text = "⚠️ **Тайм-аут.** Проверьте историю позже."
            await db.commit()
            
    except Exception as e:
        import logging
        logging.getLogger("backend.services").error(f"Background polling failed for {task_uuid}: {e}", exc_info=True)

async def check_generation_status(task_id: str):
    """Wrapper for KIE recordInfo with Russian error translation"""
    info = await get_task_info(task_id)
    
    # Check for failure states
    state = info.get("state", "").lower()
    is_failed = state in ["fail", "failed", "failure", "error", "cancelled", "rejected", "blocked"] or not info.get("success")
    
    if is_failed:
        err = info.get("error", "Unknown error")
        # Translate the error if possible
        for key, val in ERRORS_RU.items():
            if key.lower() in str(err).lower():
                info["error"] = val
                break
        else:
            info["error"] = f"Ошибка ({err})"
        
        # Ensure state is 'failed' for consistent handling in bot/frontend
        if state not in ["error", "failed"]:
            info["state"] = "failed"
            
    return info


# --- Admin API ---
import datetime

async def get_admin_stats(db) -> dict:
    logger.info("Fetching admin statistics...")
    try:
        try:
            today_start = datetime.datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        except Exception as e:
            logger.error(f"Error calculating today_start: {e}")
            raise
        
        # User stats
        total_users = (await db.execute(select(func.count(models.User.id)))).scalar() or 0
        new_users_today = (await db.execute(
            select(func.count(models.User.id))
            .filter(models.User.created_at >= today_start)
        )).scalar() or 0
        
        # Gen stats
        total_gens = (await db.execute(select(func.count(models.GenerationTask.id)))).scalar() or 0
        gens_today = (await db.execute(
            select(func.count(models.GenerationTask.id))
            .filter(models.GenerationTask.created_at >= today_start)
        )).scalar() or 0
        
        # Payment stats
        total_revenue = (await db.execute(
            select(func.sum(models.Payment.amount_rub))
            .filter(models.Payment.status == "succeeded")
        )).scalar() or 0.0
        
        revenue_today = (await db.execute(
            select(func.sum(models.Payment.amount_rub))
            .filter(models.Payment.status == "succeeded")
            .filter(models.Payment.created_at >= today_start)
        )).scalar() or 0.0
        
        # Revenue chart (last 7 days)
        chart_data = []
        for i in range(6, -1, -1):
            day_s = today_start - datetime.timedelta(days=i)
            day_e = day_s + datetime.timedelta(days=1)
            
            day_rev = (await db.execute(
                select(func.sum(models.Payment.amount_rub))
                .filter(models.Payment.status == "succeeded")
                .filter(models.Payment.created_at >= day_s)
                .filter(models.Payment.created_at < day_e)
            )).scalar() or 0.0
            
            day_users = (await db.execute(
                select(func.count(models.User.id))
                .filter(models.User.created_at >= day_s)
                .filter(models.User.created_at < day_e)
            )).scalar() or 0
            
            chart_data.append({
                "date": day_s.strftime("%d.%m"),
                "revenue": float(day_rev),
                "new_users": int(day_users)
            })

        return {
            "total_users": int(total_users),
            "new_users_today": int(new_users_today),
            "total_gens": int(total_gens),
            "gens_today": int(gens_today),
            "total_revenue": float(total_revenue),
            "revenue_today": float(revenue_today),
            "chart_data": chart_data
        }
    except Exception as e:
        logger.error(f"CRITICAL ERROR in get_admin_stats: {e}")
        logger.error(traceback.format_exc())
        return {
            "total_users": 0,
            "new_users_today": 0,
            "total_gens": 0,
            "gens_today": 0,
            "total_revenue": 0.0,
            "revenue_today": 0.0,
            "chart_data": [],
            "error": str(e)
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
    # Fetch last 50 completed tasks for this user
    res = await db.execute(
        select(models.GenerationTask)
        .filter(models.GenerationTask.user_id == user_id)
        .filter(models.GenerationTask.status == "completed")
        .filter(models.GenerationTask.image_url.isnot(None))
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

async def broadcast_to_all_users(db, text: str):
    """Sends a Telegram message to all registered users with rate limiting."""
    import aiohttp
    import asyncio
    
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        logger.error("TELEGRAM_BOT_TOKEN not set for broadcast")
        return
        
    res = await db.execute(select(models.User.id))
    user_ids = res.scalars().all()
    
    logger.info(f"Starting broadcast to {len(user_ids)} users...")
    
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    
    async with aiohttp.ClientSession() as session:
        for i, user_id in enumerate(user_ids):
            try:
                payload = {"chat_id": user_id, "text": text, "parse_mode": "HTML"}
                async with session.post(url, json=payload) as resp:
                    if resp.status == 429: # Too many requests
                        retry_after = (await resp.json()).get("parameters", {}).get("retry_after", 1)
                        logger.warning(f"Rate limited by Telegram. Waiting {retry_after}s...")
                        await asyncio.sleep(retry_after)
                        # Retry once
                        await session.post(url, json=payload)
                    elif resp.status == 403:
                        logger.warning(f"User {user_id} blocked the bot. Skipping.")
                    elif resp.status != 200:
                        data = await resp.json()
                        logger.error(f"Failed to send broadcast to {user_id}: {data}")
            except Exception as e:
                logger.error(f"Error sending broadcast to {user_id}: {e}")
            
            # Rate limiting: ~25 messages per second
            if (i + 1) % 25 == 0:
                await asyncio.sleep(1)
                
    logger.info("Broadcast completed.")

async def save_web_message(db, user_id: int, role: str, text: str = None, image_url: str = None, meta: dict = None):
    new_msg = models.WebChatMessage(
        user_id=user_id,
        role=role,
        text=text,
        image_url=image_url,
        meta=json.dumps(meta) if meta else None
    )
    db.add(new_msg)
    await db.commit()
    return new_msg

async def update_web_message(db, user_id: int, msg_id: int, text: str = None, meta: dict = None):
    res = await db.execute(select(models.WebChatMessage).filter_by(id=msg_id, user_id=user_id))
    msg = res.scalars().first()
    if msg:
        if text is not None: msg.text = text
        if meta is not None: msg.meta = json.dumps(meta)
        await db.commit()
        return msg
    return None

async def delete_web_message(db, user_id: int, msg_id: int):
    res = await db.execute(select(models.WebChatMessage).filter_by(id=msg_id, user_id=user_id))
    msg = res.scalars().first()
    if msg:
        await db.delete(msg)
        await db.commit()
        return True
    return False

async def get_web_messages(db, user_id: int, limit: int = 50):
    res = await db.execute(
        select(models.WebChatMessage)
        .filter(models.WebChatMessage.user_id == user_id)
        .order_by(models.WebChatMessage.timestamp.asc())
        .limit(limit)
    )
    return res.scalars().all()
