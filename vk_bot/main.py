import os
import asyncio
import logging
import json
import httpx
import io
import re
import random
from vkbottle.bot import Bot, Message
from vkbottle import Keyboard, KeyboardButtonColor, Text, PhotoMessageUploader, DocMessagesUploader, BaseStateGroup, OpenLink, BaseMiddleware, GroupEventType, Callback
from vkbottle.bot import MessageEvent
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
logger.info("🚀 VK Bot process started. Version: 2.1 (Enhanced Multi-Photo & Polling)")


# --- STATES ---
class BotState(BaseStateGroup):
    IDLE = "idle"
    CONFIRM_GEN = "confirm_gen"
    WAIT_PROMPT = "wait_prompt"
    POST_GEN = "post_gen"

# ... (Middleware and other code remains same)

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
                  await safe_clear_state(self.event.from_id)
        except Exception:
             import traceback
             print(f"ERROR IN MIDDLEWARE:\n{traceback.format_exc()}")
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
    # Remove bold/italic blocks (multiple symbols)
    text = text.replace("***", "").replace("**", "")
    text = text.replace("___", "").replace("__", "")
    # Remove code and strike
    text = text.replace("`", "").replace("~", "")
    # Remove Markdown links [text](url) -> text
    text = re.sub(r"\[(.*?)\]\(.*?\)", r"\1", text)
    # Only remove single * or _ if they are at the start/end of a word (simple heuristic)
    # This preserves underscores in @usernames_s
    return text.strip()

def human_model_name(model_id):
    models_map = services.get_available_models()
    return next((name for name, mid in models_map.items() if mid == model_id), model_id)

async def get_vk_user_name(user_id: int) -> str:
    try:
        users = await bot.api.users.get(user_ids=[user_id])
        if users: return users[0].first_name
    except: pass
    return ""

def get_limit_for_model(model_id: str) -> int:
    return services.get_model_limit(model_id)


async def vk_upload_photo(image_bytes: bytes, peer_id: int) -> str:
    # This is the exact logic that worked today at 11:38
    # No manual httpx, just standard vkbottle uploader
    photo_uploader = PhotoMessageUploader(bot.api)
    return await photo_uploader.upload(file_source=image_bytes, peer_id=peer_id)

async def safe_vk_send(peer_id: int, message: str, attachment: str = None, keyboard: str = None):
    # Log outgoing message
    log_msg = (message[:50] + "..") if len(message) > 50 else message
    logger.info(f"OUTGOING -> {peer_id}: '{log_msg}' [atts={attachment}]")
    
    message = clean_markdown(message)
    url = "https://api.vk.com/method/messages.send"
    params = {
        "peer_id": str(peer_id), 
        "message": message, 
        "random_id": str(random.randint(1, 2**31)), 
        "access_token": VK_TOKEN, 
        "v": "5.131"
    }
    if attachment: params["attachment"] = attachment
    if keyboard: params["keyboard"] = keyboard
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(url, data=params)
            res_json = resp.json()
            if "error" in res_json: logger.error(f"VK API ERROR: {res_json['error']}")
        except Exception as e: logger.error(f"VK SEND EXCEPTION: {e}")

async def safe_clear_state(peer_id: int):
    """Safely delete state without raising KeyError if it doesn't exist."""
    try:
        await bot.state_dispenser.delete(peer_id)
    except (KeyError, Exception):
        pass

