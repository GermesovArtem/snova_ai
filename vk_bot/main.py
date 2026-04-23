import os
import asyncio
import logging
import json
import httpx
import io
import re
from vkbottle.bot import Bot, Message
from vkbottle import Keyboard, KeyboardButtonColor, Text, PhotoMessageUploader, DocMessagesUploader, BaseStateGroup
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
    """Removes **bold**, `code`, and other Markdown formatting for VK compatibility."""
    if not text: return ""
    text = text.replace("**", "")
    text = text.replace("`", "")
    text = text.replace("_", "")
    text = re.sub(r"\[(.*?)\]\(.*?\)", r"\1", text)
    return text

def get_model_costs():
    costs_str = os.getenv("CREDITS_PER_MODEL", '{"nano-banana-2-1k": 1, "nano-banana-2-4k": 2, "nano-banana-pro-2k": 2, "nano-banana-pro-4k": 3}')
    try: return json.loads(costs_str)
    except: return {"nano-banana-2-1k": 1, "nano-banana-2-4k": 2, "nano-banana-pro-2k": 2, "nano-banana-pro-4k": 3}

def get_credit_packs():
    packs_str = os.getenv("CREDIT_PACKS", '{"149": 30, "299": 65, "990": 270}')
    try: return json.loads(packs_str)
    except: return {"149": 30, "299": 65, "990": 270}

def human_model_name(model_id):
    models_map = services.get_available_models()
    return next((name for name, mid in models_map.items() if mid == model_id), model_id)

# --- HANDLERS (ORDER MATTERS) ---

@bot.on.message(text=["начать", "start", "/start"])
async def start_handler(message: Message):
    async with AsyncSessionLocal() as db:
        user, created = await services.get_or_create_user(
            db, platform_id=message.from_id, name=f"VK_{message.from_id}", platform="vk"
        )
        
        if created:
            text = messages.MSG_START_NEW.format(balance=int(user.balance), limit=2)
        else:
            text = messages.MSG_START_REGULAR.format(name="", balance=int(user.balance))
            
        # Forces the keyboard to appear using direct API call
        await bot.api.messages.send(
            peer_id=message.from_id,
            message=clean_markdown(text),
            keyboard=keyboards.build_reply_kb(),
            random_id=0
        )
        await bot.state_dispenser.set(message.from_id, BotState.IDLE)

@bot.on.message(payload_map=[("cmd", str)])
async def menu_cmd_handler(message: Message):
    cmd = message.get_payload_json()["cmd"]
    if cmd == "create": await cmd_create_handler(message)
    elif cmd == "model": await model_menu_handler(message)
    elif cmd == "balance": await balance_handler(message)
    elif cmd == "contacts": await contacts_handler(message)
    elif cmd == "main": await start_handler(message)

@bot.on.message(text="✨ Создать")
async def cmd_create_handler(message: Message):
    await message.answer(
        clean_markdown(messages.MSG_GEN_PROMPT.format(limit=2)),
        keyboard=keyboards.build_reply_kb()
    )

@bot.on.message(text="🤖 Модель")
async def model_menu_handler(message: Message):
    async with AsyncSessionLocal() as db:
        user, _ = await services.get_or_create_user(db, message.from_id, platform="vk")
        models_list = services.get_available_models()
        costs = get_model_costs()
        
        text = messages.MSG_MODEL_MENU.format(
            human_name=human_model_name(user.model_preference),
            limit=1 if "1k" in user.model_preference.lower() else 2,
            balance=int(user.balance)
        )
        await message.answer(clean_markdown(text), keyboard=keyboards.build_model_menu_kb(models_list, user.model_preference, costs))

@bot.on.message(text="💳 Баланс")
async def balance_handler(message: Message):
    async with AsyncSessionLocal() as db:
        user, _ = await services.get_or_create_user(db, message.from_id, platform="vk")
        packs = get_credit_packs()
        text = messages.MSG_BUY_MENU.format(balance=int(user.balance))
        await message.answer(clean_markdown(text), keyboard=keyboards.build_buy_kb(packs))

@bot.on.message(text="📬 Контакты")
async def contacts_handler(message: Message):
    await message.answer(clean_markdown(messages.MSG_CONTACTS))

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
    
    await message.answer(clean_markdown(messages.MSG_MODEL_SET_SUCCESS), keyboard=keyboards.build_reply_kb())
    await message.answer(clean_markdown(messages.MSG_MODEL_SET_NEXT.format(limit=2)))

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

@bot.on.message(payload_map=[("action", "repeat_gen")])
async def repeat_gen_handler(message: Message):
    async with AsyncSessionLocal() as db:
        user, _ = await services.get_or_create_user(db, message.from_id, platform="vk")
        from sqlalchemy import select
        res = await db.execute(
            select(models.GenerationTask)
            .filter_by(user_id=user.id)
            .order_by(models.GenerationTask.created_at.desc())
            .limit(1)
        )
        last_task = res.scalars().first()
        
        if not last_task:
            await message.answer(clean_markdown(messages.MSG_GEN_SIMILAR_NO_DATA))
            return
            
        cost = services.get_model_cost(last_task.model)
        if user.balance < cost:
             await message.answer(clean_markdown(messages.MSG_ERR_FUNDS.format(cost=int(cost), balance=int(user.balance))))
             return

        await message.answer(clean_markdown(messages.MSG_GEN_SIMILAR_START))
        image_urls = json.loads(last_task.prompt_images_json) if last_task.prompt_images_json else []
        asyncio.create_task(run_vk_generation(user.id, last_task.prompt, image_urls))

