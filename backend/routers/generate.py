from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from backend.database import get_db
from backend.models.user import UserDB
from backend.services.generator import generate_image

from backend.models.transaction import TransactionDB
from backend.models import GenerationTask

router = APIRouter(prefix="/generate", tags=["Generation"])

class GenerateRequest(BaseModel):
    telegram_id: int
    prompt: str
    model: str = "nano-banana"
    cost: float = 5.0 # default TS cost

class GenerateResponse(BaseModel):
    image_url: str
    remaining_balance: float

@router.post("/", response_model=GenerateResponse)
async def generate(request: GenerateRequest, db: AsyncSession = Depends(get_db)):
    # 1. Загружаем пользователя
    result = await db.execute(select(UserDB).filter_by(telegram_id=request.telegram_id))
    user = result.scalars().first()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    if user.balance < request.cost:
        raise HTTPException(status_code=402, detail="Insufficient balance")
        
    # 2. Морозим баланс (Lock)
    user.balance -= request.cost
    user.frozen_balance += request.cost
    await db.commit()
    
    # 3. Запрос к AI
    try:
        image_url = await generate_image(request.prompt, request.model)
    except Exception as e:
        # 4a. Откат баланса при ошибке
        user.balance += request.cost
        user.frozen_balance -= request.cost
        await db.commit()
        raise HTTPException(status_code=500, detail=str(e))
        
    # Успешное списание
    user.frozen_balance -= request.cost
    
    # Запись транзакции
    tx = TransactionDB(user_id=user.id, amount=-request.cost, type="gen", status="completed")
    db.add(tx)
    
    # Запись истории
    gen_task = GenerationTask(
        user_id=user.id,
        model=request.model,
        prompt=request.prompt,
        image_url=image_url,
        status="completed",
        credits_cost=int(request.cost),
        tool="image"
    )
    db.add(gen_task)
    
    await db.commit()
    await db.refresh(user)
    
    return GenerateResponse(image_url=image_url, remaining_balance=user.balance)
