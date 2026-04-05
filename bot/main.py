import asyncio
import logging
import os
import io
import httpx
from PIL import Image
print("\n" + "!"*50)
print("!!! BOT MAIN.PY: VERSION 9.5 (START ONLY) !!!")
print("!"*50 + "\n")


import json
from aiogram import Bot, Dispatcher, types, F, Router
from aiogram.filters import CommandStart, Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, BotCommand, URLInputFile, InputMediaPhoto, ReplyKeyboardMarkup, KeyboardButton, BotCommandScopeAllPrivateChats, BotCommandScopeDefault
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.storage.base import StorageKey
from dotenv import load_dotenv

from backend.database import get_db, AsyncSessionLocal, engine, Base
from backend import services
from bot import messages
from yookassa import Configuration, Payment
import uuid

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
Configuration.account_id = os.getenv("YOOKASSA_SHOP_ID")
Configuration.secret_key = os.getenv("YOOKASSA_SECRET_KEY")
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

user_router = Router()
dp.include_router(user_router)

media_groups = {} # media_group_id -> { "messages": [], "timer": asyncio.Task }

class GenState(StatesGroup):
    waiting_for_prompt = State()
    confirming = State()
    choosing_settings = State()

def get_available_models():
    return services.get_available_models()

def get_model_limit(model_id: str) -> int:
    return services.get_model_limit(model_id)


def get_model_costs():
    costs_str = os.getenv("CREDITS_PER_MODEL", '{"nano-banana-2": 3.0, "nano-banana-pro": 4.0}')
    try:
        costs = json.loads(costs_str)
        return {services.normalize_model_id(k): v for k, v in costs.items()}
    except:
        return {"nano-banana-2": 3.0, "nano-banana-pro": 4.0}


def get_credit_packs():
    packs_str = os.getenv("CREDIT_PACKS", '{"149": 10, "299": 25, "899": 100}')
    try:
        return json.loads(packs_str)
    except:
        return {"149": 10, "299": 25, "899": 100}

def generate_model_menu_text(balance: float, current_mm: str):
    models = get_available_models()
    human_name = next((name for name, mm in models.items() if mm == current_mm), current_mm)
    limit = get_model_limit(current_mm)
    
    return messages.MSG_MODEL_MENU.format(
        human_name=human_name,
        limit=limit,
        balance=int(balance)
    )


def build_main_kb(current_model: str):
    kb = InlineKeyboardBuilder()
    models = get_available_models()
    costs = get_model_costs()
    for name, mm in models.items():
        norm_mm = services.normalize_model_id(mm)
        cost = int(costs.get(norm_mm, 3))
        prefix = "✅ " if mm == current_model else ("🆕 " if "2" in name else "")
        kb.button(text=f"{prefix}{name} ({cost} кр)", callback_data=f"set_model:{mm}")
    
    kb.adjust(1)
    return kb.as_markup()

def build_start_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="👉 Выбрать модель", callback_data="main_menu")
    return kb.as_markup()

def build_reply_kb():
    kb = ReplyKeyboardBuilder()
    kb.button(text="✨ Создать")
    kb.button(text="🤖 Модель")
    kb.button(text="💳 Баланс")
    kb.button(text="📬 Контакты")
    kb.adjust(2)
    return kb.as_markup(resize_keyboard=True, is_persistent=True)

def build_cancel_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="↩️ Назад", callback_data="cancel_fsm")
    return kb.as_markup()

def build_after_gen_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="🔄 Повторить генерацию", callback_data="gen_similar")
    kb.button(text="🖼 Начать заново", callback_data="cancel_fsm")
    kb.adjust(1)
    return kb.as_markup()

def build_confirm_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="🚀 Сгенерировать", callback_data="confirm_gen")
    kb.button(text="⚙️ Настройки", callback_data="settings_menu")
    kb.button(text="✏️ Изменить", callback_data="edit_gen")
    kb.adjust(1)
    return kb.as_markup()

