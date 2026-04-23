import os
import asyncio
import logging
import json
import httpx
import io
import re
import random
from vkbottle.bot import Bot, Message
from vkbottle import Keyboard, KeyboardButtonColor, Text, PhotoMessageUploader, DocMessagesUploader, BaseStateGroup, OpenLink, BaseMiddleware
from dotenv import load_dotenv

from backend.database import AsyncSessionLocal
from backend import services, models, s3_service
from bot import messages
from vk_bot import keyboards

load_dotenv()

# Strict logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("VK_BOT")

# VK Config
VK_TOKEN = os.getenv("VK_API_TOKEN")
GROUP_ID = os.getenv("VK_GROUP_ID")

bot = Bot(token=VK_TOKEN)

# --- STATES ---
class BotState(BaseStateGroup):
    IDLE = 0
    CONFIRM_GEN = 1
    WAIT_PROMPT = 2
    POST_GEN = 3

# --- MEGA DIAGNOSTIC MIDDLEWARE ---
class DiagnosticMiddleware(BaseMiddleware[Message]):
    async def pre(self):
        try:
             text = self.event.text or ""
             payload = self.event.payload or ""
             logger.warning(f"--- EVENT --- From: {self.event.from_id} | Text: '{text}' | Payload: '{payload}'")
             
             cmd = text.strip().lower()
             payload_data = self.event.get_payload_json() or {}
             if cmd in ["начать", "старт", "/start"] or payload_data.get("command") == "start":
                  logger.warning(f"ACTION: START RECEIVED. CLEARED STATE FOR {self.event.from_id}")
                  await bot.state_dispenser.delete(self.event.from_id)
        except Exception as e:
             logger.error(f"MIDDLEWARE ERROR: {e}")
        return True

bot.labeler.message_view.register_middleware(DiagnosticMiddleware)

# --- ROBUST STARTUP CHECK ---
async def startup_check():
    async with httpx.AsyncClient() as client:
        try:
            logger.warning(">>> STARTING IDENTITY VERIFICATION...")
            resp = await client.post("https://api.vk.com/method/groups.getById", data={
                "access_token": VK_TOKEN,
                "v": "5.199"
            })
            data = resp.json()
            if "response" in data and len(data["response"]) > 0:
                group = data["response"][0]
                logger.warning(f"SUCCESS! Bot is listening to: {group['name']} (ID: {group['id']})")
                logger.warning(f"Group Screen Name: {group.get('screen_name')}")
            else:
                logger.warning(f"CRITICAL: Failed to get group info. API Answer: {data}")
        except Exception as e:
            logger.error(f"IDENTITY CHECK FAILED: {e}")

# [Utils and Handlers remain same...]

def clean_markdown(text: str) -> str:
    if not text: return ""
    text = text.replace("**", "").replace("`", "").replace("_", "")
    text = re.sub(r"\[(.*?)\]\(.*?\)", r"\1", text)
    return text

def human_model_name(model_id):
    models_map = services.get_available_models()
    return next((name for name, mid in models_map.items() if mid == model_id), model_id)

async def get_vk_user_name(user_id: int) -> str:
    try:
        users = await bot.api.users.get(user_ids=[user_id])
        if users: return users[0].first_name
    except: pass
    return ""

def get_limit_for_model(model_name: str) -> int:
    mn = model_name.lower()
    if "pro" in mn: return 8
    return 14

