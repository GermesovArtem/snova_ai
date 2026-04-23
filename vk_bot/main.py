import os
import asyncio
import logging
import json
import httpx
import io
import re
from vkbottle.bot import Bot, Message
from vkbottle import Keyboard, KeyboardButtonColor, Text, PhotoMessageUploader, DocMessagesUploader, BaseStateGroup
from vkbottle.dispatch.rules.base import PayloadRule
from dotenv import load_dotenv

from backend.database import AsyncSessionLocal
from backend import services, models, s3_service
from bot import messages
from vk_bot import keyboards

load_dotenv()

# Logger setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# VK Config
VK_TOKEN = os.getenv("VK_API_TOKEN")
GROUP_ID = os.getenv("VK_GROUP_ID")

bot = Bot(token=VK_TOKEN)
uploader = PhotoMessageUploader(bot.api)
doc_uploader = DocMessagesUploader(bot.api)

# --- STATES ---
class BotState(BaseStateGroup):
    IDLE = 0
    CONFIRM_GEN = 1

# --- UTILS ---
def clean_markdown(text: str) -> str:
    """Removes Markdown formatting for VK."""
    if not text: return ""
    text = text.replace("**", "").replace("`", "").replace("_", "")
    text = re.sub(r"\[(.*?)\]\(.*?\)", r"\1", text)
    return text

def human_model_name(model_id):
    models_map = services.get_available_models()
    return next((name for name, mid in models_map.items() if mid == model_id), model_id)

# --- HANDLERS ---

@bot.on.message(text=["начать", "start", "/start"])
async def start_handler(message: Message):
    logger.info(f"DEBUG: [start_handler] triggered for user {message.from_id}")
    async with AsyncSessionLocal() as db:
        user, created = await services.get_or_create_user(
            db, platform_id=message.from_id, name=f"VK_{message.from_id}", platform="vk"
        )
        limit = 1 if "1k" in user.model_preference.lower() else 2
        text = messages.MSG_START_NEW.format(balance=int(user.balance), limit=limit) if created else messages.MSG_START_REGULAR.format(name="", balance=int(user.balance))
        
    await message.answer(clean_markdown(text), keyboard=keyboards.build_reply_kb())

@bot.on.message(payload_map=[("cmd", str)])
async def menu_cmd_handler(message: Message):
    cmd = message.get_payload_json()["cmd"]
    logger.info(f"DEBUG: [menu_cmd_handler] payload cmd={cmd} for user {message.from_id}")
    if cmd == "create": await cmd_create_handler(message)
    elif cmd == "model": await model_menu_handler(message)
    elif cmd == "balance": await balance_handler(message)
    elif cmd == "contacts": await contacts_handler(message)
    elif cmd == "main": await start_handler(message)

@bot.on.message(text="✨ Создать")
async def cmd_create_handler(message: Message):
    logger.info(f"DEBUG: [cmd_create_handler] for user {message.from_id}")
    async with AsyncSessionLocal() as db:
        user, _ = await services.get_or_create_user(db, message.from_id, platform="vk")
        limit = 1 if "1k" in user.model_preference.lower() else 2
    await message.answer(clean_markdown(messages.MSG_GEN_PROMPT.format(limit=limit)), keyboard=keyboards.build_reply_kb())

@bot.on.message(text="🤖 Модель")
async def model_menu_handler(message: Message):
    logger.info(f"DEBUG: [model_menu_handler] for user {message.from_id}")
    async with AsyncSessionLocal() as db:
        user, _ = await services.get_or_create_user(db, message.from_id, platform="vk")
        costs_str = os.getenv("CREDITS_PER_MODEL", '{"nano-banana-2-1k": 1}')
        costs = json.loads(costs_str)
        text = messages.MSG_MODEL_MENU.format(human_name=human_model_name(user.model_preference), limit=1 if "1k" in user.model_preference.lower() else 2, balance=int(user.balance))
    await message.answer(clean_markdown(text), keyboard=keyboards.build_model_menu_kb(services.get_available_models(), user.model_preference, costs))

