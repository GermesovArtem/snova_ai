import os
import datetime
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
from .database import get_db
from . import models, services

# Учетные данные из .env
SECRET_KEY = os.getenv("JWT_SECRET", "supersecret-snnovaa-ai-2024")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7 # 7 дней

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/v1/auth/login")

def create_access_token(data: dict, expires_delta: Optional[datetime.timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.datetime.utcnow() + expires_delta
    else:
        expire = datetime.datetime.utcnow() + datetime.timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def get_current_user(token: str = Depends(oauth2_scheme), db: AsyncSession = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    
    # Try to find user by ID
    user = await services.get_user_by_id(db, int(user_id))
    if user is None:
        raise credentials_exception
    return user

import hashlib
import hmac

def verify_telegram_data(data: dict):
    """
    Проверка подлинности данных от Telegram Login Widget.
    https://core.telegram.org/widgets/login#checking-authorization
    """
    bot_token = os.getenv("BOT_TOKEN")
    if not bot_token:
        # Для локальной разработки без токена
        return True
        
    received_hash = data.get("hash")
    if not received_hash:
        return False
        
    # Формируем строку для проверки (все поля кроме hash, отсортированные)
    check_list = []
    for key, value in data.items():
        if key != 'hash' and value:
            check_list.append(f"{key}={value}")
    
    check_string = "\n".join(sorted(check_list))
    
    # Считаем секретный ключ (SHA256 от токена бота)
    secret_key = hashlib.sha256(bot_token.encode()).digest()
    
    # Считаем HMAC-SHA256
    hash_computed = hmac.new(secret_key, check_string.encode(), hashlib.sha256).hexdigest()
    
    return hash_computed == received_hash