# --- GENERATION ROUTER ---

@bot.on.message(state=BotState.CONFIRM_GEN)
async def confirmation_handler(message: Message):
    state_data = message.state_peer.payload
    payload = message.get_payload_json() or {}
    action = payload.get("action")

    if action == "confirm_gen":
        prompt, image_urls, cost = state_data["prompt"], state_data["images"], state_data["cost"]
        async with AsyncSessionLocal() as db:
            user, _ = await services.get_or_create_user(db, message.from_id, platform="vk")
            if user.balance < cost:
                await message.answer(clean_markdown(messages.MSG_ERR_FUNDS.format(cost=int(cost), balance=int(user.balance))), keyboard=keyboards.build_reply_kb())
                await bot.state_dispenser.set(message.from_id, BotState.IDLE)
                return

        await message.answer(clean_markdown(messages.MSG_GEN_STARTING.format(model_name=human_model_name(user.model_preference))))
        asyncio.create_task(run_vk_generation(user.id, prompt, image_urls))
        await bot.state_dispenser.set(message.from_id, BotState.IDLE)
    elif action == "edit_gen" or message.text == "❌ Отмена":
        await message.answer(clean_markdown(messages.MSG_EDIT_GEN), keyboard=keyboards.build_reply_kb())
        await bot.state_dispenser.set(message.from_id, BotState.IDLE)
    else:
        await message.answer("Пожалуйста, подтвердите генерацию кнопкой или нажмите Отмена.", keyboard=keyboards.build_confirm_kb())

@bot.on.message() # Fallback for EVERYTHING else (Prompts)
async def generation_init_handler(message: Message):
    if not message.text and not message.attachments: return
    # Filter menu names and system commands to prevent them from being treated as prompts
    cmd = (message.text or "").lower().strip()
    if cmd in ["✨ создать", "🤖 модель", "💳 баланс", "📬 контакты", "начать", "start", "/start", "назад"]: 
        return

    # Process photo
    image_urls = []
    for att in message.attachments:
        if att.photo:
            photo = att.photo.sizes[-1]
            async with httpx.AsyncClient() as client:
                resp = await client.get(photo.url)
                if resp.status_code == 200:
                    s3_path = f"vk_uploads/{message.from_id}/{os.urandom(8).hex()}.jpg"
                    s3_url = await s3_service.upload_file_bytes(resp.content, "snova-ai", s3_path)
                    if s3_url: image_urls.append(s3_url)

    prompt = message.text or ""
    if not prompt and not image_urls: return

    async with AsyncSessionLocal() as db:
        user, _ = await services.get_or_create_user(db, message.from_id, platform="vk")
        cost = services.get_model_cost(user.model_preference)

    await bot.state_dispenser.set(message.from_id, BotState.CONFIRM_GEN, prompt=prompt, images=image_urls, cost=cost)
    
    confirm_text = messages.MSG_CONFIRMATION.format(
        header=messages.MSG_CONFIRM_HEADER_NEW,
        safe_prompt=prompt[:100],
        img_count_text=f"Фото: {len(image_urls)} шт.\n" if image_urls else "",
        human_name=human_model_name(user.model_preference),
        ratio="auto", fmt="png",
        cost=int(cost),
        balance=int(user.balance)
    )
    await message.answer(clean_markdown(confirm_text), keyboard=keyboards.build_confirm_kb())

async def run_vk_generation(db_user_id: int, prompt: str, image_urls: list):
    async with AsyncSessionLocal() as db:
        user = await services.get_user_by_id(db, db_user_id)
        if not user: return
        vk_p_id, model, cost = user.vk_id, user.model_preference, services.get_model_cost(user.model_preference)
        
        try:
            task_id = await services.start_generation_flow(db, db_user_id, prompt, image_urls, model, cost)
            for _ in range(160):
                await asyncio.sleep(5)
                info = await services.check_generation_status(task_id)
                if info.get("state") in ["success", "completed"]:
                    img_url = info.get("image_url")
                    await services.commit_frozen_credits(db, db_user_id, cost)
                    async with httpx.AsyncClient() as client:
                        r = await client.get(img_url)
                        if r.status_code == 200:
                            img_data = io.BytesIO(r.content)
                            img_data.name = f"result_{task_id[:6]}.png"
                            photo_att = await uploader.upload(img_data, peer_id=vk_p_id)
                            img_data.seek(0)
                            doc_att = await doc_uploader.upload(f"result_{task_id[:6]}.png", img_data, peer_id=vk_p_id)
                            user = await services.get_user_by_id(db, db_user_id)
                            text = messages.MSG_GEN_SUCCESS_WITH_BALANCE.format(balance=int(user.balance), model_name=human_model_name(model))
                            await bot.api.messages.send(
                                peer_id=vk_p_id, message=clean_markdown(text),
                                attachment=[photo_att, doc_att],
                                random_id=0, keyboard=keyboards.build_after_gen_kb()
                            )
                            return
                elif info.get("state") in ["failed", "error"]:
                    raise Exception(info.get("error", "KIE error"))
            raise Exception("Timeout exceeded")
        except Exception as e:
            logger.error(f"VK Gen Error: {e}")
            await services.refund_frozen_credits(db, db_user_id, cost)
            await bot.api.messages.send(peer_id=vk_p_id, message=clean_markdown(messages.MSG_ERR_GEN_FAILED.format(err_text=str(e))), random_id=0, keyboard=keyboards.build_reply_kb())

if __name__ == "__main__":
    bot.run_forever()
