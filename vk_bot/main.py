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

# --- MEGA DIAGNOSTIC MIDDLEWARE ---
class DiagnosticMiddleware(BaseMiddleware[Message]):
    async def pre(self):
        try:
             text = self.event.text or ""
             payload = self.event.payload or ""
             print(f"\n[!!!] NEW EVENT DETECTED [!!!] FROM: {self.event.from_id} TEXT: '{text}' PAYLOAD: '{payload}'")
             
             cmd = text.strip().lower()
             payload_data = self.event.get_payload_json() or {}
             if cmd in ["начать", "старт", "/start"] or payload_data.get("command") == "start":
                  print("-> TRIGGER: START COMMAND. RESETTING STATE.")
                  await bot.state_dispenser.delete(self.event.from_id)
        except Exception as e:
             print(f"ERROR IN MIDDLEWARE: {e}")
        return True

bot.labeler.message_view.register_middleware(DiagnosticMiddleware)

# --- ROBUST STARTUP CHECK ---
async def startup_check():
    async with httpx.AsyncClient() as client:
        try:
            print("\n" + "="*50)
            print(">>> VERIFYING GROUP TOKEN...")
            resp = await client.post("https://api.vk.com/method/groups.getById", data={
                "access_token": VK_TOKEN,
                "v": "5.199"
            })
            data = resp.json()
            if "response" in data and len(data["response"]) > 0:
                group = data["response"][0]
                print(f">>> BOT STARTUP SUCCESSFUL <<<")
                print(f">>> LISTENING TO GROUP: {group['name']} (ID: {group['id']})")
            else:
                print(f"!!! STARTUP WARNING: COULD NOT GET GROUP INFO !!!")
                print(f"!!! VK API ANSWER: {data}")
            print("="*50 + "\n")
        except Exception as e:
            print(f"!!! STARTUP CHECK EXCEPTION: {e}")

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
            if "error" in res_json: print(f"VK API ERROR LOG: {res_json['error']}")
        except Exception as e: print(f"VK SEND EXCEPTION: {e}")

@bot.on.message(func=lambda msg: (msg.text or "").strip().lower() in ["начать", "начни", "старт", "/start"] or (msg.get_payload_json() or {}).get("command") == "start")
async def start_handler(message: Message):
    print(f"START_HANDLER EXECUTING FOR {message.from_id}")
    async with AsyncSessionLocal() as db:
        real_name = await get_vk_user_name(message.from_id)
        user, created = await services.get_or_create_user(db, platform_id=message.from_id, name=real_name or f"VK_{message.from_id}", platform="vk")
        if not created and real_name and (not user.name or "VK_" in user.name):
             user.name = real_name
             await db.commit()
        limit = get_limit_for_model(user.model_preference)
        text = messages.MSG_START_NEW.format(balance=int(user.balance), limit=limit) if created else messages.MSG_START_REGULAR.format(name=user.name or "", balance=int(user.balance))
    await safe_vk_send(message.from_id, clean_markdown(text), keyboard=keyboards.build_reply_kb())

async def show_confirmation(vk_p_id: int, prompt: str, image_urls: list, vk_attachment_strs: list = None, is_refinement: bool = False, settings: dict = None):
    async with AsyncSessionLocal() as db:
        user, _ = await services.get_or_create_user(db, vk_p_id, platform="vk")
        model_id = user.model_preference
        cost = services.get_model_cost(model_id)
        balance = user.balance
        human_name = human_model_name(model_id)

    settings = settings or {"aspect_ratio": "1:1", "output_format": "png"}
    ratio = settings.get("aspect_ratio", "1:1")
    fmt = settings.get("output_format", "png")

    header = messages.MSG_CONFIRM_HEADER_REFINE if is_refinement else messages.MSG_CONFIRM_HEADER_NEW
    img_count_text = f"📸 Фото: {len(image_urls)} шт.\n" if len(image_urls) > 0 else ""
    
    text = messages.MSG_CONFIRMATION.format(
        header=header,
        safe_prompt=prompt[:150] + ("..." if len(prompt) > 150 else ""),
        img_count_text=img_count_text,
        human_name=human_name,
        ratio=ratio,
        fmt=fmt.upper(),
        cost=int(cost),
        balance=int(balance)
    )

    # Save to state
    await bot.state_dispenser.set(vk_p_id, BotState.CONFIRM_GEN, prompt=prompt, images=image_urls, vk_atts=vk_attachment_strs, cost=cost, settings=settings, is_refinement=is_refinement)
    
    attachment = ",".join(vk_attachment_strs) if vk_attachment_strs else None
    await safe_vk_send(vk_p_id, clean_markdown(text), attachment=attachment, keyboard=keyboards.build_confirm_kb())

async def balance_handler(message: Message):
    async with AsyncSessionLocal() as db:
        user, _ = await services.get_or_create_user(db, message.from_id, platform="vk")
        balance = int(user.balance)
    packs_str = os.getenv("CREDIT_PACKS", '{"149": 10, "299": 25, "899": 100}')
    packs = json.loads(packs_str)
    await safe_vk_send(message.from_id, messages.MSG_BUY_MENU.format(balance=balance), keyboard=keyboards.build_buy_kb(packs))

async def contacts_handler(message: Message):
    await safe_vk_send(message.from_id, clean_markdown(messages.MSG_CONTACTS))