def build_settings_kb(model_id: str, settings: dict):
    kb = InlineKeyboardBuilder()
    
    # 1. Aspect Ratio
    cur_ratio = settings.get("aspect_ratio", "1:1")
    ratios = ["1:1", "16:9", "9:16", "3:4", "4:3", "21:9"]
    if "nano-banana-2" in model_id: ratios.insert(0, "auto")
    
    kb.button(text="📐 Размер:", callback_data="noop")
    # Fix: Use | as delimiter to avoid collision with aspect ratio values like 1:1
    for r in ratios:
        prefix = "🔘 " if r == cur_ratio else ""
        kb.button(text=f"{prefix}{r}", callback_data=f"set_setting|aspect_ratio|{r}")
    
    # 2. Resolution
    cur_res = settings.get("resolution", "1K")
    kb.button(text="💎 Качество:", callback_data="noop")
    for res in ["1K", "2K", "4K"]:
        prefix = "🔘 " if res == cur_res else ""
        kb.button(text=f"{prefix}{res}", callback_data=f"set_setting|resolution|{res}")
        
    # 3. Format
    cur_fmt = settings.get("output_format", "png" if "pro" in model_id else "jpg")
    kb.button(text="📁 Формат:", callback_data="noop")
    for fmt in ["png", "jpg"]:
        prefix = "🔘 " if fmt == cur_fmt else ""
        kb.button(text=f"{prefix}{fmt.upper()}", callback_data=f"set_setting|output_format|{fmt}")

    kb.button(text="✅ Готово", callback_data="confirm_settings")
    kb.adjust(1, 4, 1, 3, 1, 2, 1)
    return kb.as_markup()

async def setup_bot_commands(bot: Bot):
    # Instead of deleting, just set ONE useful command (/start)
    try:
        commands = [
            BotCommand(command="start", description="🚀 Перезапустить бота")
        ]
        await bot.set_my_commands(commands, scope=BotCommandScopeDefault())
        await bot.set_my_commands(commands, scope=BotCommandScopeAllPrivateChats())
        print("DEBUG: Set /start command successfully.")
    except Exception as e:
        print(f"DEBUG: Error setting commands: {e}")

@user_router.message(CommandStart())
async def cmd_start(message: types.Message, state: FSMContext):
    await state.clear()
    async with AsyncSessionLocal() as db:
        user = await services.get_or_create_user(db, message.from_user.id, message.from_user.username)
        limit = get_model_limit(services.normalize_model_id(user.model_preference))
        actual_model = human_model_name(user.model_preference)
        
        text = messages.MSG_START.format(balance=int(user.balance), limit=limit, model=actual_model)
        await message.answer(text, reply_markup=build_reply_kb(), parse_mode="Markdown")

# --- REDIRECTS FOR OLD COMMANDS ---
@user_router.message(Command("model"))
@user_router.message(Command("buy"))
@user_router.message(Command("gen"))
@user_router.message(Command("contacts"))
@user_router.message(Command("bots"))
@user_router.message(Command("example"))
@user_router.message(Command("friend"))
async def catch_old_commands(message: types.Message):
    await message.answer("💡 Пожалуйста, используйте кнопки в меню ниже для управления ботом.", reply_markup=build_reply_kb())

@user_router.message(F.text.startswith("/"))
async def catch_any_command(message: types.Message):
    # Ignore unknown commands or remind about buttons
    if message.text != "/start":
        await message.answer("💡 Все функции теперь доступны через кнопки внизу экрана.", reply_markup=build_reply_kb())

@user_router.message(F.text == "✨ Создать")
async def handle_reply_gen(message: types.Message, state: FSMContext):
    await cmd_gen(message, state)

@user_router.message(F.text == "🤖 Модель")
async def handle_reply_model(message: types.Message, state: FSMContext):
    await cmd_model(message, state)

@user_router.message(F.text == "💳 Баланс")
async def handle_reply_buy(message: types.Message, state: FSMContext):
    await cmd_buy(message, state)

