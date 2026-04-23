import os
import asyncio
import logging
import json
import httpx
import io
import re
import random
from vkbottle.bot import Bot, Message
from vkbottle import Keyboard, KeyboardButtonColor, Text, PhotoMessageUploader, DocMessagesUploader, BaseStateGroup, OpenLink
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
    if not text: return ""
    text = text.replace("**", "").replace("`", "").replace("_", "")
    text = re.sub(r"\[(.*?)\]\(.*?\)", r"\1", text)
    return text

def human_model_name(model_id):
    models_map = services.get_available_models()
    return next((name for name, mid in models_map.items() if mid == model_id), model_id)

async def safe_clear_state(peer_id: int):
    try:
        await bot.state_dispenser.delete(peer_id)
    except:
        pass

async def get_vk_user_name(user_id: int) -> str:
    try:
        users = await bot.api.users.get(user_ids=[user_id])
        if users:
            return users[0].first_name
    except:
        pass
    return ""

def get_limit_for_model(model_name: str) -> int:
    if "1k" in model_name.lower(): return 1
    return 14

async def safe_vk_send(peer_id: int, message: str, attachment: str = None, keyboard: str = None):
    """Extremely robust message sender for VK."""
    params = {
        "peer_id": str(peer_id),
        "message": message,
        "random_id": random.randint(1, 2**31),
    }
    if attachment: params["attachment"] = attachment
    if keyboard: params["keyboard"] = keyboard
    
    logger.info(f"SAFE_SEND: peer={peer_id}, att_len={len(attachment or '')}, has_kb={bool(keyboard)}")
    try:
        # Use low-level request to bypass model serialization issues
        await bot.api.request("messages.send", params)
    except Exception as e:
        logger.error(f"SAFE_SEND_ERROR: {e} | Params: {params}")
        raise e

# --- HANDLERS ---

@bot.on.message(text=["начать", "Начать", "НАЧАТЬ", "start", "Start", "START", "/start"])
async def start_handler(message: Message):
    await safe_clear_state(message.from_id)
    async with AsyncSessionLocal() as db:
        real_name = await get_vk_user_name(message.from_id)
        user, created = await services.get_or_create_user(
            db, platform_id=message.from_id, name=real_name or f"VK_{message.from_id}", platform="vk"
        )
        if not created and real_name and (not user.name or "VK_" in user.name):
             user.name = real_name
             await db.commit()
        limit = get_limit_for_model(user.model_preference)
        text = messages.MSG_START_NEW.format(balance=int(user.balance), limit=limit) if created else messages.MSG_START_REGULAR.format(name=user.name or "", balance=int(user.balance))
    await safe_vk_send(message.from_id, clean_markdown(text), keyboard=keyboards.build_reply_kb())

@bot.on.message(payload_map=[("cmd", str)])
async def menu_cmd_handler(message: Message):
    await safe_clear_state(message.from_id)
    cmd = message.get_payload_json()["cmd"]
    if cmd == "create": await cmd_create_handler(message)
    elif cmd == "model": await model_menu_handler(message)
    elif cmd == "balance": await balance_handler(message)
    elif cmd == "contacts": await contacts_handler(message)
    elif cmd == "main": await start_handler(message)

@bot.on.message(text=["✨ создать", "✨ Создать", "Создать", "создать"])
async def cmd_create_handler(message: Message):
    await safe_clear_state(message.from_id)
    async with AsyncSessionLocal() as db:
        user, _ = await services.get_or_create_user(db, message.from_id, platform="vk")
        limit = get_limit_for_model(user.model_preference)
    await safe_vk_send(message.from_id, clean_markdown(messages.MSG_GEN_PROMPT.format(limit=limit)), keyboard=keyboards.build_reply_kb())

@bot.on.message(text=["🤖 модель", "🤖 Модель", "Модель", "модель"])
async def model_menu_handler(message: Message):
    await safe_clear_state(message.from_id)
    async with AsyncSessionLocal() as db:
        user, _ = await services.get_or_create_user(db, message.from_id, platform="vk")
        costs_str = os.getenv("CREDITS_PER_MODEL", '{"nano-banana-2-1k": 1, "nano-banana-2-4k": 2}')
        text = messages.MSG_MODEL_MENU.format(human_name=human_model_name(user.model_preference), limit=get_limit_for_model(user.model_preference), balance=int(user.balance))
    await safe_vk_send(message.from_id, clean_markdown(text), keyboard=keyboards.build_model_menu_kb(services.get_available_models(), user.model_preference, json.loads(costs_str)))

