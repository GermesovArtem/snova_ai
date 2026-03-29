import asyncio
import logging
import os
print("\n" + "!"*50)
print("!!! BOT MAIN.PY: VERSION 7.0 (PRO OPTIMIZATION) !!!")
print("!"*50 + "\n")


import json
from aiogram import Bot, Dispatcher, types, F, Router
from aiogram.filters import CommandStart, Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, BotCommand, URLInputFile
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.storage.base import StorageKey
from dotenv import load_dotenv

from backend.database import get_db, AsyncSessionLocal, engine, Base
from backend import services

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

from bot.admin import admin_router
user_router = Router()
dp.include_router(admin_router)
dp.include_router(user_router)

media_groups = {} # media_group_id -> { "messages": [], "timer": asyncio.Task }

class GenState(StatesGroup):
    waiting_for_prompt = State()
    confirming = State()

def get_available_models():
    models_str = os.getenv("AVAILABLE_MODELS", '{"NanoBanana 2": "nano-banana-2", "NanoBanana PRO": "nano-banana-pro"}')
    try:
        return json.loads(models_str)
    except:
        return {"NanoBanana 2": "nano-banana-2", "NanoBanana PRO": "nano-banana-pro"}


def get_model_costs():
    costs_str = os.getenv("CREDITS_PER_MODEL", '{"nano-banana-2": 3.0, "nano-banana-pro": 4.0}')
    try:
        return json.loads(costs_str)
    except:
        return {"nano-banana-2": 3.0, "nano-banana-pro": 4.0}


def get_credit_packs():
    packs_str = os.getenv("CREDIT_PACKS", '{"149": 10}')
    try:
        return json.loads(packs_str)
    except:
        return {"149": 10}

def generate_model_menu_text(balance: float, current_mm: str):
    models = get_available_models()
    human_name = next((name for name, mm in models.items() if mm == current_mm), current_mm)
    
    return (
        f"🤖 **Управление нейросетями**\n\n"
        f"Активная ИИ-модель: **{human_name}**\n\n"
        f"🆕 **Nano Banana 2** (Продвинутая)\n"
        f"• Стоимость: **3 генерации**\n"
        f"• Разрешение: Ультра-высокое (4K)\n"
        f"• Понимает современные тренды и мемы\n"
        f"• Поддерживает несколько картинок-референсов\n"
        f"• Идеально для дизайна соцсетей и стильных артов\n\n"
        f"**Pro** (Профессиональная)\n"
        f"• Стоимость: **4 генерации**\n"
        f"• Разрешение: Максимальное (4K+)\n"
        f"• Безупречная прорисовка мельчайших деталей\n"
        f"• Идеально ровно пишет текст на картинках\n"
        f"• Лучший выбор для сложного фотореализма\n\n"
        f"💰 На вашем счете: **{int(balance)} генераций**"
    )


def build_main_kb(current_model: str):
    kb = InlineKeyboardBuilder()
    models = get_available_models()
    costs = get_model_costs()
    for name, mm in models.items():
        cost = int(costs.get(mm, 1))
        prefix = "✅ " if mm == current_model else ("🆕 " if "2" in name else "")
        kb.button(text=f"{prefix}{name} ({cost} ген)", callback_data=f"set_model:{mm}")
    
    kb.adjust(1)
    return kb.as_markup()

def build_start_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="👉 Выбрать модель", callback_data="main_menu")
    return kb.as_markup()

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
    kb.button(text="✏️ Изменить", callback_data="edit_gen")
    kb.adjust(1)
    return kb.as_markup()

async def setup_bot_commands(bot: Bot):
    commands = [
        BotCommand(command="gen", description="🎨 Редактировать фото"),
        BotCommand(command="create", description="✨ Создать изображение"),
        BotCommand(command="model", description="🤖 Выбор модели"),
        BotCommand(command="buy", description="💳 Пополнить баланс"),
        BotCommand(command="example", description="💡 Примеры промптов"),
        BotCommand(command="bots", description="🤖 Наши боты"),
        BotCommand(command="friend", description="👥 Реферальная программа"),
        BotCommand(command="help", description="❓ Помощь"),
    ]
    await bot.set_my_commands(commands)

@user_router.message(CommandStart())
async def cmd_start(message: types.Message, state: FSMContext):
    await state.clear()
    async with AsyncSessionLocal() as db:
        user = await services.get_or_create_user(db, message.from_user.id, message.from_user.username)
        
        text = (
            f"🍌 **Добро пожаловать в S•NOVA AI**\n"
            f"— Ai фотошоп от Google в удобном телеграм-боте:\n\n"
            f"🎁 У вас есть **{int(user.balance)} бесплатных генераций**\n\n"
            f"**Доступные модели:**\n"
            f"• 🆕 Nano Banana 2 — 3 кредита, 4K\n"
            f"• Pro — 4 кредита, 4K, максимальное качество\n\n"

            f"Нажмите «Выбрать модель» чтобы начать 👇\n\n"
            f"Пользуясь ботом, Вы принимаете наше пользовательское соглашение и политику конфиденциальности."
        )
        
        await message.answer(text, reply_markup=build_start_kb(), parse_mode="Markdown")
        await asyncio.sleep(0.5)
        await message.answer("Пришлите 1-4 фотографии которые нужно изменить или объединить")

