import asyncio
import logging
import os
import json
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart, Command
from aiogram.types import WebAppInfo, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from dotenv import load_dotenv

from backend.database import get_db, AsyncSessionLocal, engine, Base
from backend import services

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
WEB_APP_URL = os.getenv("WEB_APP_URL", "https://bananix.ai")
logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

logger = logging.getLogger(__name__)
media_groups = {} # media_group_id -> { "messages": [], "timer": asyncio.Task }

def get_available_models():
    models_str = os.getenv("AVAILABLE_MODELS", '{"NanoBanana": "nanobanana", "NanoBanana 2": "nano_banana_2", "NanoBanana PRO": "nanobanana_pro"}')
    try:
        return json.loads(models_str)
    except:
        return {"NanoBanana": "nanobanana", "NanoBanana 2": "nano_banana_2", "NanoBanana PRO": "nanobanana_pro"}

def build_main_kb(current_model: str):
    kb = InlineKeyboardBuilder()
    models = get_available_models()
    for name, mm in models.items():
        prefix = "✅ " if mm == current_model else ""
        kb.button(text=f"{prefix}{name}", callback_data=f"set_model:{mm}")
    
    kb.button(text="👤 Профиль и Баланс", callback_data="profile")
    kb.button(text="💳 Пополнить", callback_data="buy_credits")
    kb.adjust(1, 1, 1, 2)
    return kb.as_markup()

@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    async with AsyncSessionLocal() as db:
        user = await services.get_or_create_user(db, message.from_user.id, message.from_user.username)
        await message.answer(
            f"Привет, {user.name}! 👋\n\nВыбери модель нейросети и отправь промпт или фото:",
            reply_markup=build_main_kb(user.model_preference)
        )

@dp.callback_query(F.data == "main_menu")
async def process_main_menu(callback_query: CallbackQuery):
    async with AsyncSessionLocal() as db:
        user = await services.get_or_create_user(db, callback_query.from_user.id)
        await callback_query.message.edit_text(
            f"Выбери модель нейросети и отправь промпт или фото:",
            reply_markup=build_main_kb(user.model_preference)
        )

@dp.callback_query(F.data == "profile")
async def process_profile(callback_query: CallbackQuery):
    async with AsyncSessionLocal() as db:
        user = await services.get_or_create_user(db, callback_query.from_user.id)
        text = f"👤 <b>Профиль</b>\n\n💳 Баланс: {user.balance} кредитов\n🤖 Модель: {user.model_preference}\n❄️ Заморожено: {user.frozen_balance} кр."
        
        kb = InlineKeyboardBuilder()
        kb.button(text="💳 Купить кредиты", callback_data="buy_credits")
        kb.button(text="⬅️ Назад", callback_data="main_menu")
        kb.adjust(1)
        await callback_query.message.edit_text(text, reply_markup=kb.as_markup(), parse_mode="HTML")

def get_credit_packs():
    packs_str = os.getenv("CREDIT_PACKS", '{"149": 10}')
    try:
        return json.loads(packs_str)
    except:
        return {"149": 10}

@dp.callback_query(F.data == "buy_credits")
async def process_buy_credits(callback_query: CallbackQuery):
    packs = get_credit_packs()
    kb = InlineKeyboardBuilder()
    for price, amount in packs.items():
        kb.button(text=f"🍌 {amount} кр. — {price} руб.", callback_data=f"buy:{price}:{amount}")
    kb.button(text="⬅️ Назад", callback_data="profile")
    kb.adjust(1)
    await callback_query.message.edit_text("Выберите пакет кредитов для пополнения (оплата ЮKassa):", reply_markup=kb.as_markup())

@dp.callback_query(F.data.startswith("buy:"))
async def process_buy_packet(callback_query: CallbackQuery):
    _, price, amount = callback_query.data.split(":")
    await callback_query.answer(f"Создан счет на {price} руб. (имитация)", show_alert=True)

@dp.callback_query(F.data.startswith("set_model:"))
async def process_set_model(callback_query: CallbackQuery):
    model = callback_query.data.split(":")[1]
    async with AsyncSessionLocal() as db:
        user = await services.get_or_create_user(db, callback_query.from_user.id)
        user.model_preference = model
        await db.commit()
        await callback_query.message.edit_reply_markup(reply_markup=build_main_kb(user.model_preference))
        await callback_query.answer(f"Модель изменена на {model}")

@dp.message(F.media_group_id)
async def handle_media_group(message: types.Message):
    mg_id = message.media_group_id
    if mg_id not in media_groups:
        media_groups[mg_id] = {"messages": []}
        loop = asyncio.get_event_loop()
        media_groups[mg_id]["timer"] = loop.call_later(2.0, asyncio.create_task, process_media_group(mg_id, message.from_user.id))
    media_groups[mg_id]["messages"].append(message)

async def process_media_group(mg_id: str, user_id: int):
    data = media_groups.pop(mg_id, None)
    if not data: return
    messages = data["messages"]
    
    caption = next((m.caption for m in messages if m.caption), "Сделай красиво")
    await bot.send_message(user_id, f"Начинаем работу с альбомом ({len(messages)} фото)...")
    # For a real integration, Telegram photo URLs expire and bot_token is secret. We extract it here hypothetically:
    # prompt = caption
    # image_urls = [get_public_telegram_url(msg)] 
    
@dp.message(F.photo | F.text)
async def handle_single_prompt(message: types.Message):
    if message.media_group_id: return
    
    prompt = message.text or message.caption or ""
    user_id = message.from_user.id
    
    async with AsyncSessionLocal() as db:
        user = await services.get_or_create_user(db, user_id, message.from_user.username)
        try:
            cost = await services.pre_charge_generation(db, user, user.model_preference)
        except ValueError as e:
            await message.answer(f"❌ {e}")
            return
            
    msg_wait = await message.answer(f"⏳ Начинаю генерацию (Модель: {user.model_preference})...")
    asyncio.create_task(run_generation_task(user_id, prompt, cost, user.model_preference, msg_wait.message_id))

async def run_generation_task(user_id: int, prompt: str, cost: float, model: str, msg_id: int):
    try:
        async with AsyncSessionLocal() as db:
            kie_task_id = await services.start_generation_flow(db, user_id, prompt, [], model, cost)
            
        for _ in range(30):
            await asyncio.sleep(2)
            info = await services.check_generation_status(kie_task_id)
            state = info.get("state")
            if state in ["success", "completed"] and info.get("image_url"):
                await bot.send_photo(user_id, info["image_url"], caption="🍌 Готово!")
                await bot.delete_message(user_id, msg_id)
                
                async with AsyncSessionLocal() as db:
                    await services.commit_frozen_credits(db, user_id, cost)
                return
            elif state in ["failed", "error"]:
                err_text = info.get("error", "KIE server processing failed")
                raise Exception(err_text)
                
        raise Exception("Timeout limit reached")
    except Exception as e:
        logger.error(f"Gen error: {e}")
        await bot.edit_message_text(f"❌ Ошибка генерации: {e}", chat_id=user_id, message_id=msg_id)
        # Perform Database Rollback
        async with AsyncSessionLocal() as db:
            await services.refund_frozen_credits(db, user_id, cost)

async def on_startup():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

async def main():
    await on_startup()
    await dp.start_polling(bot)

if __name__ == "__main__":
    if not BOT_TOKEN or BOT_TOKEN == "YOUR_TELEGRAM_BOT_TOKEN_HERE":
        logger.error("Please configure BOT_TOKEN properly in .env.")
    else:
        asyncio.run(main())