@bot.on.message(payload_map=[("set_model", str)])
async def set_model_handler(message: Message):
    await safe_clear_state(message.from_id)
    new_model = message.get_payload_json()["set_model"]
    async with AsyncSessionLocal() as db:
        user, _ = await services.get_or_create_user(db, message.from_id, platform="vk")
        user.model_preference = new_model
        await db.commit()
    await message.answer(f"✅ Модель успешно изменена на: {human_model_name(new_model)}")
    await cmd_create_handler(message)

@bot.on.message(text=["💳 баланс", "💳 Баланс", "Баланс", "баланс"])
async def balance_handler(message: Message):
    await safe_clear_state(message.from_id)
    async with AsyncSessionLocal() as db:
        user, _ = await services.get_or_create_user(db, message.from_id, platform="vk")
        packs_str = os.getenv("CREDIT_PACKS", '{"149": 30, "299": 65, "990": 270}')
        text = messages.MSG_BUY_MENU.format(balance=int(user.balance))
    await safe_vk_send(message.from_id, clean_markdown(text), keyboard=keyboards.build_buy_kb(json.loads(packs_str)))

@bot.on.message(text=["📬 контакты", "📬 Контакты", "Контакты", "контакты"])
async def contacts_handler(message: Message):
    await safe_clear_state(message.from_id)
    vk_contacts = "🆘 Техподдержка: @artemgavr\n👤 Менеджер: @doloreees_s\n\nПишите нам по любым вопросам!"
    await safe_vk_send(message.from_id, clean_markdown(vk_contacts))

@bot.on.message(payload_map=[("buy", str)])
async def buy_handler(message: Message):
    payload = message.get_payload_json()
    async with AsyncSessionLocal() as db:
        user, _ = await services.get_or_create_user(db, message.from_id, platform="vk")
        payment_url = await services.create_yookassa_payment(db, user.id, float(payload["buy"]), f"Buy {payload['amount']} credits (VK:{message.from_id})")
    await safe_vk_send(message.from_id, f"⏳ Счёт на {payload['buy']} руб. создан! Нажмите кнопку ниже для оплаты:", keyboard=keyboards.build_pay_link_kb(payment_url))

@bot.on.message(state=BotState.CONFIRM_GEN)
async def confirmation_handler(message: Message):
    payload = message.get_payload_json() or {}
    action = payload.get("action")
    if action == "confirm_gen":
        state_data = message.state_peer.payload
        async with AsyncSessionLocal() as db:
             user, _ = await services.get_or_create_user(db, message.from_id, platform="vk")
             cost = state_data["cost"]
             if user.balance < cost:
                  await safe_vk_send(message.from_id, clean_markdown(messages.MSG_ERR_FUNDS.format(cost=int(cost), balance=int(user.balance))))
                  await bot.state_dispenser.delete(message.from_id)
                  return
        await safe_vk_send(message.from_id, clean_markdown(messages.MSG_GEN_STARTING.format(model_name=human_model_name(user.model_preference))))
        asyncio.create_task(run_vk_generation(message.from_id, state_data["prompt"], state_data["images"]))
        await bot.state_dispenser.delete(message.from_id)
    elif action == "edit_gen" or message.text == "❌ Отмена":
        await safe_vk_send(message.from_id, clean_markdown(messages.MSG_EDIT_GEN), keyboard=keyboards.build_reply_kb())
        await bot.state_dispenser.delete(message.from_id)
    else:
        cmd = (message.text or "").strip().lower()
        if any(x in cmd for x in ["создать", "модель", "баланс", "контакты", "начать", "start"]):
             await safe_clear_state(message.from_id)
             if "начать" in cmd or "start" in cmd: await start_handler(message)
             return
        await safe_vk_send(message.from_id, "Пожалуйста, используйте кнопки для подтверждения или отмены.", keyboard=keyboards.build_confirm_kb())

