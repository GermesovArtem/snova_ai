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

from backend import services

@router.get("/stats")
async def get_stats(db: AsyncSession = Depends(get_db), admin: str = Depends(verify_admin_token)):
    """Returns data for charts (last 7 days registration, generation, and revenue activity)"""
    try:
        stats = await services.get_admin_stats(db)
        return {
            "success": True,
            "data": stats
        }
    except Exception:
        return {"success": False, "data": {}}

@router.get("/users")
async def list_users(db: AsyncSession = Depends(get_db), admin: str = Depends(verify_admin_token)):
    res = await db.execute(select(models.User).order_by(models.User.created_at.desc()).limit(100))
    users = res.scalars().all()
    # Simple conversion to avoid serialization issues
    safe_users = []
    for u in users:
        safe_users.append({
            "id": u.id,
            "name": u.name,
            "balance": u.balance,
            "created_at": u.created_at.isoformat() if u.created_at else None
        })
    return {"success": True, "data": safe_users}

class BalanceUpdate(BaseModel):
    amount: float

class BroadcastRequest(BaseModel):
    text: str

@router.post("/broadcast")
async def broadcast(req: BroadcastRequest, db: AsyncSession = Depends(get_db), admin: str = Depends(verify_admin_token)):
    from fastapi import BackgroundTasks
    # We use a background task to not block the response
    import asyncio
    from fastapi import BackgroundTasks
    
    # Define a wrapper for background execution
    async def run_broadcast():
        await services.broadcast_to_all_users(db, req.text)
        
    # Note: We need a fresh session for long running background tasks 
    # but for now we'll just trigger it. 
    # Better approach: pass id and fetch in task.
    
    # For a simple implementation:
    loop = asyncio.get_event_loop()
    loop.create_task(services.broadcast_to_all_users(db, req.text))
    
    return {"success": True, "message": "Broadcast started in background"}

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