@bot.on.message(func=lambda msg: (msg.text or "").strip().lower() in ["начать", "начни", "старт", "/start", "start"] or (msg.get_payload_json() or {}).get("command") in ["start", "begin"])
async def start_handler(message: Message):
    # Log to console to verify the trigger
    print(f"\n[START_HANDLER] Triggered for user {message.from_id} | Text: '{message.text}' | Payload: '{message.payload}'\n")
    
    # Always clear state on start
    await safe_clear_state(message.from_id)
    async with AsyncSessionLocal() as db:
        real_name = await get_vk_user_name(message.from_id)
        user, created = await services.get_or_create_user(db, platform_id=message.from_id, name=real_name or f"VK_{message.from_id}", platform="vk")
        if not created and real_name and (not user.name or "VK_" in user.name):
             user.name = real_name
             await db.commit()
        # Show newbie message if user is literally new OR if they have 0 balance and haven't got bonus yet
        if created or (user.balance == 0 and not user.bonus_received):
            text = messages.MSG_START_NEW_VK.format(balance=int(user.balance))
            kb = keyboards.build_sub_check_kb()
        else:
            text = messages.MSG_START_REGULAR.format(name=user.name or "", balance=int(user.balance))
            kb = keyboards.build_reply_kb()
    await safe_vk_send(message.from_id, clean_markdown(text), keyboard=kb)

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
        safe_prompt=prompt,
        img_count_text=img_count_text,
        human_name=human_name,
        ratio=ratio,
        fmt=fmt.upper(),
        cost=int(cost),
        balance=int(balance)
    )

    # Save to state
    await bot.state_dispenser.set(vk_p_id, BotState.CONFIRM_GEN, prompt=prompt, images=image_urls, vk_atts=vk_attachment_strs, cost=cost, settings=settings, is_refinement=is_refinement)
    
    attachment = ",".join(vk_attachment_strs[:10]) if vk_attachment_strs else None

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

@bot.on.message(payload_map=[("set_setting", str), ("value", str)])
async def set_setting_handler(message: Message):
    payload = message.get_payload_json()
    key = payload["set_setting"]
    value = payload["value"]
    state = await bot.state_dispenser.get(message.from_id)
    if not state or not state.payload: return
    settings = state.payload.get("settings", {"aspect_ratio": "1:1", "output_format": "png"})
    settings[key] = value
    # Re-save state
    await bot.state_dispenser.set(message.from_id, state.state, **state.payload, settings=settings)
    
    async with AsyncSessionLocal() as db:
        user, _ = await services.get_or_create_user(db, message.from_id, platform="vk")
        model_id = user.model_preference

    await safe_vk_send(message.from_id, f"Выбрано: {value}", keyboard=keyboards.build_settings_kb(settings, model_id))

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
    await safe_clear_state(message.from_id)
    async with AsyncSessionLocal() as db:
        user, _ = await services.get_or_create_user(db, message.from_id, platform="vk")
        limit = get_limit_for_model(user.model_preference)
    await safe_vk_send(message.from_id, clean_markdown(messages.MSG_GEN_PROMPT.format(limit=limit)), keyboard=keyboards.build_reply_kb())


@bot.on.message(text=["🤖 модель", "🤖 Модель", "Модель", "модель"])
async def model_menu_handler(message: Message):
    async with AsyncSessionLocal() as db:
        user, _ = await services.get_or_create_user(db, message.from_id, platform="vk")
        costs_str = os.getenv("CREDITS_PER_MODEL", '{"nano-banana-2-1k": 1, "nano-banana-2-4k": 2, "nano-banana-pro-2k": 2, "nano-banana-pro-4k": 3, "gpt-image-2": 3}')
        text = messages.MSG_MODEL_MENU.format(human_name=human_model_name(user.model_preference), limit=get_limit_for_model(user.model_preference), balance=int(user.balance))
    await safe_vk_send(message.from_id, clean_markdown(text), keyboard=keyboards.build_model_menu_kb(services.get_available_models(), user.model_preference, json.loads(costs_str)))