@bot.on.message()
async def generic_handler(message: Message):
    if not message.text and not message.attachments: return
    cmd = (message.text or "").strip().lower()
    if any(x in cmd for x in ["создать", "модель", "баланс", "контакты", "начать", "start", "/start", "назад"]) or message.payload: return
    
    image_processed_msg = None
    if message.attachments:
         image_processed_msg = await message.answer("📸 Обрабатываю ваши изображения...")

    image_urls = []
    vk_attachment_strs = []
    for att in message.attachments:
        url, vk_id = None, ""
        if att.photo: 
             url = att.photo.sizes[-1].url
             vk_id = f"photo{att.photo.owner_id}_{att.photo.id}"
        elif att.doc and att.doc.type == 1: 
             url = att.doc.url
             vk_id = f"doc{att.doc.owner_id}_{att.doc.id}"
            
        if url:
            vk_attachment_strs.append(vk_id)
            async with httpx.AsyncClient() as client:
                try:
                    resp = await client.get(url, timeout=30.0)
                    if resp.status_code == 200:
                        s3_url = await s3_service.upload_file_bytes(resp.content, "snova-ai", f"vk/{message.from_id}/{os.urandom(8).hex()}.jpg")
                        if s3_url: image_urls.append(s3_url)
                except Exception as e: logger.error(f"S3 Upload fail: {e}")

    prompt = (message.text or "").strip()
    if not prompt and not image_urls: return

    async with AsyncSessionLocal() as db:
        user, _ = await services.get_or_create_user(db, message.from_id, platform="vk")
        limit = get_limit_for_model(user.model_preference)
        if len(image_urls) > limit: 
             image_urls = image_urls[:limit]
             vk_attachment_strs = vk_attachment_strs[:limit]
        cost = services.get_model_cost(user.model_preference)

    await bot.state_dispenser.set(message.from_id, BotState.CONFIRM_GEN, prompt=prompt, images=image_urls, cost=cost)
    
    confirm_text = messages.MSG_CONFIRMATION.format(
        header=messages.MSG_CONFIRM_HEADER_NEW if not image_urls else messages.MSG_CONFIRM_HEADER_EDIT,
        safe_prompt=prompt[:100] or "(без текста)",
        img_count_text=f"Фото: {len(image_urls)} шт.\n" if image_urls else "",
        human_name=human_model_name(user.model_preference),
        ratio="auto", fmt="png", cost=int(cost), balance=int(user.balance)
    )
    
    await safe_vk_send(message.from_id, clean_markdown(confirm_text), attachment=",".join(vk_attachment_strs), keyboard=keyboards.build_confirm_kb())

async def run_vk_generation(vk_p_id: int, prompt: str, image_urls: list):
    async with AsyncSessionLocal() as db:
        from sqlalchemy import select
        res = await db.execute(select(models.User).filter_by(vk_id=vk_p_id))
        user = res.scalars().first()
        if not user: return
        user_id, model, cost = user.id, user.model_preference, services.get_model_cost(user.model_preference)
        generation_committed = False
        try:
            task_id = await services.start_generation_flow(db, user_id, prompt, image_urls, model, cost)
            for i in range(150):
                await asyncio.sleep(5)
                info = await services.check_generation_status(task_id)
                if info.get("state") in ["success", "completed"]:
                    img_url = info.get("image_url")
                    await services.commit_frozen_credits(db, user_id, cost)
                    generation_committed = True
                    async with httpx.AsyncClient() as client:
                        r = await client.get(img_url, timeout=60.0)
                        if r.status_code == 200:
                            img_data = io.BytesIO(r.content)
                            img_data.name = "result.png"
                            photo_att = await uploader.upload(img_data, peer_id=int(vk_p_id))
                            img_data.seek(0)
                            doc_att = await doc_uploader.upload("result.png", img_data, peer_id=int(vk_p_id))
                            user = await services.get_user_by_id(db, user_id)
                            text = messages.MSG_GEN_SUCCESS_WITH_BALANCE.format(balance=int(user.balance), model_name=human_model_name(model))
                            
                            atts = []
                            if photo_att: atts.append(str(photo_att))
                            if doc_att: atts.append(str(doc_att))
                            
                            await safe_vk_send(vk_p_id, clean_markdown(text), attachment=",".join(atts), keyboard=keyboards.build_after_gen_kb())
                            return
                elif info.get("state") in ["failed", "error"]:
                    raise Exception(info.get("error", "KIE Error"))
            raise Exception("Timeout")
        except Exception as e:
            logger.error(f"GEN ERROR: {e}")
            if not generation_committed:
                try: await services.refund_frozen_credits(db, user_id, cost)
                except: pass
            await safe_vk_send(vk_p_id, f"❌ Ошибка: {str(e)}", keyboard=keyboards.build_reply_kb())

if __name__ == "__main__":
    bot.run_forever()
