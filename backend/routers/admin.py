import os
import jwt
from datetime import datetime, timedelta, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func, cast, Date
from pydantic import BaseModel

from backend.database import get_db
from backend import models

router = APIRouter(prefix="/admin", tags=["Admin"])

# Use custom admin secret for security
SECRET_KEY = os.getenv("JWT_ADMIN_SECRET", "snova_admin_fallback_secret")
ALGORITHM = "HS256"

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/admin/token")

def verify_admin_token(token: str = Depends(oauth2_scheme)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise HTTPException(status_code=401, detail="Invalid admin token")
        return username
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid admin token")

@router.post("/token")
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    admin_user = os.getenv("ADMIN_USER", "admin")
    admin_pass = os.getenv("ADMIN_PASS", "supersecret")
    
    if form_data.username != admin_user or form_data.password != admin_pass:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    expire = datetime.now(timezone.utc) + timedelta(hours=24)
    encoded_jwt = jwt.encode({"sub": form_data.username, "exp": expire}, SECRET_KEY, algorithm=ALGORITHM)
    return {"access_token": encoded_jwt, "token_type": "bearer"}

@router.get("/stats")
async def get_stats(db: AsyncSession = Depends(get_db), admin: str = Depends(verify_admin_token)):
    """Returns data for charts (last 7 days registration and generation activity)"""
    today = datetime.now(timezone.utc).date()
    stats_data = []
    
    for i in range(6, -1, -1):
        day = today - timedelta(days=i)
        
        # User registrations
        user_count = (await db.execute(
            select(func.count(models.User.id))
            .filter(cast(models.User.created_at, Date) == day)
        )).scalar() or 0
        
        # Generations
        gen_count = (await db.execute(
            select(func.count(models.GenerationTask.id))
            .filter(cast(models.GenerationTask.created_at, Date) == day)
        )).scalar() or 0
        
        stats_data.append({
            "date": day.strftime("%d.%m"),
            "users": user_count,
            "generations": gen_count
        })
    
    total_users = (await db.execute(select(func.count(models.User.id)))).scalar() or 0
    total_gens = (await db.execute(select(func.count(models.GenerationTask.id)))).scalar() or 0
    
    return {
        "success": True,
        "summary": {
            "total_users": total_users,
            "total_generations": total_gens,
            "new_today": stats_data[-1]["users"]
        },
        "chart": stats_data
    }

@router.get("/users")
async def list_users(db: AsyncSession = Depends(get_db), admin: str = Depends(verify_admin_token)):
    res = await db.execute(select(models.User).order_by(models.User.created_at.desc()).limit(100))
    return res.scalars().all()

class BalanceUpdate(BaseModel):
    amount: float

@router.post("/users/{user_id}/balance")
async def update_balance(user_id: int, req: BalanceUpdate, db: AsyncSession = Depends(get_db), admin: str = Depends(verify_admin_token)):
    res = await db.execute(select(models.User).filter_by(id=user_id))
    user = res.scalars().first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    user.balance += req.amount
    await db.commit()
    await db.refresh(user)
    return {"success": True, "new_balance": user.balance}