@bot.on.message(payload_map=[("action", str)])
async def action_handler(message: Message):
    action = message.get_payload_json()["action"]
    if action == "confirm_gen":
        state = await bot.state_dispenser.get(message.from_id)
        if not state or not state.payload:
             await safe_vk_send(message.from_id, "Ошибка: данные не найдены. Пожалуйста, пришлите фото или текст снова.")
             return
        
        p = state.payload
        prompt = p.get("prompt")
        images = p.get("images", [])
        settings = p.get("settings", {})
        is_refinement = p.get("is_refinement", False)
        
        async with AsyncSessionLocal() as db:
            user, _ = await services.get_or_create_user(db, message.from_id, platform="vk")
            model_name = human_model_name(user.model_preference)
        
        await safe_vk_send(message.from_id, messages.MSG_GEN_STARTING.format(model_name=model_name))
        
        res = "1K"
        if "-4k" in user.model_preference.lower() or "gpt-image-2" in user.model_preference.lower(): res = "4K"
        elif "-2k" in user.model_preference: res = "2K"
        
        asyncio.create_task(run_vk_generation(
            vk_p_id=message.from_id, 
            prompt=prompt, 
            image_urls=images,
            aspect_ratio=settings.get("aspect_ratio", "1:1"),
            resolution=res,
            output_format=settings.get("output_format", "png"),
            is_refinement=is_refinement
        ))
        await bot.state_dispenser.delete(message.from_id)

    elif action == "edit_gen":
        await bot.state_dispenser.delete(message.from_id)
        await safe_vk_send(message.from_id, messages.MSG_EDIT_GEN)
        
    elif action == "settings_menu":
        state = await bot.state_dispenser.get(message.from_id)
        if not state or not state.payload: return
        
        async with AsyncSessionLocal() as db:
            user, _ = await services.get_or_create_user(db, message.from_id, platform="vk")
            model_id = user.model_preference

        p = state.payload
        settings = p.get("settings")
        if not settings:
            ratio = "16:9" if "gpt-image-2" in model_id.lower() else "1:1"
            settings = {"aspect_ratio": ratio, "output_format": "png" if "pro" in model_id else "jpg"}
            p["settings"] = settings
            await bot.state_dispenser.set(message.from_id, state.state, **p)

        await safe_vk_send(message.from_id, messages.MSG_SETTINGS_MENU, keyboard=keyboards.build_settings_kb(settings, model_id))

    elif action == "confirm_settings":
        state = await bot.state_dispenser.get(message.from_id)
        if not state or not state.payload: return
        p = state.payload
        await show_confirmation(message.from_id, p["prompt"], p["images"], p.get("vk_atts"), p.get("is_refinement", False), p.get("settings"))

    elif action == "refine_gen":
        state = await bot.state_dispenser.get(message.from_id)
        if not state or not state.payload or "last_url" not in state.payload:
            await safe_vk_send(message.from_id, "Ошибка: результат не найден.")
            return
        last_url = state.payload["last_url"]
        
        # Give immediate feedback
        await safe_vk_send(message.from_id, "⏳ Подготавливаю превью для редактирования...")
        
        # Download and upload to VK to show it
        vk_id = None
        try:
            async with httpx.AsyncClient() as client:
                 r = await client.get(last_url, timeout=30)
                 vk_id = await vk_upload_photo(r.content, message.from_id)
        except: pass

        await bot.state_dispenser.set(message.from_id, BotState.WAIT_PROMPT, images=[last_url], vk_atts=[vk_id] if vk_id else [], is_refinement=True)
        await safe_vk_send(message.from_id, "Бот запомнил это фото. Напишите, что нужно изменить? 👇", attachment=vk_id)

    elif action == "repeat_gen":
        state = await bot.state_dispenser.get(message.from_id)
        if not state or not state.payload: return
        p = state.payload
        prompt = p.get("last_prompt")
        images = p.get("last_images", [])
        if not prompt: return
        
        # Give immediate feedback
        await safe_vk_send(message.from_id, "⏳ Подготавливаю повторную генерацию...")
        
        vk_atts = []
        if images:
             try:
                 async with httpx.AsyncClient() as client:
                      # Upload up to 5 photos for preview to avoid VK timeouts/limits
                      for img_url in images[:5]:
                          r = await client.get(img_url, timeout=30)
                          vk_id = await vk_upload_photo(r.content, message.from_id)
                          vk_atts.append(vk_id)
             except Exception as e:
                 logger.error(f"Error uploading photos for repeat_gen: {e}")


        await safe_vk_send(message.from_id, "🔄 Повторяем генерацию! Проверьте настройки:")
        await show_confirmation(message.from_id, prompt, images, vk_attachment_strs=vk_atts)

    elif action == "check_sub":
        group_id = "233112492"
        url = "https://api.vk.com/method/groups.isMember"
        params = {"group_id": group_id, "user_id": str(message.from_id), "access_token": VK_TOKEN, "v": "5.199"}
        async with httpx.AsyncClient() as client:
            try:
                resp = await client.post(url, data=params)
                res = resp.json()
                if res.get("response") == 1:
                    async with AsyncSessionLocal() as db:
                        user, _ = await services.get_or_create_user(db, message.from_id, platform="vk")
                        if not user.bonus_received:
                            user.balance += 3.0
                            user.bonus_received = True
                            await db.commit()
                            await safe_vk_send(message.from_id, messages.MSG_SUB_SUCCESS, keyboard=keyboards.build_reply_kb())
                        else:
                            await safe_vk_send(message.from_id, messages.MSG_SUB_ALREADY, keyboard=keyboards.build_reply_kb())
                else:
                    await safe_vk_send(message.from_id, messages.MSG_SUB_FAIL, keyboard=keyboards.build_sub_check_kb())
            except Exception as e:
                logger.error(f"Check sub error: {e}")
                await safe_vk_send(message.from_id, "Ошибка при проверке подписки. Попробуйте позже.")
    elif action == "reset_gen":
        await safe_clear_state(message.from_id)
        await safe_vk_send(message.from_id, messages.MSG_CANCEL_FSM, keyboard=keyboards.build_reply_kb())