async def vk_upload_photo(image_bytes: bytes, peer_id: int) -> str:
    async with httpx.AsyncClient() as client:
        resp = await client.post("https://api.vk.com/method/photos.getMessagesUploadServer", data={"peer_id": str(peer_id), "access_token": VK_TOKEN, "v": "5.199"})
        data = resp.json()
        if "error" in data: raise Exception(f"UploadServer Error: {data['error']['error_msg']}")
        upload_url = data["response"]["upload_url"]
        files = {"photo": ("photo.jpg", image_bytes, "image/jpeg")}
        resp = await client.post(upload_url, files=files)
        upload_data = resp.json()
        resp = await client.post("https://api.vk.com/method/photos.saveMessagesPhoto", data={"photo": upload_data["photo"], "server": upload_data["server"], "hash": upload_data["hash"], "access_token": VK_TOKEN, "v": "5.199"})
        photo_resp = resp.json()
        if "error" in photo_resp: raise Exception(f"SavePhoto Error: {photo_resp['error']['error_msg']}")
        photo = photo_resp["response"][0]
        return f"photo{photo['owner_id']}_{photo['id']}"

async def safe_vk_send(peer_id: int, message: str, attachment: str = None, keyboard: str = None):
    url = "https://api.vk.com/method/messages.send"
    params = {"peer_id": str(peer_id), "message": message, "random_id": str(random.randint(1, 2**31)), "access_token": VK_TOKEN, "v": "5.199"}
    if attachment: params["attachment"] = attachment
    if keyboard: params["keyboard"] = keyboard
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(url, data=params)
            res_json = resp.json()
            if "error" in res_json: logger.error(f"VK API ERROR: {res_json['error']}")
        except Exception as e: logger.error(f"VK EXCEPTION: {e}")

@bot.on.message(func=lambda msg: (msg.text or "").strip().lower() in ["начать", "начни", "старт", "/start"] or (msg.get_payload_json() or {}).get("command") == "start")
async def start_handler(message: Message):
    logger.warning(f"START HANDLER TRIGGERED for {message.from_id}")
    async with AsyncSessionLocal() as db:
        real_name = await get_vk_user_name(message.from_id)
        user, created = await services.get_or_create_user(db, platform_id=message.from_id, name=real_name or f"VK_{message.from_id}", platform="vk")
        if not created and real_name and (not user.name or "VK_" in user.name):
             user.name = real_name
             await db.commit()
        limit = get_limit_for_model(user.model_preference)
        text = messages.MSG_START_NEW.format(balance=int(user.balance), limit=limit) if created else messages.MSG_START_REGULAR.format(name=user.name or "", balance=int(user.balance))
    await safe_vk_send(message.from_id, clean_markdown(text), keyboard=keyboards.build_reply_kb())

@bot.on.message(payload_map=[("cmd", str)])
async def menu_cmd_handler(message: Message):
    cmd = message.get_payload_json()["cmd"]
    if cmd == "create": await cmd_create_handler(message)
    elif cmd == "model": await model_menu_handler(message)
    elif cmd == "balance": await balance_handler(message)
    elif cmd == "contacts": await contacts_handler(message)
    elif cmd == "main": await start_handler(message)

@bot.on.message(text=["✨ создать", "✨ Создать", "Создать", "создать"])
async def cmd_create_handler(message: Message):
    async with AsyncSessionLocal() as db:
        user, _ = await services.get_or_create_user(db, message.from_id, platform="vk")
        limit = get_limit_for_model(user.model_preference)
    await safe_vk_send(message.from_id, clean_markdown(messages.MSG_GEN_PROMPT.format(limit=limit)), keyboard=keyboards.build_reply_kb())

@bot.on.message(text=["🤖 модель", "🤖 Модель", "Модель", "модель"])
async def model_menu_handler(message: Message):
    async with AsyncSessionLocal() as db:
        user, _ = await services.get_or_create_user(db, message.from_id, platform="vk")
        costs_str = os.getenv("CREDITS_PER_MODEL", '{"nano-banana-2-1k": 1, "nano-banana-2-4k": 2}')
        text = messages.MSG_MODEL_MENU.format(human_name=human_model_name(user.model_preference), limit=get_limit_for_model(user.model_preference), balance=int(user.balance))
    await safe_vk_send(message.from_id, clean_markdown(text), keyboard=keyboards.build_model_menu_kb(services.get_available_models(), user.model_preference, json.loads(costs_str)))

