from fastapi import APIRouter, Depends, Request, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

import uuid
from yookassa import Configuration, Payment
from pydantic import BaseModel

from backend.database import get_db
from backend.models.user import UserDB
from backend.models.transaction import TransactionDB
from backend.settings import settings

router = APIRouter(prefix="/payments", tags=["Payments"])

# Настраиваем SDK ЮKassa
Configuration.account_id = settings.shop_id
Configuration.secret_key = settings.secret_key

class CreatePaymentRequest(BaseModel):
    telegram_id: int
    amount: float
    description: str

@router.post("/create")
async def create_payment(request: CreatePaymentRequest):
    """Создает платеж и возвращает ссылку на оплату"""
    idempotence_key = str(uuid.uuid4())
    
    payment_data = {
        "amount": {
            "value": str(request.amount),
            "currency": "RUB"
        },
        "confirmation": {
            "type": "redirect",
            "return_url": "https://t.me/your_bot_name" # Твой бот
        },
        "capture": True,
        "description": request.description,
        "metadata": {
            "telegram_id": request.telegram_id
        }
    }
    
    try:
        # SDK синхронная, но сетевой вызов быстрый. 
        # В идеале завернуть в run_in_executor
        payment = Payment.create(payment_data, idempotence_key)
        return {"url": payment.confirmation.confirmation_url, "payment_id": payment.id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/webhook")
async def yookassa_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    """
    Вебхук от ЮKassa.
    В реальном проекте здесь должна быть валидация IP адресов ЮKassa.
    """
    try:
        data = await request.json()
    except:
        raise HTTPException(status_code=400, detail="Invalid JSON")
        
    event = data.get("event")
    
    # Ожидаем успешного платежа
    if event == "payment.succeeded":
        payment_obj = data.get("object", {})
        status = payment_obj.get("status")
        
        # ЮKassa позволяет передавать кастомную мету, берем оттуда ID юзера
        metadata = payment_obj.get("metadata", {})
        telegram_id = metadata.get("telegram_id")
        
        if not telegram_id or status != "succeeded":
            return {"status": "ignored"}
            
        amount_val = payment_obj.get("amount", {}).get("value")
        if not amount_val:
             return {"status": "ignored"}
             
        # Конвертируем рубли в кредиты (по какой-то логике, например 1 к 1 или 100р = 100кр)
        credits_added = float(amount_val)
        
        # 1. Находим юзера
        result = await db.execute(select(UserDB).filter_by(telegram_id=int(telegram_id)))
        user = result.scalars().first()
        
        if not user:
            return {"status": "user_not_found"}
            
        # 2. Начисляем баланс
        user.balance += credits_added
        
        # 3. Записываем транзакцию
        tx = TransactionDB(user_id=user.id, amount=credits_added, type="pay", status="completed")
        db.add(tx)
        
        # Если есть реферер - начислить ему бонус 10% (упрощенная логика из ТЗ)
        if user.referrer_id:
            try:
                ref_id = int(user.referrer_id)
                ref_res = await db.execute(select(UserDB).filter_by(telegram_id=ref_id))
                referrer = ref_res.scalars().first()
                if referrer:
                    bonus = credits_added * 0.10 # 10%
                    referrer.balance += bonus
                    db.add(TransactionDB(user_id=referrer.id, amount=bonus, type="ref", status="completed"))
            except ValueError:
                pass # Невалидный ID
        
        await db.commit()
        return {"status": "ok"}
        
    return {"status": "ignored"}