# Burst accumulator for VK messages (since VK has no media groups)
pending_bursts = {}
user_locks = {}

import time
arrival_times = {}

@bot.on.message()
async def generic_handler(message: Message):
    # Ignore payloads and empty messages
    if not message.text and not message.attachments: return
    if message.get_payload_json(): return
    
    user_id = message.peer_id
    now = time.time()
    dt = now - arrival_times.get(user_id, 0)
    arrival_times[user_id] = now
    logger.info(f"--- Message {message.id} from {user_id} arrived. DT: {dt:.3f}s ---")
    
    # NEW: Fetch FULL message from API to bypass potential payload truncation
    try:
        full_msgs = await bot.api.messages.get_by_id(message_ids=[message.id])
        if full_msgs and full_msgs.items:
            message = full_msgs.items[0]
            logger.info(f"  -> Fetched full message. Atts found: {len(message.attachments or [])}")
    except Exception as e:
        logger.warning(f"  -> Failed to fetch full message: {e}")

    # RAW LOGGING for deep debugging (Safer way)
    try:
        atts_summary = []
        if message.attachments:
            for a in message.attachments:
                atts_summary.append({"type": a.type, "id": getattr(a, "id", "no-id")})
        
        logger.info(f"DEBUG: Msg ID {message.id} | Final Atts: {len(message.attachments or [])} | Types: {atts_summary}")
    except Exception as raw_e:
        logger.error(f"Debug logging error: {raw_e}")


    
    # Atomic-like initialization of the burst list
    if user_id not in pending_bursts:
        pending_bursts[user_id] = []
    
    # Add current message to burst
    pending_bursts[user_id].append(message)
    
    # Wait for more messages in the burst (0.6s is a good balance)
    await asyncio.sleep(0.6)
    
    # Check if this is still the last message. 
    if message != pending_bursts[user_id][-1]:
        return

    
    # We are the last message! Take all accumulated messages and clear the list
    messages_to_process = pending_bursts[user_id]
    pending_bursts[user_id] = []
    
    # Atomic-like initialization of the lock
    if user_id not in user_locks:
        user_locks[user_id] = asyncio.Lock()
    
    lock = user_locks[user_id]
    async with lock:
        await _process_merged_burst(user_id, messages_to_process)