# --- CALLBACK ROUTERS ---
@user_router.callback_query(F.data == "cancel_fsm")
async def process_cancel_fsm(callback_query: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback_query.message.answer(messages.MSG_CANCEL_FSM)
    await callback_query.answer()

@user_router.callback_query(F.data == "gen_similar")
async def process_gen_similar(callback_query: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    prompt = data.get("last_prompt")
    image_urls = data.get("last_image_urls", [])
    last_settings = data.get("last_settings", {})
    
    if not prompt:
         await callback_query.answer("Не удалось найти данные для повтора. Попробуйте создать новую!", show_alert=True)
         return
    
    await callback_query.answer("Запускаю повтор...")
    
    # Extract saved settings if available
    ratio = last_settings.get("aspect_ratio", "1:1")
    res = last_settings.get("resolution", "4K")
    fmt = last_settings.get("output_format", "png")
    
    await start_generation_wrapper(
        callback_query.from_user.id, 
        prompt=prompt, 
        image_urls=image_urls, 
        state=state,
        aspect_ratio=ratio,
        resolution=res,
        output_format=fmt
    )

@user_router.callback_query(F.data == "main_menu")
async def process_main_menu(callback_query: CallbackQuery, state: FSMContext):
    await state.clear()
    async with AsyncSessionLocal() as db:
        user = await services.get_or_create_user(db, callback_query.from_user.id)
        text = generate_model_menu_text(user.balance, user.model_preference)
        await callback_query.message.edit_text(
            text,
            reply_markup=build_main_kb(user.model_preference),
            parse_mode="Markdown"
        )

@user_router.callback_query(F.data == "profile")
async def process_profile(callback_query: CallbackQuery):
    async with AsyncSessionLocal() as db:
        user = await services.get_or_create_user(db, callback_query.from_user.id)
        text = f"👤 <b>Профиль</b>\n\n💳 Баланс: {user.balance} кредитов\n🤖 Модель: {user.model_preference}\n❄️ Заморожено: {user.frozen_balance} кр."
        
        kb = InlineKeyboardBuilder()
        kb.button(text="💳 Купить кредиты", callback_data="buy_credits")
        kb.button(text="⬅️ Назад", callback_data="main_menu")
        kb.adjust(1)
        await callback_query.message.edit_text(text, reply_markup=kb.as_markup(), parse_mode="HTML")

@user_router.callback_query(F.data == "buy_credits")
async def process_buy_credits_cb(callback_query: CallbackQuery):
    packs = get_credit_packs()
    kb = InlineKeyboardBuilder()
    for price, amount in packs.items():
        kb.button(text=f"🍌 {amount} кр. — {price} руб.", callback_data=f"buy:{price}:{amount}")
    kb.button(text="⬅️ Назад", callback_data="profile")
    kb.adjust(1)
    await callback_query.message.edit_text(messages.MSG_BUY_MENU, reply_markup=kb.as_markup())

async def auto_check_payment(user_id: int, payment_id: str, amount: float, msg_id: int, price: int):
    # Poll for 15 minutes max (90 checks * 10 seconds)
    for _ in range(90):
        await asyncio.sleep(10)
        try:
            payment_info = Payment.find_one(payment_id)
            if payment_info.status == 'succeeded':
                async with AsyncSessionLocal() as db:
                    await services.update_user_balance(db, user_id, amount)
                try:
                    await bot.edit_message_text(chat_id=user_id, message_id=msg_id, text=f"✅ Оплата **{price} руб.** прошла успешно! Начислено **{amount} кр.**", parse_mode="Markdown")
                except: pass
                return
            elif payment_info.status == 'canceled':
                break
        except Exception as e:
            logger.error(f"Error checking Yookassa payment: {e}")
            break

@user_router.callback_query(F.data.startswith("buy:"))
async def process_buy_packet(callback_query: CallbackQuery):
    _, price, amount = callback_query.data.split(":")
    
    bot_info = await bot.me()
    payment = Payment.create({
        "amount": {"value": str(price), "currency": "RUB"},
        "confirmation": {"type": "redirect", "return_url": f"https://t.me/{bot_info.username}"},
        "capture": True,
        "description": f"Покупка {amount} кредитов S•NOVA AI"
    }, str(uuid.uuid4()))
    
    kb = InlineKeyboardBuilder()
    kb.button(text="💳 Оплатить", url=payment.confirmation.confirmation_url)
    kb.button(text="🔄 Проверить оплату", callback_data=f"check_pay:{payment.id}:{amount}:{price}")
    kb.adjust(1)
    
    msg = await callback_query.message.edit_text(
        f"⏳ Создан счет на **{price} руб.** для оплаты **{amount} кр.**\n\n"
        f"Оплата подтвердится автоматически, либо нажмите кнопку проверки ниже.",
        reply_markup=kb.as_markup(), parse_mode="Markdown"
    )
    await callback_query.answer()
    
    asyncio.create_task(auto_check_payment(callback_query.from_user.id, payment.id, float(amount), msg.message_id, int(price)))

@user_router.callback_query(F.data.startswith("check_pay:"))
async def process_check_payment(callback_query: CallbackQuery):
    parts = callback_query.data.split(":")
    payment_id = parts[1]
    amount = float(parts[2])
    price = int(parts[3]) if len(parts) > 3 else 0
    
    try:
        payment_info = Payment.find_one(payment_id)
        if payment_info.status == 'succeeded':
            async with AsyncSessionLocal() as db:
                await services.update_user_balance(db, callback_query.from_user.id, amount)
            await callback_query.message.edit_text(f"✅ Оплата **{price} руб.** прошла успешно! Начислено **{amount} кр.**", parse_mode="Markdown")
            await callback_query.answer("Оплата подтверждена!", show_alert=True)
        elif payment_info.status == 'canceled':
            kb = InlineKeyboardBuilder()
            kb.button(text="💬 Написать в тех.поддержку", url="https://t.me/artemgavr1lov")
            await callback_query.message.edit_text(f"❌ Оплата была отменена или не прошла.", reply_markup=kb.as_markup(), parse_mode="Markdown")
            await callback_query.answer("Оплата не прошла", show_alert=True)
        else:
            await callback_query.answer("⏳ Оплата еще не поступила. Подождите немного и попробуйте снова.", show_alert=True)
    except Exception as e:
        logger.error(f"Check payment error: {e}")
        await callback_query.answer("Ошибка проверки. Попробуйте позже.", show_alert=True)

@user_router.callback_query(F.data.startswith("set_model:"))
async def process_set_model(callback_query: CallbackQuery):
    model = callback_query.data.split(":")[1]
    async with AsyncSessionLocal() as db:
        user = await services.get_or_create_user(db, callback_query.from_user.id)
        user.model_preference = model
        await db.commit()
        text = generate_model_menu_text(user.balance, user.model_preference)
        await callback_query.message.edit_text(text, reply_markup=build_main_kb(user.model_preference), parse_mode="Markdown")
        await callback_query.answer(f"Модель успешно обновлена!", show_alert=False)
        
        limit = get_model_limit(user.model_preference)
        await bot.send_message(callback_query.from_user.id, messages.MSG_MODEL_SET_NEXT.format(limit=limit), parse_mode="Markdown", reply_markup=build_reply_kb())

@user_router.callback_query(GenState.confirming, F.data == "settings_menu")
async def process_settings_menu(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    async with AsyncSessionLocal() as db:
        user = await services.get_or_create_user(db, callback.from_user.id)
    
    settings = data.get("gen_settings", {})
    # Set maximum quality defaults for all models: 1:1, 4K, PNG
    if "aspect_ratio" not in settings:
        settings["aspect_ratio"] = "1:1"
    if "resolution" not in settings:
        settings["resolution"] = "4K"
    if "output_format" not in settings:
        settings["output_format"] = "png"
        
    await state.update_data(gen_settings=settings)
    
    try:
        await callback.message.edit_text(
            "⚙️ **Настройки генерации**\n\nВыберите нужные параметры:",
            reply_markup=build_settings_kb(user.model_preference, settings),
            parse_mode="Markdown"
        )
    except:
        await callback.message.edit_caption(
            caption="⚙️ **Настройки генерации**\n\nВыберите нужные параметры:",
            reply_markup=build_settings_kb(user.model_preference, settings),
            parse_mode="Markdown"
        )
    await callback.answer()

@user_router.callback_query(F.data.startswith("set_setting|"))
async def process_change_setting(callback: CallbackQuery, state: FSMContext):
    _, key, value = callback.data.split("|")
    data = await state.get_data()
    settings = data.get("gen_settings", {})
    settings[key] = value
    await state.update_data(gen_settings=settings)
    
    async with AsyncSessionLocal() as db:
        user = await services.get_or_create_user(db, callback.from_user.id)
    
    # Update menu to show new selection
    try:
        await callback.message.edit_reply_markup(reply_markup=build_settings_kb(user.model_preference, settings))
    except: pass
    await callback.answer(f"Выбрано: {value}")

@user_router.callback_query(F.data == "confirm_settings")
async def process_confirm_settings(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    prompt = data.get("confirm_prompt")
    urls = data.get("confirm_image_urls", [])
    is_refine = data.get("is_refinement", False)
    
    # Return to confirmation by EDITING current message instead of deleting/re-sending
    await show_confirmation(callback.from_user.id, prompt, urls, state, is_refine, message=callback.message)
    await callback.answer()

async def show_confirmation(user_id: int, prompt: str | None, image_urls: list, state: FSMContext, is_refinement: bool = False, message: types.Message = None):
    data = await state.get_data()
    async with AsyncSessionLocal() as db:
        user = await services.get_or_create_user(db, user_id)
        model = services.normalize_model_id(user.model_preference)
    
    logger.info(f"show_confirmation: user={user_id}, model={model}, prompt={prompt}, imgs={len(image_urls)}, is_refine={is_refinement}")
    # Save for confirmation

    prompt_str = str(prompt or "")
    await state.update_data(confirm_prompt=prompt_str, confirm_image_urls=image_urls, is_refinement=is_refinement)
    await state.set_state(GenState.confirming)
    
    async with AsyncSessionLocal() as db:
        user = await services.get_or_create_user(db, user_id)
    
    actual_model = user.model_preference
    # Google Nano Banana needs a special 'edit' model ID if photos are present
    if image_urls and (actual_model == "google/nano-banana" or actual_model == "nano-banana"):
        actual_model = "google/nano-banana-edit"
    
    cost = services.get_model_cost(actual_model)
    models_map = get_available_models()
    human_name = next((n for n, m in models_map.items() if m == user.model_preference), user.model_preference)
    
    img_count_text = f"📸 Фото: **{len(image_urls)} шт.**\n" if len(image_urls) > 1 else ""
    header = "🔄 **Доработка результата**" if is_refinement else "✨ **Ваш промпт почти готов!**"
    
    safe_prompt = prompt_str[:200] + ("..." if len(prompt_str) > 200 else "")
    
    settings = data.get("gen_settings", {})
    # Setup defaults for display
    ratio = settings.get("aspect_ratio", "1:1")
    res = settings.get("resolution", "4K")
    fmt = settings.get("output_format", "png")

    text = (
        f"{header}\n\n"
        f"📝 Текст: `{safe_prompt}`\n"
        f"{img_count_text}"
        f"🤖 Модель: **{human_name}**\n"
        f"📐 Размер: **{ratio}** | 💎 **{res}** | 📁 **{fmt.upper()}**\n"
        f"💰 Стоимость: **{int(cost)} кр.**\n\n"
        f"💳 Ваш баланс: **{int(user.balance)} кр.**\n\n"
        f"Всё верно? Начинаем генерацию?"
    )

    if message:
        # Smart Edit: Update existing message if possible to avoid clutter
        if len(image_urls) == 1 and (message.photo or message.caption):
            try:
                await message.edit_caption(caption=text, reply_markup=build_confirm_kb(), parse_mode="Markdown")
                return
            except: pass
        elif not image_urls:
            try:
                await message.edit_text(text, reply_markup=build_confirm_kb(), parse_mode="Markdown")
                return
            except: pass
        
        # Cleanup: If it's a media group (multiple photos), we can't easily edit it
        # to add buttons, so we delete it to avoid duplicates.
        try: await message.delete()
        except: pass

    if image_urls:
        if len(image_urls) > 1:
            media = [InputMediaPhoto(media=url) for url in image_urls]
            await bot.send_media_group(user_id, media=media)
            await bot.send_message(user_id, text, reply_markup=build_confirm_kb(), parse_mode="Markdown")
        else:
            # Single photo case: check if it's a URL (could be heavy 4K to refine)
            photo_source = image_urls[0]
            if str(photo_source).startswith("http"):
                optimized = await get_safe_preview_photo(photo_source)
                if optimized:
                    photo_source = optimized
            
            await bot.send_photo(user_id, photo=photo_source, caption=text, reply_markup=build_confirm_kb(), parse_mode="Markdown")
    else:
        await bot.send_message(user_id, text, reply_markup=build_confirm_kb(), parse_mode="Markdown")

@user_router.callback_query(GenState.confirming, F.data == "confirm_gen")
async def process_confirm_gen(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    prompt = data.get("confirm_prompt")
    image_urls = data.get("confirm_image_urls", [])
    
    final_urls = []
    for item in (image_urls or []):
        if item and not str(item).startswith("http"):
            file = await bot.get_file(item)
            final_urls.append(f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file.file_path}")
        elif item:
            final_urls.append(item)

    # Prepare settings BEFORE clearing state/updating data
    settings = data.get("gen_settings", {})
    
    await state.update_data(last_prompt=prompt, last_image_urls=final_urls, last_settings=settings)
    await state.set_state(None)

    settings = data.get("gen_settings", {})
    async with AsyncSessionLocal() as db:
        user = await services.get_or_create_user(db, callback.from_user.id)
    
    # Global max defaults: 4K, PNG, 1:1
    ratio = settings.get("aspect_ratio", "1:1")
    res = settings.get("resolution", "4K")
    fmt = settings.get("output_format", "png")

    await start_generation_wrapper(
        callback.from_user.id, 
        prompt=prompt, 
        image_urls=final_urls, 
        state=state,
        aspect_ratio=ratio,
        resolution=res,
        output_format=fmt
    )


@user_router.callback_query(F.data == "edit_gen")
async def process_edit_gen(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("Хорошо! Пришлите новый промпт (текст или фото) и мы попробуем еще раз. 👇")


# --- MEDIA GROUP HANDLING ---
@user_router.message(F.media_group_id)
async def handle_media_group(message: types.Message):
    mg_id = message.media_group_id
    if mg_id not in media_groups:
        media_groups[mg_id] = {"messages": []}
        loop = asyncio.get_event_loop()
        media_groups[mg_id]["timer"] = loop.call_later(1.0, asyncio.create_task, process_media_group_delayed(mg_id, message.from_user.id))
    media_groups[mg_id]["messages"].append(message)

async def process_media_group_delayed(mg_id: str, user_id: int):
    data = media_groups.pop(mg_id, None)
    if not data: return
    messages = data["messages"]
    
    async with AsyncSessionLocal() as db:
        user = await services.get_or_create_user(db, user_id)
    limit = get_model_limit(user.model_preference)
    
    if len(messages) > limit:
        await bot.send_message(user_id, f"❌ Ошибка: выбраная модель поддерживает максимум **{limit} фото** в одном запросе. Вы прислали {len(messages)}.")
        return

    # Clear refinement context for new media groups
    state = FSMContext(storage=dp.storage, key=StorageKey(bot_id=bot.id, chat_id=user_id, user_id=user_id))
    await state.update_data(refinement_context_url=None)

    # Collect all images from the group
    image_urls = []
    caption = None
    for m in messages:
        if m.caption:
            caption = m.caption
        if m.photo:
            file_id = m.photo[-1].file_id
            file = await bot.get_file(file_id)
            img_url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file.file_path}"
            # For the UI, we'll store the file_id in image_urls[0] for the confirmation message
            # and the full URL for the backend in a separate list.
            image_urls.append(file_id) # Use file_id for UI

            
    has_caption = bool(caption and str(caption).strip())
    
    if not has_caption:
        # Prompt user for text
        await bot.send_message(user_id, "Введите промпт (описание того, что вы хотите сделать):", reply_markup=build_cancel_kb())
        
        # Inject FSM State
        state = FSMContext(storage=dp.storage, key=StorageKey(bot_id=bot.id, chat_id=user_id, user_id=user_id))
        await state.update_data(queued_images=len(messages), image_urls=image_urls)
        await state.set_state(GenState.waiting_for_prompt)
    else:
        # Instead of starting immediately, show confirmation
        state = FSMContext(storage=dp.storage, key=StorageKey(bot_id=bot.id, chat_id=user_id, user_id=user_id))
        await show_confirmation(user_id, caption, image_urls, state)


@user_router.message(GenState.waiting_for_prompt)
async def handle_prompt_for_media(message: types.Message, state: FSMContext):
    try:
        logger.info(f"handle_prompt_for_media: user={message.from_user.id}, text={message.text}")
        if message.photo or message.media_group_id:
            logger.info("New media detected in waiting_for_prompt, resetting.")
            await state.clear()
            if message.media_group_id:
                return await handle_media_group(message)
            else:
                return await handle_single_prompt(message, state)

        prompt_text = (message.text or message.caption or "").strip()
        data = await state.get_data()
        image_urls = data.get("image_urls") or []
        
        logger.info(f"Retrieved from state: urls_count={len(image_urls)}")

        # Also check if we should fallback to refinement context if state urls are missing
        if not image_urls:
            refinement_url = data.get("refinement_context_url")
            if refinement_url:
                image_urls = [refinement_url]
                logger.info("Falling back to refinement_url in state handler.")

        await show_confirmation(message.from_user.id, prompt_text, image_urls, state)
    except Exception as e:
        logger.error(f"Error in handle_prompt_for_media: {e}", exc_info=True)
        await message.answer(f"❌ Произошла ошибка при обработке: {e}")



# --- SINGLE PHOTO OR TEXT ---
@user_router.message(F.photo | F.text)
async def handle_single_prompt(message: types.Message, state: FSMContext):
    try:
        if message.media_group_id: return
        
        # Check if a single photo was sent without text
        has_caption = bool(message.caption and message.caption.strip())
        if message.photo:
            # Clear previous context if new photo is sent
            await state.update_data(refinement_context_url=None)
            logger.info("New photo detected, cleared refinement context.")
            
            if not has_caption:
                file_id = message.photo[-1].file_id
                # We need the URL for the backend, but we'll use file_id for the UI
                await state.update_data(queued_images=1, image_urls=[file_id])
                await state.set_state(GenState.waiting_for_prompt)
                await message.answer("📸 Фото получено! Теперь введите промпт (описание):", reply_markup=build_cancel_kb())
                return

        prompt = message.text or message.caption or ""
        image_urls = []
        
        data = await state.get_data()
        refinement_url = data.get("refinement_context_url")
        is_refinement = False
        
        logger.info(f"Checking refinement for user {message.from_user.id}: {refinement_url}")

        if message.photo:
            file_id = message.photo[-1].file_id
            image_urls = [file_id]
            logger.info("Using new photo for generation.")

        elif message.text and refinement_url:
            # Auto-inject last result as reference
            image_urls = [refinement_url]
            is_refinement = True
            logger.info(f"Auto-injecting refinement context: {refinement_url}")

            
        await show_confirmation(message.from_user.id, prompt, image_urls, state, is_refinement=is_refinement)
    except Exception as e:
        logger.error(f"Error in handle_single_prompt: {e}", exc_info=True)
        await message.answer(f"❌ Ошибка: не удалось обработать ваш запрос. Попробуйте ещё раз.")

async def start_generation_wrapper(user_id: int, prompt: str, image_urls: list = None, state: FSMContext = None,
                               aspect_ratio: str = "auto", resolution: str = "1K", output_format: str = "jpg"):
    image_urls = image_urls or []
    async with AsyncSessionLocal() as db:
        user = await services.get_or_create_user(db, user_id)
        # Resolve actual model and cost before try block
        actual_model = services.normalize_model_id(user.model_preference)
        
        cost = services.get_model_cost(actual_model)

        try:
            # Pre-charge the user based on the correct model
            await services.pre_charge_generation(db, user, actual_model)

        except ValueError:
            # Insufficient funds exact replica
            text = f"Недостаточно кр. (нужно {int(cost)}, у вас {int(user.balance)}).\nПополните баланс или смените модель: /model"
            
            kb = InlineKeyboardBuilder()
            kb.button(text="💳 Карта РФ(₽)", callback_data="buy_credits")
            kb.button(text="⭐ Telegram Stars", callback_data="buy_credits")
            kb.adjust(1)
            
            await bot.send_message(user_id, text, reply_markup=kb.as_markup())
            return
            
    # Save resolved URLs for "Repeat" functionality to avoid 500 errors
    if state:
        await state.update_data(last_prompt=prompt, last_image_urls=image_urls)

    msg_wait = await bot.send_message(user_id, f"🚀 **Запрос подтвержден!** Начинаю генерацию (**{human_model_name(user.model_preference)}**)...", parse_mode="Markdown")
    asyncio.create_task(run_generation_task(
        user_id, prompt, cost, actual_model, msg_wait.message_id, image_urls, state,
        aspect_ratio, resolution, output_format
    ))

def human_model_name(model_id: str) -> str:
    model_id = services.normalize_model_id(model_id)
    models = get_available_models()
    return next((n for n, m in models.items() if services.normalize_model_id(m) == model_id), model_id)

async def get_safe_preview_photo(url: str) -> types.BufferedInputFile | None:
    """Download image and optimize if it exceeds 10MB to ensure Telegram can send it as a photo."""
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, timeout=30.0)
            if resp.status_code != 200:
                logger.warning(f"Failed to download image from {url}: {resp.status_code}")
                return None
            
            data = resp.content
            size_mb = len(data) / (1024 * 1024)
            
            # If it's already small enough, no need to process
            if size_mb < 9.5:
                return types.BufferedInputFile(data, filename="preview.png")

            logger.info(f"Optimizing large image: {size_mb:.2f} MB")
            with Image.open(io.BytesIO(data)) as img:
                # If it's CMYK or similar, convert to RGB for web
                if img.mode != 'RGB':
                    img = img.convert('RGB')
                
                # 1. Try to save with optimization
                buf = io.BytesIO()
                img.save(buf, format="PNG", optimize=True)
                if len(buf.getvalue()) < 10000000:
                    buf.seek(0)
                    return types.BufferedInputFile(buf.getvalue(), filename="preview_opt.png")

                # 2. Still too large? Use Quantization (Indexed palette)
                buf = io.BytesIO()
                # 256 colors often reduces size by 4x
                quantized = img.quantize(colors=256).convert('P')
                quantized.save(buf, format="PNG", optimize=True)
                if len(buf.getvalue()) < 10000000:
                    buf.seek(0)
                    return types.BufferedInputFile(buf.getvalue(), filename="preview_quant.png")

                # 3. Last fallback: High-quality JPEG
                buf = io.BytesIO()
                img.save(buf, format="JPEG", quality=90, optimize=True)
                buf.seek(0)
                return types.BufferedInputFile(buf.getvalue(), filename="preview_fallback.jpg")

    except Exception as e:
        logger.error(f"Error in get_safe_preview_photo: {e}", exc_info=True)
        return None

async def run_generation_task(user_id: int, prompt: str, cost: float, model: str, msg_id: int, image_urls: list[str], state: FSMContext = None,
                          aspect_ratio: str = "auto", resolution: str = "1K", output_format: str = "jpg"):
    kie_task_id = None
    try:
        # 1. Start Flow (Short DB session)
        async with AsyncSessionLocal() as db:
            kie_task_id = await services.start_generation_flow(
                db, user_id, prompt, image_urls, model, cost, 
                aspect_ratio, resolution, output_format
            )
            
        # 2. Wait Loop (No DB session)
        last_log_state = None
        for i in range(120): # 120 * 5s = 600s (10 mins)
            await asyncio.sleep(5)
            info = await services.check_generation_status(kie_task_id)
            kie_status = info.get("state")
            
            if kie_status != last_log_state:
                logger.info(f"Task {kie_task_id} status change: {last_log_state} -> {kie_status}")
                last_log_state = kie_status

            if kie_status in ["success", "completed"] and info.get("image_url"):
                # 1. Update state FIRST
                if state:
                    await state.update_data(refinement_context_url=info.get("image_url"))

                # 2. Finalize credits
                async with AsyncSessionLocal() as db:
                    await services.commit_frozen_credits(db, user_id, cost)
                    user = await services.get_or_create_user(db, user_id)
                    new_balance = int(user.balance)

                models_map = get_available_models()
                human_name = next((n for n, m in models_map.items() if services.normalize_model_id(m) == model), model)
                
                # 3. Delivery Strategy
                photo_sent = False
                try:
                    photo_data = await get_safe_preview_photo(info["image_url"])
                    if photo_data:
                        caption = messages.MSG_GEN_SUCCESS_WITH_BALANCE.format(balance=new_balance, model_name=human_name)
                        await bot.send_photo(user_id, photo=photo_data, caption=caption, reply_markup=build_after_gen_kb(), parse_mode="Markdown")
                        photo_sent = True
                    
                    await bot.send_document(user_id, document=URLInputFile(info["image_url"], filename=f"gen_{kie_task_id[:8]}.png"), caption="💾 Оригинал (PNG/4K)")
                except Exception as e:
                    logger.warning(f"Delivery failed: {e}")
                    if not photo_sent:
                        fallback_caption = messages.MSG_GEN_SUCCESS_FALLBACK.format(balance=new_balance)
                        await bot.send_document(user_id, document=URLInputFile(info["image_url"], filename=f"gen_{kie_task_id[:8]}.png"), 
                                               caption=fallback_caption, parse_mode="Markdown", reply_markup=build_after_gen_kb())
                
                try: await bot.delete_message(user_id, msg_id)
                except: pass
                return
                
            elif kie_status in ["failed", "error", "cancelled"]:
                err_text = info.get("error", f"KIE reported state: {kie_status}")
                raise Exception(err_text)
                
        raise Exception("Превышено время ожидания генерации.")
        
    except Exception as e:
        logger.error(f"Generation task error: {e}", exc_info=True)
        # Refund (Short DB session)
        async with AsyncSessionLocal() as db:
            await services.refund_frozen_credits(db, user_id, cost)
            
        await bot.send_message(user_id, f"❌ Ошибка генерации: {e}")
        try: await bot.delete_message(user_id, msg_id)
        except: pass



async def on_startup():
    await setup_bot_commands(bot)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    async with AsyncSessionLocal() as db:
        await services.fix_all_model_ids(db)

async def main():
    await on_startup()
    await dp.start_polling(bot)

if __name__ == "__main__":
    if not BOT_TOKEN or BOT_TOKEN == "YOUR_TELEGRAM_BOT_TOKEN_HERE":
        logger.error("Please configure BOT_TOKEN properly in .env.")
    else:
        asyncio.run(main())
