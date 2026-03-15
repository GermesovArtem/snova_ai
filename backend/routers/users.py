from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from pydantic import BaseModel
from typing import Optional

from backend.database import get_db
from backend.models.user import UserDB

router = APIRouter(prefix="/users", tags=["Users"])

class UserCreate(BaseModel):
    telegram_id: int
    username: Optional[str] = None
    referrer_id: Optional[str] = None

class UserResponse(BaseModel):
    id: int
    telegram_id: int
    username: Optional[str] = None
    balance: float
    role: str

    class Config:
        from_attributes = True

@router.post("/", response_model=UserResponse)
async def get_or_create_user(user: UserCreate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(UserDB).filter_by(telegram_id=user.telegram_id))
    db_user = result.scalars().first()
    
    if db_user:
        return db_user
        
    new_user = UserDB(
        telegram_id=user.telegram_id, 
        username=user.username,
        referrer_id=user.referrer_id
    )
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    return new_user

@router.get("/{telegram_id}/referrals")
async def get_referral_stats(telegram_id: int, db: AsyncSession = Depends(get_db)):
    # Находим юзера
    result = await db.execute(select(UserDB).filter_by(telegram_id=telegram_id))
    user = result.scalars().first()
    if not user:
         raise HTTPException(status_code=404, detail="User not found")
    
    # Считаем количество рефералов
    ref_result = await db.execute(select(UserDB).filter_by(referrer_id=str(telegram_id)))
    referrals = ref_result.scalars().all()
    
    # Подсчет бонусов с рефералов (проходим по транзакциям) - упрощенно просто возвращаем количество
    return {
        "referral_count": len(referrals),
        "referral_link": f"https://t.me/your_bot_name?start=r-{telegram_id}"
    }

@router.get("/{telegram_id}/balance", response_model=float)
async def get_balance(telegram_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(UserDB).filter_by(telegram_id=telegram_id))
    db_user = result.scalars().first()
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")
    return db_user.balance

class BalanceAdd(BaseModel):
    amount: float

@router.post("/{telegram_id}/add_balance", response_model=float)
async def add_balance(telegram_id: int, request: BalanceAdd, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(UserDB).filter_by(telegram_id=telegram_id))
    db_user = result.scalars().first()
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")
    
    db_user.balance += request.amount
    await db.commit()
    await db.refresh(db_user)
    return db_user.balance

