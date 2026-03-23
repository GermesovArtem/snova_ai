import asyncio
import logging
import os
print("\n" + "!"*50)
print("!!! BOT MAIN.PY: VERSION 5.0 (ADMIN FIX) !!!")
print("!"*50 + "\n")
import json
from aiogram import Bot, Dispatcher, types, F
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
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())
logger = logging.getLogger(__name__)

from bot.admin import admin_router
dp.include_router(admin_router)

media_groups = {} # media_group_id -> { "messages": [], "timer": asyncio.Task }

class GenState(StatesGroup):
    waiting_for_prompt = State()

def get_available_models():
    models_str = os.getenv("AVAILABLE_MODELS", '{"NanoBanana": "google/nano-banana", "NanoBanana 2": "nano-banana-2", "NanoBanana PRO": "nano-banana-pro"}')
    try:
        return json.loads(models_str)
    except:
        return {"NanoBanana": "nano-banana", "NanoBanana 2": "nano-banana-2", "NanoBanana PRO": "nano-banana-pro"}

def get_model_costs():
    costs_str = os.getenv("CREDITS_PER_MODEL", '{"nano-banana": 1.0, "nano-banana-2": 3.0, "nano-banana-pro": 4.0}')
    try:
        return json.loads(costs_str)
    except:
        return {"nano-banana": 1.0, "nano-banana-2": 3.0, "nano-banana-pro": 4.0}

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
        f"**Standard** (Базовая версия)\n"
        f"• Стоимость: **1 генерация**\n"
        f"• Качество: Отличное базовое\n"
        f"• Скорость: Моментальная\n\n"
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
    kb.button(text="🔄 Сгенерировать похожее", callback_data="gen_similar")
    kb.button(text="1️⃣ Начать с 1-го фото", callback_data="gen_first")
    kb.button(text="🖼 Начать заново", callback_data="cancel_fsm")
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

@dp.message(CommandStart())
async def cmd_start(message: types.Message, state: FSMContext):
    await state.clear()
    async with AsyncSessionLocal() as db:
        user = await services.get_or_create_user(db, message.from_user.id, message.from_user.username)
        
        text = (
            f"🍌 **Добро пожаловать в S•NOVA AI**\n"
            f"— Ai фотошоп от Google в удобном телеграм-боте:\n\n"
            f"🎁 У вас есть **{int(user.balance)} бесплатных генераций**\n\n"
            f"**Доступные модели:**\n"
            f"• Standard — 1 кредит, быстрая генерация\n"
            f"• 🆕 Nano Banana 2 — 3 кредита, 4K, знает актуальные события\n"
            f"• Pro — 4 кредита, 4K, максимальное качество\n\n"
            f"Нажмите «Выбрать модель» чтобы начать 👇\n\n"
            f"Пользуясь ботом, Вы принимаете наше пользовательское соглашение и политику конфиденциальности."
        )
        
        await message.answer(text, reply_markup=build_start_kb(), parse_mode="Markdown")
        await asyncio.sleep(0.5)
        await message.answer("Пришлите 1-4 фотографии которые нужно изменить или объединить")

# --- NATIVE MENU COMMANDS ---
@dp.message(Command("model"))
async def cmd_model(message: types.Message, state: FSMContext):
    await state.clear()
    async with AsyncSessionLocal() as db:
        user = await services.get_or_create_user(db, message.from_user.id)
        text = generate_model_menu_text(user.balance, user.model_preference)
        await message.answer(text, reply_markup=build_main_kb(user.model_preference), parse_mode="Markdown")

@dp.message(Command("buy"))
async def cmd_buy(message: types.Message, state: FSMContext):
    await state.clear()
    packs = get_credit_packs()
    kb = InlineKeyboardBuilder()
    for price, amount in packs.items():
        kb.button(text=f"🍌 {amount} кр. — {price} руб.", callback_data=f"buy:{price}:{amount}")
    kb.button(text="⬅️ Назад", callback_data="main_menu")
    kb.adjust(1)
    await message.answer("Выберите пакет кредитов для пополнения (оплата ЮKassa):", reply_markup=kb.as_markup())

