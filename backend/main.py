from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager

from backend.database import engine, Base
from backend.routers import users, generate, payments, admin
from backend.models.user import UserDB
from backend.models.transaction import TransactionDB
from backend.models.payout import PayoutDB
from backend.models.setting import SettingDB

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Создаем таблицы при старте, если их нет
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    # Логика при выключении (если нужна)
    await engine.dispose()

app = FastAPI(title="Scalable Bot API", lifespan=lifespan)

app.include_router(users.router)
app.include_router(generate.router)
app.include_router(payments.router)
app.include_router(admin.router)

# Служим статичный фронтенд для админки
import os
os.makedirs("static", exist_ok=True)
app.mount("/admin-panel", StaticFiles(directory="static", html=True), name="static")

@app.get("/")
async def root():
    return {"message": "API is running"}
