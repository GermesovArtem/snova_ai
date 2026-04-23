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

# Logger setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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

# --- DIAGNOSTIC MIDDLEWARE ---
class DiagnosticMiddleware(BaseMiddleware[Message]):
    async def pre(self):
        try:
             text = self.event.text or ""
             payload = self.event.payload or ""
             logger.info(f"\n[!!!] NEW EVENT [!!!] FROM: {self.event.from_id} TEXT: '{text}' PAYLOAD: '{payload}'")
             
             cmd = text.strip().lower()
             payload_data = self.event.get_payload_json() or {}
             if cmd in ["начать", "старт", "/start"] or payload_data.get("command") == "start":
                  logger.info("-> START COMMAND DETECTED. RESETTING STATE.")
                  await bot.state_dispenser.delete(self.event.from_id)
        except Exception as e:
             logger.error(f"MIDDLEWARE ERROR: {e}")
        return True

bot.labeler.message_view.register_middleware(DiagnosticMiddleware)

# --- UTILS ---
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
        resp = await client.post("https://api.vk.com/method/photos.getMessagesUploadServer", data={"peer_id": str(peer_id), "access_token": VK_TOKEN, "v": "5.131"})
        data = resp.json()
        if "error" in data: raise Exception(f"UploadServer Error: {data['error']['error_msg']}")
        upload_url = data["response"]["upload_url"]
        files = {"photo": ("photo.jpg", image_bytes, "image/jpeg")}
        resp = await client.post(upload_url, files=files)
        upload_data = resp.json()
        resp = await client.post("https://api.vk.com/method/photos.saveMessagesPhoto", data={"photo": upload_data["photo"], "server": upload_data["server"], "hash": upload_data["hash"], "access_token": VK_TOKEN, "v": "5.131"})
        photo_resp = resp.json()
        if "error" in photo_resp: raise Exception(f"SavePhoto Error: {photo_resp['error']['error_msg']}")
        photo = photo_resp["response"][0]
        return f"photo{photo['owner_id']}_{photo['id']}"

async def safe_vk_send(peer_id: int, message: str, attachment: str = None, keyboard: str = None):
    url = "https://api.vk.com/method/messages.send"
    params = {"peer_id": str(peer_id), "message": message, "random_id": str(random.randint(1, 2**31)), "access_token": VK_TOKEN, "v": "5.131"}
    if attachment: params["attachment"] = attachment
    if keyboard: params["keyboard"] = keyboard
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(url, data=params)
            res_json = resp.json()
            if "error" in res_json: logger.error(f"VK API DIRECT ERROR: {res_json['error']}")
        except Exception as e: logger.error(f"VK DIRECT HTTP ERROR: {e}")

# --- HANDLERS ---

@bot.on.message(func=lambda msg: (msg.text or "").strip().lower() in ["начать", "начни", "старт", "/start"] or (msg.get_payload_json() or {}).get("command") == "start")
async def start_handler(message: Message):
    logger.info(f"START_HANDLER EXECUTING FOR {message.from_id}")
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

@bot.on.message(payload_map=[("set_model", str)])
async def set_model_handler(message: Message):
    new_model = message.get_payload_json()["set_model"]
    async with AsyncSessionLocal() as db:
        user, _ = await services.get_or_create_user(db, message.from_id, platform="vk")
        user.model_preference = new_model
        await db.commit()
    await message.answer(f"✅ Модель успешно изменена на: {human_model_name(new_model)}")
    await cmd_create_handler(message)

# --- STATE HANDLERS ---

@bot.on.message(state=BotState.CONFIRM_GEN)
async def confirmation_handler(message: Message):
    payload = message.get_payload_json() or {}
    if payload.get("action") == "confirm_gen":
        state_data = message.state_peer.payload
        async with AsyncSessionLocal() as db:
             user, _ = await services.get_or_create_user(db, message.from_id, platform="vk")
             cost = state_data["cost"]; balance = int(user.balance)
             if balance < cost:
                  await safe_vk_send(message.from_id, clean_markdown(messages.MSG_ERR_FUNDS.format(cost=int(cost), balance=balance)))
                  await bot.state_dispenser.delete(message.from_id); return
        await safe_vk_send(message.from_id, clean_markdown(messages.MSG_GEN_STARTING.format(model_name=human_model_name(user.model_preference))))
        asyncio.create_task(run_vk_generation(message.from_id, state_data["prompt"], state_data["images"]))
        await bot.state_dispenser.delete(message.from_id)
    elif payload.get("action") == "edit_gen" or (message.text or "").strip().lower() == "❌ отмена":
        await safe_vk_send(message.from_id, clean_markdown(messages.MSG_EDIT_GEN), keyboard=keyboards.build_reply_kb())
        await bot.state_dispenser.delete(message.from_id)