@dp.message(Command("gen"))
async def cmd_gen(message: types.Message, state: FSMContext):
    await message.answer("Пришлите 1-4 фотографии которые нужно изменить или объединить")

@dp.message(Command("create"))
async def cmd_create(message: types.Message, state: FSMContext):
    await state.set_state(GenState.waiting_for_prompt)
    await message.answer("Введите промпт (что изменить) или продиктуйте голосом:", reply_markup=build_cancel_kb())

@dp.message(Command("help"))
async def cmd_help(message: types.Message):
    await message.answer("💡 Помощь\nПросто отправьте мне фото или текст, и я сгенерирую результат на основе выбранной вами нейросети!")

@dp.message(Command("bots"))
@dp.message(Command("example"))
@dp.message(Command("friend"))
async def cmd_dummies(message: types.Message):
    await message.answer("Этот раздел находится в разработке 🏗")

# --- CALLBACK ROUTERS ---
@dp.callback_query(F.data == "cancel_fsm")
async def process_cancel_fsm(callback_query: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback_query.message.edit_text("Действие отменено.")
    await callback_query.message.answer("Пришлите 1-4 фотографии которые нужно изменить или объединить")

@dp.callback_query(F.data == "gen_similar")
@dp.callback_query(F.data == "gen_first")
async def process_gen_dummies(callback_query: CallbackQuery):
    await callback_query.answer("Эта функция скоро появится!", show_alert=True)

@dp.callback_query(F.data == "main_menu")
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

@dp.callback_query(F.data == "profile")
async def process_profile(callback_query: CallbackQuery):
    async with AsyncSessionLocal() as db:
        user = await services.get_or_create_user(db, callback_query.from_user.id)
        text = f"👤 <b>Профиль</b>\n\n💳 Баланс: {user.balance} кредитов\n🤖 Модель: {user.model_preference}\n❄️ Заморожено: {user.frozen_balance} кр."
        
        kb = InlineKeyboardBuilder()
        kb.button(text="💳 Купить кредиты", callback_data="buy_credits")
        kb.button(text="⬅️ Назад", callback_data="main_menu")
        kb.adjust(1)
        await callback_query.message.edit_text(text, reply_markup=kb.as_markup(), parse_mode="HTML")

@dp.callback_query(F.data == "buy_credits")
async def process_buy_credits_cb(callback_query: CallbackQuery):
    packs = get_credit_packs()
    kb = InlineKeyboardBuilder()
    for price, amount in packs.items():
        kb.button(text=f"🍌 {amount} кр. — {price} руб.", callback_data=f"buy:{price}:{amount}")
    kb.button(text="⬅️ Назад", callback_data="profile")
    kb.adjust(1)
    await callback_query.message.edit_text("Выберите пакет кредитов для пополнения (оплата ЮKassa):", reply_markup=kb.as_markup())

@dp.callback_query(F.data.startswith("buy:"))
async def process_buy_packet(callback_query: CallbackQuery):
    _, price, amount = callback_query.data.split(":")
    await callback_query.answer(f"Создан счет на {price} руб. (имитация)", show_alert=True)

@dp.callback_query(F.data.startswith("set_model:"))
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

# --- MEDIA GROUP HANDLING ---
@dp.message(F.media_group_id)
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
            image_urls.append(f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file.file_path}")
            
    if not caption:
        # Prompt user for text
        await bot.send_message(user_id, "Введите промпт (описание того, что вы хотите сделать):", reply_markup=build_cancel_kb())
        
        # Inject FSM State
        state = FSMContext(storage=dp.storage, key=StorageKey(bot_id=bot.id, chat_id=user_id, user_id=user_id))
        await state.update_data(queued_images=len(messages), image_urls=image_urls)
        await state.set_state(GenState.waiting_for_prompt)
    else:
        await start_generation_wrapper(user_id, prompt=caption, image_urls=image_urls)

@dp.message(GenState.waiting_for_prompt)
async def handle_prompt_for_media(message: types.Message, state: FSMContext):
    prompt_text = message.text or ""
    data = await state.get_data()
    image_urls = data.get("image_urls", [])
    
    await state.clear()
    await start_generation_wrapper(message.from_user.id, prompt=prompt_text, image_urls=image_urls)

# --- SINGLE PHOTO OR TEXT ---
@dp.message(F.photo | F.text)
async def handle_single_prompt(message: types.Message, state: FSMContext):
    if message.media_group_id: return
    
    # Check if a single photo was sent without text
    if message.photo and not message.caption:
        await state.update_data(queued_images=1)
        await state.set_state(GenState.waiting_for_prompt)
        await message.answer("Введите промпт (описание того, что вы хотите изменить):", reply_markup=build_cancel_kb())
        return

    prompt = message.text or message.caption or ""
    image_urls = []
    if message.photo:
        file_id = message.photo[-1].file_id
        file = await bot.get_file(file_id)
        image_urls = [f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file.file_path}"]
        
    await start_generation_wrapper(message.from_user.id, prompt=prompt, image_urls=image_urls)

async def start_generation_wrapper(user_id: int, prompt: str, image_urls: list[str] = None):
    image_urls = image_urls or []
    async with AsyncSessionLocal() as db:
        user = await services.get_or_create_user(db, user_id)
        try:
            # Check and select correct model context
            actual_model = user.model_preference
            if image_urls and actual_model == "google/nano-banana":
                actual_model = "google/nano-banana-edit"

            # Pre-charge the user based on the correct model
            cost = await services.pre_charge_generation(db, user, actual_model)
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
    asyncio.create_task(run_generation_task(user_id, prompt, cost, actual_model, msg_wait.message_id, image_urls))

async def run_generation_task(user_id: int, prompt: str, cost: float, model: str, msg_id: int, image_urls: list[str]):
    try:
        async with AsyncSessionLocal() as db:
            user = await services.get_or_create_user(db, user_id) # Re-fetch user to ensure latest balance/model
            
            # The cost has already been deducted in start_generation_wrapper, so we just start the task
            kie_task_id = await services.start_generation_flow(db, user_id, prompt, image_urls, model, cost)
            
        for _ in range(30):
            await asyncio.sleep(2)
            info = await services.check_generation_status(kie_task_id)
            state = info.get("state")
            if state in ["success", "completed"] and info.get("image_url"):
                
                models = get_available_models()
                human_name = next((n for n, m in models.items() if m == model), model)
                
                # 1. Send as high-res document
                file_caption = f"Скачать файлом — качество будет лучше, чем при просмотре здесь\n\nТекущая модель: {human_name}"
                await bot.send_document(
                    user_id, 
                    document=URLInputFile(info["image_url"], filename=f"image_{kie_task_id[:8]}.png"),
                    caption=file_caption
                )
                
                # 2. Send photo preview with inline keyboard
                await bot.send_photo(
                    user_id, 
                    photo=URLInputFile(info["image_url"]),
                    caption="Если хотите что-то изменить или добавить напишите в чат ⬇️",
                    reply_markup=build_after_gen_kb()
                )
                
                await bot.delete_message(user_id, msg_id)
                
                async with AsyncSessionLocal() as db:
                    await services.commit_frozen_credits(db, user_id, cost)
                return
            elif state in ["failed", "error"]:
                err_text = info.get("error", "KIE server processing failed")
                raise Exception(err_text)
                
        raise Exception("Timeout limit reached")
    except Exception as e:
        logger.error(f"Gen error: {e}")
        await bot.edit_message_text(f"❌ Ошибка генерации: {e}", chat_id=user_id, message_id=msg_id)
        # Rollback
        async with AsyncSessionLocal() as db:
            await services.refund_frozen_credits(db, user_id, cost)

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
