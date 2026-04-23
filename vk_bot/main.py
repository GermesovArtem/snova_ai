import os
import asyncio
import logging
import json
import httpx
import io
from vkbottle.bot import Bot, Message
from vkbottle import Keyboard, KeyboardButtonColor, Text, PhotoMessageUploader, BaseStateGroup
from dotenv import load_dotenv

from backend.database import AsyncSessionLocal
from backend import services, models, s3_service
from bot import messages
from vk_bot import keyboards

load_dotenv()

# Logger setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# VK Config (Ensure these are set on server)
VK_TOKEN = os.getenv("VK_API_TOKEN")
GROUP_ID = os.getenv("VK_GROUP_ID")

if not VK_TOKEN:
    logger.error("VK_API_TOKEN not found in .env")

bot = Bot(token=VK_TOKEN)
uploader = PhotoMessageUploader(bot.api)

# --- STATES ---
class BotState(BaseStateGroup):
    IDLE = 0
    CONFIRM_GEN = 1

# --- UTILS ---
def get_model_costs():
    costs_str = os.getenv("CREDITS_PER_MODEL", '{"nano-banana-2": 1, "nano-banana-pro": 3}')
    try: return json.loads(costs_str)
    except: return {"nano-banana-2": 1, "nano-banana-pro": 3}

def get_credit_packs():
    packs_str = os.getenv("CREDIT_PACKS", '{"149": 30, "299": 65, "990": 270}')
    try: return json.loads(packs_str)
    except: return {"149": 30, "299": 65, "990": 270}

# --- HANDLERS ---

@bot.on.message(text=["начать", "start", "/start"])
async def start_handler(message: Message):
    async with AsyncSessionLocal() as db:
        user, created = await services.get_or_create_user(
            db, platform_id=message.from_id, name=f"VK User {message.from_id}", platform="vk"
        )
        
        if created:
            text = messages.MSG_START_NEW.format(balance=int(user.balance), limit=2)
        else:
            text = messages.MSG_START_REGULAR.format(name="", balance=int(user.balance))
            
        await message.answer(text, keyboard=keyboards.build_reply_kb())
        await bot.state_dispenser.set(message.from_id, BotState.IDLE)

@bot.on.message(text="✨ Создать")
async def cmd_create_handler(message: Message):
    await message.answer(
        "📝 **Пришлите описание (промпт) или фото.**\n\nЯ запомню его и предложу варианты генерации.",
        keyboard=keyboards.build_reply_kb()
    )

@bot.on.message(text="🤖 Модель")
async def model_menu_handler(message: Message):
    async with AsyncSessionLocal() as db:
        user, _ = await services.get_or_create_user(db, message.from_id, platform="vk")
        models_list = services.get_available_models()
        costs = get_model_costs()
        
        text = f"🤖 **Выбор модели**\n\nТекущая: {user.model_preference}\nБаланс: {int(user.balance)} ⚡"
        await message.answer(text, keyboard=keyboards.build_model_menu_kb(models_list, user.model_preference, costs))

@bot.on.message(text="💳 Баланс")
async def balance_handler(message: Message):
    async with AsyncSessionLocal() as db:
        user, _ = await services.get_or_create_user(db, message.from_id, platform="vk")
        packs = get_credit_packs()
        text = messages.MSG_BUY_MENU.format(balance=int(user.balance))
        await message.answer(text, keyboard=keyboards.build_buy_kb(packs))

@bot.on.message(text="📬 Контакты")
async def contacts_handler(message: Message):
    await message.answer(messages.MSG_CONTACTS)

# --- PAYLOAD HANDLERS ---

@bot.on.message(payload_map=[("menu", str)])
async def menu_payload_handler(message: Message):
    await start_handler(message)

@bot.on.message(payload_map=[("set_model", str)])
async def set_model_handler(message: Message):
    model = message.get_payload_json()["set_model"]
    async with AsyncSessionLocal() as db:
        user, _ = await services.get_or_create_user(db, message.from_id, platform="vk")
        user.model_preference = model
        await db.commit()
    
    await message.answer(f"✅ Модель изменена на: {model}", keyboard=keyboards.build_reply_kb())

@bot.on.message(payload_map=[("buy", str)])
async def buy_handler(message: Message):
    payload = message.get_payload_json()
    price = payload["buy"]
    amount = payload["amount"]
    
    async with AsyncSessionLocal() as db:
        description = f"Пополнение {amount} ⚡ (VK:{message.from_id})"
        payment_url = await services.create_yookassa_payment(db, message.from_id, float(price), description)
        
    await message.answer(
        f"⏳ Счёт на {price} руб. ({amount} ⚡) создан!\n\nОплатите по ссылке:\n{payment_url}",
        keyboard=keyboards.build_reply_kb()
    )

# --- GENERATION ROUTER ---