async def _process_merged_burst(user_id: int, burst: list[Message]):
    # Use the last message for context (state check, reply destination)
    last_msg = burst[-1]
    
    logger.info(f"--- Processing BURST from {user_id} ({len(burst)} messages) ---")
    
    # 1. Load existing context from state
    state = await bot.state_dispenser.get(user_id)
    
    image_urls, vk_attachment_strs = [], []
    is_refinement = False
    
    if state:
        # Robust state name checking (handle vkbottle's "Group:state" format)
        s_name_upper = str(state.state).upper()
        logger.info(f"DEBUG: Loaded state for {user_id}: {state.state}")
        
        if "WAIT_PROMPT" in s_name_upper or "CONFIRM_GEN" in s_name_upper:
            image_urls = state.payload.get("images", []).copy()
            vk_attachment_strs = state.payload.get("vk_atts", []).copy()
            is_refinement = state.payload.get("is_refinement", False)
            logger.info(f"  -> Merging with {len(image_urls)} existing images from state")


    # 2. Accumulate NEW data from ALL messages in the burst
    prompt = ""
    for msg in burst:
        if msg.text:
            prompt = msg.text.strip()
            
        # Recursive attachment extraction
        def get_all_atts(m):
            atts = list(m.attachments or [])
            if m.fwd_messages:
                for fwd in m.fwd_messages:
                    atts.extend(get_all_atts(fwd))
            if m.reply_message:
                atts.extend(get_all_atts(m.reply_message))
            return atts

        all_atts = get_all_atts(msg)
        if len(all_atts) > 1:
            logger.info(f"  -> Found {len(all_atts)} total attachments (including nested)")

        for att in all_atts:
            url, vk_id = None, ""
            if att.photo: 
                 url = att.photo.sizes[-1].url
                 vk_id = f"photo{att.photo.owner_id}_{att.photo.id}"
                 if hasattr(att.photo, "access_key") and att.photo.access_key: vk_id += f"_{att.photo.access_key}"
                 logger.info(f"    - Found PHOTO in nested: {vk_id}")
            elif att.doc:
                 ext = (att.doc.ext or "").lower()
                 if att.doc.type == 1 or ext in ['jpg', 'jpeg', 'png', 'webp', 'heic', 'bmp']:
                     url = att.doc.url
                     vk_id = f"doc{att.doc.owner_id}_{att.doc.id}"
                     if hasattr(att.doc, "access_key") and att.doc.access_key: vk_id += f"_{att.doc.access_key}"
                     logger.info(f"    - Found DOC IMAGE in nested: {vk_id}")
            
            if url and url not in image_urls:
                vk_attachment_strs.append(vk_id)
                image_urls.append(url)


    # 3. Check Limits
    async with AsyncSessionLocal() as db:
        user, _ = await services.get_or_create_user(db, user_id, platform="vk")
        limit = get_limit_for_model(user.model_preference)

    if len(image_urls) > limit:
        await safe_vk_send(user_id, messages.MSG_ERR_LIMIT.format(limit=limit, count=len(image_urls)))
        image_urls = image_urls[:limit]
        vk_attachment_strs = vk_attachment_strs[:limit]

    # 4. Handle logic (Images only vs Prompt+Images)
    if image_urls and not prompt:
         await bot.state_dispenser.set(user_id, BotState.WAIT_PROMPT, images=image_urls, vk_atts=vk_attachment_strs, is_refinement=is_refinement)
         logger.info(f"  -> State updated for {user_id}: {len(image_urls)} images saved.")
         count_text = f" ({len(image_urls)} шт.)" if len(image_urls) > 1 else ""
         preview_atts = ",".join(vk_attachment_strs[:10]) if vk_attachment_strs else None
         await safe_vk_send(user_id, f"📸 Фото получены{count_text}. Напишите задание 👇", attachment=preview_atts)
         return

    if not prompt and not image_urls:
        return
    
    # We have both prompt and (optionally) images (either new or from state)
    logger.info(f"  -> Showing confirmation for {user_id} with {len(image_urls)} images and prompt: '{prompt}'")
    await show_confirmation(user_id, prompt, image_urls, vk_attachment_strs, is_refinement=is_refinement)



