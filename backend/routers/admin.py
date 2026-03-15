import os
import jwt
from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from pydantic import BaseModel

from backend.database import get_db
from backend.models.user import UserDB
from backend.models.transaction import TransactionDB
from backend.models.payout import PayoutDB

router = APIRouter(prefix="/admin", tags=["Admin"])

SECRET_KEY = os.getenv("JWT_SECRET", "supersecretkey")
ALGORITHM = "HS256"

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/admin/token")

def verify_token(token: str = Depends(oauth2_scheme)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise HTTPException(status_code=401, detail="Invalid token")
        return username
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

@router.post("/token")
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    # Simple hardcoded check against env
    admin_user = os.getenv("ADMIN_USER", "admin")
    admin_pass = os.getenv("ADMIN_PASS", "supersecret")
    
    if form_data.username != admin_user or form_data.password != admin_pass:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    expire = datetime.utcnow() + timedelta(hours=24)
    encoded_jwt = jwt.encode({"sub": form_data.username, "exp": expire}, SECRET_KEY, algorithm=ALGORITHM)
    return {"access_token": encoded_jwt, "token_type": "bearer"}

@router.get("/users")
async def get_users(db: AsyncSession = Depends(get_db), current_admin: str = Depends(verify_token)):
    res = await db.execute(select(UserDB))
    users = res.scalars().all()
    return users

class BalanceUpdate(BaseModel):
    amount: float

@router.post("/users/{telegram_id}/balance")
async def update_balance(telegram_id: int, req: BalanceUpdate, db: AsyncSession = Depends(get_db), current_admin: str = Depends(verify_token)):
    res = await db.execute(select(UserDB).filter_by(telegram_id=telegram_id))
    user = res.scalars().first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    user.balance += req.amount
    
    # Log manual transaction
    tx = TransactionDB(user_id=user.id, amount=req.amount, type="admin_payout", status="completed")
    db.add(tx)
    
    await db.commit()
    await db.refresh(user)
    return {"message": "Balance updated", "new_balance": user.balance}

@router.get("/transactions")
async def get_transactions(db: AsyncSession = Depends(get_db), current_admin: str = Depends(verify_token)):
    res = await db.execute(select(TransactionDB).order_by(TransactionDB.created_at.desc()).limit(100))
    txs = res.scalars().all()
    return txs

@router.get("/payouts")
async def get_payouts(db: AsyncSession = Depends(get_db), current_admin: str = Depends(verify_token)):
    res = await db.execute(select(PayoutDB).order_by(PayoutDB.created_at.desc()))
    payouts = res.scalars().all()
    return payouts

class PayoutStatusUpdate(BaseModel):
    status: str # completed or rejected

@router.post("/payouts/{payout_id}/status")
async def update_payout_status(payout_id: int, req: PayoutStatusUpdate, db: AsyncSession = Depends(get_db), current_admin: str = Depends(verify_token)):
    res = await db.execute(select(PayoutDB).filter_by(id=payout_id))
    payout = res.scalars().first()
    if not payout:
        raise HTTPException(status_code=404, detail="Payout not found")
        
    payout.status = req.status
    
    # If rejected, refund the user? (TS says "Запрос причины -> Возврат средств")
    if req.status == "rejected":
        user_res = await db.execute(select(UserDB).filter_by(id=payout.user_id))
        user = user_res.scalars().first()
        if user:
            user.balance += payout.amount
            db.add(TransactionDB(user_id=user.id, amount=payout.amount, type="refund", status="completed"))
            
    await db.commit()
    return {"message": f"Payout marked as {req.status}"}