@bot.on.message()
async def generic_handler(message: Message, existing_images=None, existing_vk_atts=None):
    if not message.text and not message.attachments and not existing_images: return
    payload = message.get_payload_json() or {}
    if payload.get("action") == "repeat_gen":
         state_data = message.state_peer.payload
         if state_data: asyncio.create_task(run_vk_generation(message.from_id, state_data["last_prompt"], state_data["last_images"]))
         return
    if payload.get("action") == "reset_gen": await start_handler(message); return
    image_urls, vk_attachment_strs = existing_images or [], existing_vk_atts or []
    if message.attachments:
        for att in message.attachments:
            url, vk_id = None, ""
            if att.photo: 
                 url = att.photo.sizes[-1].url; vk_id = f"photo{att.photo.owner_id}_{att.photo.id}"
                 if hasattr(att.photo, "access_key") and att.photo.access_key: vk_id += f"_{att.photo.access_key}"
            elif att.doc and att.doc.type == 1: 
                 url = att.doc.url; vk_id = f"doc{att.doc.owner_id}_{att.doc.id}"
                 if hasattr(att.doc, "access_key") and att.doc.access_key: vk_id += f"_{att.doc.access_key}"
            if url: vk_attachment_strs.append(vk_id); image_urls.append(url)
    prompt = (message.text or "").strip()
    if image_urls and not prompt:
         await bot.state_dispenser.set(message.from_id, BotState.WAIT_PROMPT, images=image_urls, vk_atts=vk_attachment_strs)
         await safe_vk_send(message.from_id, "Фото получены. Напишите задание 👇", attachment=",".join(vk_attachment_strs))
         return
    if not prompt and not image_urls: return
    async with AsyncSessionLocal() as db:
        user, _ = await services.get_or_create_user(db, message.from_id, platform="vk")
        cost = services.get_model_cost(user.model_preference)
    await bot.state_dispenser.set(message.from_id, BotState.CONFIRM_GEN, prompt=prompt, images=image_urls, cost=cost)
    await safe_vk_send(message.from_id, f"Задание получено. Стоимость: {cost} кр.", keyboard=keyboards.build_confirm_kb())

async def run_vk_generation(vk_p_id: int, prompt: str, image_urls: list):
    async with AsyncSessionLocal() as db:
        from sqlalchemy import select
        res = await db.execute(select(models.User).filter_by(vk_id=vk_p_id))
        user = res.scalars().first()
        if not user: return
        user_id, model, cost = user.id, user.model_preference, services.get_model_cost(user.model_preference)
        try:
            task_id = await services.start_generation_flow(db, user_id, prompt, image_urls, model, cost)
            for i in range(150):
                await asyncio.sleep(5)
                info = await services.check_generation_status(task_id)
                if info.get("state") in ["success", "completed"]:
                    img_url = info.get("image_url")
                    if isinstance(img_url, list) and len(img_url) > 0: img_url = img_url[0]
                    await services.commit_frozen_credits(db, user_id, cost)
                    async with httpx.AsyncClient() as client:
                        r = await client.get(img_url, timeout=60.0)
                        if r.status_code == 200:
                            photo_att = await vk_upload_photo(r.content, vk_p_id)
                            await safe_vk_send(vk_p_id, "Готово!", attachment=photo_att, keyboard=keyboards.build_after_gen_kb())
                            await bot.state_dispenser.set(vk_p_id, BotState.POST_GEN, last_url=img_url, last_prompt=prompt, last_images=image_urls)
                            return
                elif info.get("state") in ["failed", "error"]: raise Exception(info.get("error"))
            raise Exception("Timeout")
        except Exception as e:
            logger.error(f"GEN ERROR: {e}")
            await services.refund_frozen_credits(db, user_id, cost)
            await safe_vk_send(vk_p_id, f"Ошибка: {e}")

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.create_task(startup_check())
    bot.run_forever()