async def run_vk_generation(vk_p_id: int, prompt: str, image_urls: list, aspect_ratio: str = "1:1", resolution: str = "1K", output_format: str = "png", is_refinement: bool = False):
    async with AsyncSessionLocal() as db:
        from sqlalchemy import select
        res = await db.execute(select(models.User).filter_by(vk_id=vk_p_id))
        user = res.scalars().first()
        if not user: return
        user_id, model, cost = user.id, user.model_preference, services.get_model_cost(user.model_preference)
        try:
            task_id = await services.start_generation_flow(db, user_id, prompt, image_urls, model, cost, aspect_ratio=aspect_ratio, resolution=resolution, output_format=output_format, is_refinement=is_refinement)
            for i in range(240): # 240 * 5s = 1200s (20 mins)
                await asyncio.sleep(5)
                info = await services.check_generation_status(task_id)
                if info.get("state") in ["success", "completed"]:
                    img_url = info.get("image_url")
                    if isinstance(img_url, list) and len(img_url) > 0: img_url = img_url[0]
                    
                    if not img_url:
                        raise Exception("Ошибка: KIE вернул успех, но URL изображения пуст.")

                    await services.commit_frozen_credits(db, user_id, cost)
                    async with httpx.AsyncClient() as client:
                        try:
                            r = await client.get(img_url, timeout=120.0)
                            if r.status_code != 200:
                                raise Exception(f"Не удалось скачать готовое фото (HTTP {r.status_code})")
                        except Exception as download_err:
                            raise Exception(f"Ошибка при скачивании результата: {download_err}")

                        try:
                            # Log content size for debugging
                            logger.info(f"Uploading result for user {vk_p_id}. Size: {len(r.content)} bytes")
                            
                            # 1. Upload Preview Photo (with fallback to document if it fails)
                            photo_att = None
                            try:
                                photo_att = await vk_upload_photo(r.content, vk_p_id)
                            except Exception as photo_err:
                                logger.warning(f"Photo upload failed, trying as doc: {photo_err}")
                                doc_uploader = DocMessagesUploader(bot.api)
                                doc_res = await doc_uploader.upload(title="preview.png", file_source=r.content, peer_id=vk_p_id)
                                photo_att = doc_res
                            
                            # 2. Upload Document (High Quality Original)
                            doc_uploader = DocMessagesUploader(bot.api)
                            doc_att = await doc_uploader.upload(
                                title=f"gen_{task_id[:8]}.png", 
                                file_source=r.content, 
                                peer_id=vk_p_id
                            )
                            
                            await safe_vk_send(vk_p_id, "🔥 Готово!", attachment=photo_att, keyboard=keyboards.build_after_gen_kb())
                            await safe_vk_send(vk_p_id, "💾 Оригинал (без сжатия)", attachment=doc_att)
                            
                            await bot.state_dispenser.set(vk_p_id, BotState.POST_GEN, last_url=img_url, last_prompt=prompt, last_images=image_urls)
                            return
                        except Exception as upload_err:
                            print(f"VK UPLOAD ERROR: {upload_err}")
                            raise Exception(f"Ошибка при отправке фото в ВК: {upload_err}")

                elif info.get("state") in ["failed", "error"]:
                    raise Exception(info.get("error") or "Ошибка на стороне нейросети")
            
            raise Exception("Timeout: Время ожидания истекло (20 мин)")
        except Exception as e:
            print(f"GEN ERROR: {e}")
            # Use our translation service to make it friendly
            friendly_err = services.translate_error(str(e))
            await safe_vk_send(vk_p_id, friendly_err)

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.create_task(startup_check())
    bot.run_forever()