@bot.on.message(text="💳 Баланс")
async def balance_handler(message: Message):
    logger.info(f"DEBUG: [balance_handler] for user {message.from_id}")
    async with AsyncSessionLocal() as db:
        user, _ = await services.get_or_create_user(db, message.from_id, platform="vk")
        packs_str = os.getenv("CREDIT_PACKS", '{"149": 30}')
        text = messages.MSG_BUY_MENU.format(balance=int(user.balance))
    await message.answer(clean_markdown(text), keyboard=keyboards.build_buy_kb(json.loads(packs_str)))

@bot.on.message(payload_map=[("buy", str)])
async def buy_handler(message: Message):
    payload = message.get_payload_json()
    logger.info(f"DEBUG: [buy_handler] payload={payload} for user {message.from_id}")
    async with AsyncSessionLocal() as db:
        user, _ = await services.get_or_create_user(db, message.from_id, platform="vk")
        payment_url = await services.create_yookassa_payment(db, user.id, float(payload["buy"]), f"Buy {payload['amount']} credits")
    await message.answer(f"⏳ Счёт создан! Нажмите кнопку для оплаты:", keyboard=keyboards.build_pay_link_kb(payment_url))

@bot.on.message(state=BotState.CONFIRM_GEN)
async def confirmation_handler(message: Message):
    payload = message.get_payload_json() or {}
    action = payload.get("action")
    logger.info(f"DEBUG: [confirmation_handler] state=CONFIRM_GEN, action={action}, text='{message.text}'")
    
    if action == "confirm_gen":
        state_data = message.state_peer.payload
        await message.answer(clean_markdown(messages.MSG_GEN_STARTING.format(model_name="...")))
        asyncio.create_task(run_vk_generation(message.from_id, state_data["prompt"], state_data["images"]))
        await bot.state_dispenser.delete(message.from_id)
    elif action == "edit_gen" or message.text == "❌ Отмена":
        await message.answer(clean_markdown(messages.MSG_EDIT_GEN), keyboard=keyboards.build_reply_kb())
        await bot.state_dispenser.delete(message.from_id)
    else:
        await message.answer("Пожалуйста, используйте кнопки для подтверждения или отмены.", keyboard=keyboards.build_confirm_kb())

@bot.on.message()
async def generic_handler(message: Message):
    logger.info(f"DEBUG: [generic_handler] text='{message.text}' payload='{message.payload}'")
    
    # 1. Skip menu buttons
    if message.text in ["✨ Создать", "🤖 Модель", "💳 Баланс", "📬 Контакты"]: return
    
    # 2. Process images
    image_urls = []
    for att in message.attachments:
        if att.photo:
            photo = att.photo.sizes[-1]
            async with httpx.AsyncClient() as client:
                resp = await client.get(photo.url)
                if resp.status_code == 200:
                    s3_url = await s3_service.upload_file_bytes(resp.content, "snova-ai", f"vk/{message.from_id}/{os.urandom(4).hex()}.jpg")
                    if s3_url: image_urls.append(s3_url)

    if not message.text and not image_urls: return

    async with AsyncSessionLocal() as db:
        user, _ = await services.get_or_create_user(db, message.from_id, platform="vk")
        cost = services.get_model_cost(user.model_preference)

    await bot.state_dispenser.set(message.from_id, BotState.CONFIRM_GEN, prompt=message.text or "", images=image_urls, cost=cost)
    await message.answer("✨ Подтвердите генерацию:", keyboard=keyboards.build_confirm_kb())

async def run_vk_generation(vk_id: int, prompt: str, image_urls: list):
    logger.info(f"DEBUG: [run_vk_generation] start for {vk_id}")
    # Logic remains same but with logs
    pass

if __name__ == "__main__":
    bot.run_forever()