@bot.on.message(state=BotState.WAIT_PROMPT)
async def wait_prompt_handler(message: Message):
    if not message.text:
         await message.answer("Пожалуйста, введите задание текстом 👇"); return
    state_data = message.state_peer.payload
    await generic_handler(message, existing_images=state_data["images"], existing_vk_atts=state_data["vk_atts"])

@bot.on.message()
async def generic_handler(message: Message, existing_images=None, existing_vk_atts=None):
    if not message.text and not message.attachments and not existing_images: return
    payload = message.get_payload_json() or {}
    if payload.get("action") == "repeat_gen":
         state_data = message.state_peer.payload
         if state_data: asyncio.create_task(run_vk_generation(message.from_id, state_data["last_prompt"], state_data["last_images"]))
         return
    if payload.get("action") == "reset_gen": await start_handler(message); return

    cmd = (message.text or "").strip().lower()
    image_urls, vk_attachment_strs = existing_images or [], existing_vk_atts or []
    current_state = await bot.state_dispenser.get(message.from_id)
    if current_state and current_state.state == BotState.POST_GEN and message.text and not message.attachments:
         last_url = current_state.payload.get("last_url")
         if last_url: image_urls = [last_url]

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
         premium_msg = "✨ **Загрузка завершена!**\n\nВы прислали **{} фото** (см. выше 👆)\nТеперь напишите, пожалуйста, **задание** для нейросети: что именно нужно сделать? 👇".format(len(image_urls))
         await safe_vk_send(message.from_id, clean_markdown(premium_msg), attachment=",".join(vk_attachment_strs))
         return
    if not prompt and not image_urls: return
    async with AsyncSessionLocal() as db:
        user, _ = await services.get_or_create_user(db, message.from_id, platform="vk")
        cost = services.get_model_cost(user.model_preference); balance = int(user.balance)
        limit = get_limit_for_model(user.model_preference)
        if len(image_urls) > limit: image_urls = image_urls[:limit]; vk_attachment_strs = vk_attachment_strs[:limit]

    await bot.state_dispenser.set(message.from_id, BotState.CONFIRM_GEN, prompt=prompt, images=image_urls, cost=cost)
    confirm_text = messages.MSG_CONFIRMATION.format(header=messages.MSG_CONFIRM_HEADER_NEW if not image_urls else messages.MSG_CONFIRM_HEADER_EDIT, safe_prompt=prompt[:100] or "(description)", img_count_text=f"Фото: {len(image_urls)} шт.\n" if image_urls else "", human_name=human_model_name(user.model_preference), ratio="auto", fmt="png", cost=int(cost), balance=balance)
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
                    if isinstance(img_url, list) and len(img_url) > 0: img_url = img_url[0]
                    await services.commit_frozen_credits(db, user_id, cost); generation_committed = True
                    async with httpx.AsyncClient() as client:
                        r = await client.get(img_url, timeout=60.0)
                        if r.status_code == 200:
                            photo_att = await vk_upload_photo(r.content, vk_p_id)
                            user = await services.get_user_by_id(db, user_id)
                            text = messages.MSG_GEN_SUCCESS_WITH_BALANCE.format(balance=int(user.balance), model_name=human_model_name(model))
                            await safe_vk_send(vk_p_id, clean_markdown(text), attachment=photo_att, keyboard=keyboards.build_after_gen_kb())
                            await bot.state_dispenser.set(vk_p_id, BotState.POST_GEN, last_url=img_url, last_prompt=prompt, last_images=image_urls)
                            return
                elif info.get("state") in ["failed", "error"]: raise Exception(info.get("error", "KIE Error"))
            raise Exception("Timeout")
        except Exception as e:
            logger.error(f"GEN ERROR: {e}")
            if not generation_committed:
                try: await services.refund_frozen_credits(db, user_id, cost)
                except: pass
            await safe_vk_send(vk_p_id, f"❌ Ошибка: {str(e)}", keyboard=keyboards.build_reply_kb())

if __name__ == "__main__":
    bot.run_forever()