# --- NATIVE MENU COMMANDS ---
@user_router.message(Command("model"))
async def cmd_model(message: types.Message, state: FSMContext):
    await state.clear()
    async with AsyncSessionLocal() as db:
        user = await services.get_or_create_user(db, message.from_user.id)
        text = generate_model_menu_text(user.balance, user.model_preference)
        await message.answer(text, reply_markup=build_main_kb(user.model_preference), parse_mode="Markdown")

@user_router.message(Command("buy"))
async def cmd_buy(message: types.Message, state: FSMContext):
    await state.clear()
    packs = get_credit_packs()
    kb = InlineKeyboardBuilder()
    for price, amount in packs.items():
        kb.button(text=f"🍌 {amount} кр. — {price} руб.", callback_data=f"buy:{price}:{amount}")
    kb.button(text="⬅️ Назад", callback_data="main_menu")
    kb.adjust(1)
    await message.answer("Выберите пакет кредитов для пополнения (оплата ЮKassa):", reply_markup=kb.as_markup())

@user_router.message(Command("gen"))
async def cmd_gen(message: types.Message, state: FSMContext):
    await message.answer("Пришлите 1-4 фотографии которые нужно изменить или объединить")

@user_router.message(Command("create"))
async def cmd_create(message: types.Message, state: FSMContext):
    await state.set_state(GenState.waiting_for_prompt)
    await message.answer("Введите промпт (что изменить) или продиктуйте голосом:", reply_markup=build_cancel_kb())

@user_router.message(Command("help"))
async def cmd_help(message: types.Message):
    await message.answer("💡 Помощь\nПросто отправьте мне фото или текст, и я сгенерирую результат на основе выбранной вами нейросети!")

@user_router.message(Command("bots"))
@user_router.message(Command("example"))
@user_router.message(Command("friend"))
async def cmd_dummies(message: types.Message):
    await message.answer("Этот раздел находится в разработке 🏗")