@bot.on.message(state=BotState.IDLE)
@bot.on.message() # Fallback for no state
async def generation_init_handler(message: Message):
    if not message.text and not message.attachments:
         return

    # Skip menu buttons
    if message.text in ["✨ Создать", "🤖 Модель", "💳 Баланс", "📬 Контакты"]:
        return

    # Process photo if exists
    image_urls = []
    for att in message.attachments:
        if att.photo:
            photo = att.photo.sizes[-1]
            async with httpx.AsyncClient() as client:
                resp = await client.get(photo.url)
                if resp.status_code == 200:
                    s3_path = f"vk_uploads/{message.from_id}/{os.urandom(8).hex()}.jpg"
                    s3_url = await s3_service.upload_file_bytes(resp.content, "snova-ai", s3_path)
                    if s3_url:
                        image_urls.append(s3_url)

    prompt = message.text or ""
    if not prompt and not image_urls: return

    async with AsyncSessionLocal() as db:
        user, _ = await services.get_or_create_user(db, message.from_id, platform="vk")
        cost = services.get_model_cost(user.model_preference)

    # Set confirmation state
    await bot.state_dispenser.set(message.from_id, BotState.CONFIRM_GEN, prompt=prompt, images=image_urls, cost=cost)
    
    confirm_text = (
        f"🤖 **Подтвердите генерацию**\n\n"
        f"💬 Запрос: {prompt[:100] + '...' if len(prompt) > 100 else prompt}\n"
        f"🖼 Фото: {'Добавлено' if image_urls else 'Нет'}\n"
        f"💰 Стоимость: {int(cost)} ⚡\n"
        f"🏦 Ваш баланс: {int(user.balance)} ⚡"
    )
    await message.answer(confirm_text, keyboard=keyboards.build_confirm_kb())

@bot.on.message(state=BotState.CONFIRM_GEN)
async def confirmation_handler(message: Message):
    state_data = message.state_peer.payload
    
    # Check if payload action is 'confirm_gen' (button) or any random text
    payload = message.get_payload_json() or {}
    action = payload.get("action")

    if action == "confirm_gen":
        prompt = state_data["prompt"]
        image_urls = state_data["images"]
        cost = state_data["cost"]

        async with AsyncSessionLocal() as db:
            user, _ = await services.get_or_create_user(db, message.from_id, platform="vk")
            if user.balance < cost:
                await message.answer("❌ Недостаточно молний для генерации.", keyboard=keyboards.build_reply_kb())
                await bot.state_dispenser.set(message.from_id, BotState.IDLE)
                return

        await message.answer(f"🚀 Запрос подтвержден! Начинаю генерацию ({user.model_preference})...")
        asyncio.create_task(run_vk_generation(user.id, prompt, image_urls))
        await bot.state_dispenser.set(message.from_id, BotState.IDLE)

    elif action == "edit_gen":
        await message.answer("Хорошо, отправьте новый запрос или нажмите кнопки меню.", keyboard=keyboards.build_reply_kb())
        await bot.state_dispenser.set(message.from_id, BotState.IDLE)
    else:
        await message.answer("Пожалуйста, подтвердите генерацию кнопкой выше или нажмите 'Изменить'.", keyboard=keyboards.build_confirm_kb())

async def run_vk_generation(db_user_id: int, prompt: str, image_urls: list):
    async with AsyncSessionLocal() as db:
        user = await services.get_user_by_id(db, db_user_id)
        if not user: return
        
        vk_platform_id = user.vk_id
        model = user.model_preference
        cost = services.get_model_cost(model)
        
        try:
            # 1. Start Flow
            task_id = await services.start_generation_flow(db, db_user_id, prompt, image_urls, model, cost)
            
            # 2. Poll
            for _ in range(150): # 12.5 minutes max
                await asyncio.sleep(5)
                info = await services.check_generation_status(task_id)
                if info.get("state") in ["success", "completed"]:
                    img_url = info.get("image_url")
                    
                    # Commit credits
                    await services.commit_frozen_credits(db, db_user_id, cost)
                    
                    # Download image for VK upload
                    async with httpx.AsyncClient() as client:
                        img_resp = await client.get(img_url)
                        if img_resp.status_code != 200:
                             raise Exception(f"Failed to download result image from {img_url}")
                        
                        img_data = io.BytesIO(img_resp.content)
                        img_data.name = "result.png"

                    # Send result to VK
                    photo_att = await uploader.upload(img_data, peer_id=vk_platform_id)
                    await bot.api.messages.send(
                        peer_id=vk_platform_id,
                        message=f"✨ Ваша генерация готова!\n\n🤖 Модель: {model}\n⚡ Списано: {int(cost)} молний.",
                        attachment=photo_att,
                        random_id=0,
                        keyboard=keyboards.build_after_gen_kb()
                    )
                    return
                elif info.get("state") in ["failed", "error"]:
                    raise Exception(info.get("error", "KIE Error"))
            
            raise Exception("Timeout (Wait limit exceeded)")
            
        except Exception as e:
            logger.error(f"VK Gen Error: {e}")
            await services.refund_frozen_credits(db, db_user_id, cost)
            await bot.api.messages.send(peer_id=vk_platform_id, message=f"❌ Ошибка генерации: {e}", random_id=0, keyboard=keyboards.build_reply_kb())

if __name__ == "__main__":
    bot.run_forever()