@bot.on.message(payload_map=[("set_model", str)])
async def set_model_handler(message: Message):
    model = message.get_payload_json()["set_model"]
    async with AsyncSessionLocal() as db:
        user, _ = await services.get_or_create_user(db, message.from_id, platform="vk")
        user.model_preference = model
        await db.commit()
    await safe_vk_send(message.from_id, messages.MSG_MODEL_SET_SUCCESS)
    limit = get_limit_for_model(model)
    await safe_vk_send(message.from_id, messages.MSG_MODEL_SET_NEXT.format(limit=limit), keyboard=keyboards.build_reply_kb())

@bot.on.message(payload_map=[("buy", str)])
async def buy_handler(message: Message):
    payload = message.get_payload_json()
    price = payload["buy"]
    amount = payload.get("amount", "0")
    async with AsyncSessionLocal() as db:
        user, _ = await services.get_or_create_user(db, message.from_id, platform="vk")
        description = f"Пополнение на {amount} ⚡ для S•NOVA AI (VK)"
        try:
            payment_url = await services.create_yookassa_payment(db, user.id, float(price), description)
            await safe_vk_send(message.from_id, f"Счет на {price} руб. создан. После оплаты баланс пополнится автоматически.", keyboard=keyboards.build_pay_link_kb(payment_url))
        except Exception as e:
            logger.error(f"Payment error: {e}")
            await safe_vk_send(message.from_id, "Ошибка при создании счета. Попробуйте позже.")

@bot.on.message(payload_map=[("action", str)])
async def action_handler(message: Message):
    action = message.get_payload_json()["action"]
    if action == "confirm_gen":
        state = message.state_peer
        if not state or not state.payload:
             await safe_vk_send(message.from_id, "Ошибка: данные не найдены. Пожалуйста, пришлите фото или текст снова.")
             return
        
        p = state.payload
        prompt = p.get("prompt")
        images = p.get("images", [])
        settings = p.get("settings", {})
        
        async with AsyncSessionLocal() as db:
            user, _ = await services.get_or_create_user(db, message.from_id, platform="vk")
            model_name = human_model_name(user.model_preference)
        
        await safe_vk_send(message.from_id, messages.MSG_GEN_STARTING.format(model_name=model_name))
        
        # Determine resolution from model
        res = "1K"
        if "-4k" in user.model_preference: res = "4K"
        elif "-2k" in user.model_preference: res = "2K"
        
        asyncio.create_task(run_vk_generation(
            vk_p_id=message.from_id, 
            prompt=prompt, 
            image_urls=images,
            aspect_ratio=settings.get("aspect_ratio", "1:1"),
            resolution=res,
            output_format=settings.get("output_format", "png")
        ))
        await bot.state_dispenser.delete(message.from_id)
        
    elif action == "edit_gen":
        await bot.state_dispenser.delete(message.from_id)
        await safe_vk_send(message.from_id, messages.MSG_EDIT_GEN)
    elif action == "repeat_gen":
        state = message.state_peer
        if state and state.payload:
             p = state.payload
             if p.get("last_prompt"):
                  asyncio.create_task(run_vk_generation(message.from_id, p["last_prompt"], p.get("last_images", [])))
    elif action == "reset_gen":
        await bot.state_dispenser.delete(message.from_id)
        await start_handler(message)
    elif action == "settings_menu":
        state = message.state_peer
        if not state or not state.payload: return
        settings = state.payload.get("settings", {"aspect_ratio": "1:1", "output_format": "png"})
        await safe_vk_send(message.from_id, messages.MSG_SETTINGS_MENU, keyboard=keyboards.build_settings_kb(settings))
    elif action == "confirm_settings":
        state = message.state_peer
        if not state or not state.payload: return
        p = state.payload
        await show_confirmation(message.from_id, p["prompt"], p["images"], p.get("vk_atts"), p.get("is_refinement", False), p.get("settings"))

@bot.on.message(payload_map=[("set_setting", str), ("value", str)])
async def set_setting_handler(message: Message):
    payload = message.get_payload_json()
    key = payload["set_setting"]
    value = payload["value"]
    state = message.state_peer
    if not state or not state.payload: return
    settings = state.payload.get("settings", {"aspect_ratio": "1:1", "output_format": "png"})
    settings[key] = value
    await bot.state_dispenser.set(message.from_id, BotState.CONFIRM_GEN, **state.payload, settings=settings)
    await safe_vk_send(message.from_id, f"Выбрано: {value}", keyboard=keyboards.build_settings_kb(settings))

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
    if message.get_payload_json(): return
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
    await show_confirmation(message.from_id, prompt, image_urls, vk_attachment_strs)

async def run_vk_generation(vk_p_id: int, prompt: str, image_urls: list, aspect_ratio: str = "1:1", resolution: str = "1K", output_format: str = "png"):
    async with AsyncSessionLocal() as db:
        from sqlalchemy import select
        res = await db.execute(select(models.User).filter_by(vk_id=vk_p_id))
        user = res.scalars().first()
        if not user: return
        user_id, model, cost = user.id, user.model_preference, services.get_model_cost(user.model_preference)
        try:
            task_id = await services.start_generation_flow(db, user_id, prompt, image_urls, model, cost, aspect_ratio=aspect_ratio, resolution=resolution, output_format=output_format)
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
            print(f"GEN ERROR: {e}")
            await services.refund_frozen_credits(db, user_id, cost)
            await safe_vk_send(vk_p_id, f"Ошибка: {e}")

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.create_task(startup_check())
    bot.run_forever()