# --- CALLBACK ROUTERS ---
@user_router.callback_query(F.data == "cancel_fsm")
async def process_cancel_fsm(callback_query: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback_query.message.answer("Ок! Жду ваши фото или текст для новой идеи. 😉")
    await callback_query.answer()

@user_router.callback_query(F.data == "gen_similar")
async def process_gen_similar(callback_query: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    prompt = data.get("last_prompt")
    image_urls = data.get("last_image_urls", [])
    if not prompt:
         await callback_query.answer("Не удалось найти данные для повтора. Попробуйте создать новую!", show_alert=True)
         return
    await callback_query.answer("Запускаю повтор...")
    await start_generation_wrapper(callback_query.from_user.id, prompt=prompt, image_urls=image_urls)

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
    await callback_query.message.edit_text("Выберите пакет кредитов для пополнения (оплата ЮKassa):", reply_markup=kb.as_markup())

@user_router.callback_query(F.data.startswith("buy:"))
async def process_buy_packet(callback_query: CallbackQuery):
    _, price, amount = callback_query.data.split(":")
    await callback_query.answer(f"Создан счет на {price} руб. (имитация)", show_alert=True)

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
        await bot.send_message(callback_query.from_user.id, "Отлично! Теперь пришлите фото или введите текст.")

async def show_confirmation(user_id: int, prompt: str | None, image_urls: list, state: FSMContext, is_refinement: bool = False):
    data = await state.get_data()
    async with AsyncSessionLocal() as db:
        user = await services.get_or_create_user(db, user_id)
        model = user.model_preference
    
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
    
    text = (
        f"{header}\n\n"
        f"📝 Текст: `{safe_prompt}`\n"
        f"{img_count_text}"
        f"🤖 Модель: **{human_name}**\n"
        f"💰 Стоимость: **{int(cost)} ген.**\n\n"
        f"💳 Ваш баланс: **{int(user.balance)} ген.**\n\n"
        f"Всё верно? Начинаем генерацию?"
    )


    
    if image_urls:
        # Use first image_urls entry as photo. 
        # Crucial: if it's a file_id, Telegram sends it instantly. if it's a URL, it fetches.
        await bot.send_photo(
            user_id, 
            photo=image_urls[0], 
            caption=text, 
            reply_markup=build_confirm_kb(), 
            parse_mode="Markdown"
        )

    else:
        await bot.send_message(
            user_id, 
            text, 
            reply_markup=build_confirm_kb(), 
            parse_mode="Markdown"
        )

@user_router.callback_query(GenState.confirming, F.data == "confirm_gen")
async def process_confirm_gen(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    prompt = data.get("confirm_prompt")
    image_urls = data.get("confirm_image_urls", [])
    
    # Save for "Similar"
    await state.update_data(last_prompt=prompt, last_image_urls=image_urls)
    await state.set_state(None)
    
    try:
        if callback.message.photo or callback.message.caption:
            await callback.message.edit_caption(caption="🚀 Запрос подтвержден! Начинаю генерацию...", reply_markup=None)
        else:
            await callback.message.edit_text("🚀 Запрос подтвержден! Начинаю генерацию...", reply_markup=None)
    except Exception as e:
        logger.warning(f"Could not edit confirmation message (using fallback): {e}")
        try:
            await callback.message.answer("🚀 Запрос подтвержден! Начинаю генерацию...")
            await callback.message.delete()
        except: pass


    
    # Pre-process image_urls: convert file_ids to URLs before sending to wrapper
    final_urls = []
    for item in (image_urls or []):
        if item and not str(item).startswith("http"):
            # It's a file_id! Get URL
            file = await bot.get_file(item)
            final_urls.append(f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file.file_path}")
        elif item:
            final_urls.append(item)


    await start_generation_wrapper(callback.from_user.id, prompt=prompt, image_urls=final_urls, state=state)


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
    if message.media_group_id: return
    
    # Check if a single photo was sent without text
    has_caption = bool(message.caption and message.caption.strip())
    if message.photo and not has_caption:
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
        # Clear previous context if new photo is sent
        await state.update_data(refinement_context_url=None)
        logger.info("New photo sent, cleared refinement context.")

    elif message.text and refinement_url:
        # Auto-inject last result as reference
        image_urls = [refinement_url]
        is_refinement = True
        logger.info(f"Auto-injecting refinement context: {refinement_url}")

        
    await show_confirmation(message.from_user.id, prompt, image_urls, state, is_refinement=is_refinement)

async def start_generation_wrapper(user_id: int, prompt: str, image_urls: list = None, state: FSMContext = None):
    image_urls = image_urls or []
    async with AsyncSessionLocal() as db:
        user = await services.get_or_create_user(db, user_id)
        # Resolve actual model and cost before try block to avoid UnboundLocalError
        actual_model = user.model_preference
        
        cost = services.get_model_cost(actual_model)

        try:
            # Pre-charge the user based on the correct model
            await services.pre_charge_generation(db, user, actual_model)

        except ValueError:
            # Insufficient funds exact replica
            text = f"Недостаточно генераций (нужно {int(cost)}, у вас {int(user.balance)}).\nПополните баланс или смените модель: /model"
            
            kb = InlineKeyboardBuilder()
            kb.button(text="💳 Карта РФ(₽)", callback_data="buy_credits")
            kb.button(text="⭐ Звёзды", callback_data="buy_credits")
            kb.adjust(1)
            
            await bot.send_message(user_id, text, reply_markup=kb.as_markup())
            return
            
    msg_wait = await bot.send_message(user_id, f"⏳ Начинаю генерацию (Модель: {user.model_preference})...")
    asyncio.create_task(run_generation_task(user_id, prompt, cost, actual_model, msg_wait.message_id, image_urls, state))

async def run_generation_task(user_id: int, prompt: str, cost: float, model: str, msg_id: int, image_urls: list[str], state: FSMContext = None):
    kie_task_id = None
    try:
        # 1. Start Flow (Short DB session)
        async with AsyncSessionLocal() as db:
            kie_task_id = await services.start_generation_flow(db, user_id, prompt, image_urls, model, cost)
            
        # 2. Wait Loop (No DB session)
        for _ in range(60): # 60 * 4s = 240s
            await asyncio.sleep(4)
            info = await services.check_generation_status(kie_task_id)
            kie_status = info.get("state")
            
            if kie_status in ["success", "completed"] and info.get("image_url"):
                # Success Logic (Short DB session for commit)
                async with AsyncSessionLocal() as db:
                    await services.commit_frozen_credits(db, user_id, cost)
                    user = await services.get_or_create_user(db, user_id)
                    new_balance = int(user.balance)

                models = get_available_models()
                human_name = next((n for n, m in models.items() if m == model), model)
                
                # 1. Send as high-res document
                file_caption = f"💾 **Оригинал в высоком качестве**\n💳 Остаток баланса: **{new_balance} ген.**\n\nТекущая модель: {human_name}"
                await bot.send_document(
                    user_id, 
                    document=URLInputFile(info["image_url"], filename=f"image_{kie_task_id[:8]}.png"),
                    caption=file_caption,
                    parse_mode="Markdown"
                )
                
                # 2. Send photo preview with inline keyboard
                await bot.send_photo(
                    user_id, 
                    photo=URLInputFile(info["image_url"]),
                    caption="🔥 **Готово!** Как вам результат?\nЕсли хотите что-то изменить, напишите в чат ниже. 👇",
                    reply_markup=build_after_gen_kb(),
                    parse_mode="Markdown"
                )
                
                # Store in refinement context
                if state:
                    await state.update_data(refinement_context_url=info["image_url"])

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

async def main():
    await on_startup()
    await dp.start_polling(bot)

if __name__ == "__main__":
    if not BOT_TOKEN or BOT_TOKEN == "YOUR_TELEGRAM_BOT_TOKEN_HERE":
        logger.error("Please configure BOT_TOKEN properly in .env.")
    else:
        asyncio.run(main())
