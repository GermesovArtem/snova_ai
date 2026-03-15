import os
import asyncio
import logging
from dotenv import load_dotenv
from deep_translator import GoogleTranslator
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, CommandObject
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import LabeledPrice, PreCheckoutQuery, URLInputFile
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from bot.api_client import get_or_create_user, get_balance, generate_image, get_referral_stats, create_payment_link

load_dotenv()

API_TOKEN = os.getenv("BOT_TOKEN")
SHOP_ID = os.getenv("SHOP_ID", "dummy")
SECRET_KEY = os.getenv("SECRET_KEY", "dummy")

# Идеально получать из БД (Settings), но пока оставляем кэш
COSTS = {
    "NanoBanana": int(os.getenv("COST_NANOBANANA", 5)),
    "NanoBanana PRO": int(os.getenv("COST_NANOBANANA_PRO", 20))
}

MODEL_ENDPOINTS = {
    "NanoBanana": "nano-banana",
    "NanoBanana PRO": "nano-banana-pro"
}

class GenStates(StatesGroup):
    awaiting_content = State()
    confirm_screen = State()

bot = Bot(token=API_TOKEN)
dp = Dispatcher()

async def get_current_model(state: FSMContext) -> str:
    data = await state.get_data()
    return data.get("current_model", "NanoBanana")

async def main_kb(user_id: int):
    bal = await get_balance(user_id)
    builder = InlineKeyboardBuilder()
    builder.row(types.InlineKeyboardButton(text="🎨 Сгенерировать", callback_data="start_gen"))
    builder.row(types.InlineKeyboardButton(text=f"👛 Баланс: {bal} 🪙", callback_data="add_funds"))
    builder.row(types.InlineKeyboardButton(text="💰 Пригласи друга", callback_data="partners"))
    return builder.as_markup()

# --- ФАЗА 1: Authentication & Landing ---
@dp.message(Command("start"))
async def start(message: types.Message, command: CommandObject, state: FSMContext):
    referrer_id = None
    if command.args and command.args.startswith("r-"):
        referrer_id = command.args.replace("r-", "")

    await get_or_create_user(message.from_user.id, message.from_user.username, referrer_id)
    await state.clear()
    
    await message.answer(
        "👋 **Добро пожаловать в NanoBanana AI**\n\nСоздавайте потрясающие изображения за секунды!\nНажимая `[Сгенерировать]`, вы соглашаетесь с правилами сервиса.", 
        reply_markup=await main_kb(message.from_user.id), 
        parse_mode="Markdown"
    )

@dp.callback_query(F.data == "start_gen")
async def start_generation_flow(call: types.CallbackQuery, state: FSMContext):
    await state.set_state(GenStates.awaiting_content)
    await call.message.edit_text(
        "Отправьте мне текст (промпт) или фото (как референс) 🌠",
        reply_markup=InlineKeyboardBuilder().row(types.InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")).as_markup()
    )

@dp.callback_query(F.data == "cancel")
async def cancel_flow(call: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await call.message.edit_text(
        "Действие отменено.", 
        reply_markup=await main_kb(call.from_user.id)
    )

# --- ФАЗА 2: Request Handling ---
@dp.message(GenStates.awaiting_content)
async def process_content(message: types.Message, state: FSMContext):
    # Обрабатываем текст или фото (упрощенно пока только текст, фото можно добавить как опцию)
    if message.photo:
        prompt = message.caption or "Фото референс"
        # Заглушка: сохранить file_id для img2img, но мы используем text2img API от Kie
        await state.update_data(prompt=prompt, img_ref=message.photo[-1].file_id)
    elif message.text:
        prompt = message.text
        await state.update_data(prompt=prompt)
    else:
        return await message.answer("Пожалуйста, отправьте текст или фото.")

    await state.set_state(GenStates.confirm_screen)
    
    bal = await get_balance(message.from_user.id)
    mod = await get_current_model(state)
    
    builder = InlineKeyboardBuilder()
    builder.row(types.InlineKeyboardButton(text=f"✅ Сделать фото — {COSTS['NanoBanana']} кр", callback_data="gen_NanoBanana"))
    builder.row(types.InlineKeyboardButton(text=f"🔥 NanoBanana PRO — {COSTS['NanoBanana PRO']} кр", callback_data="gen_NanoBanana PRO"))
    builder.row(types.InlineKeyboardButton(text="❌ Отменить", callback_data="cancel"))
    
    await message.answer(
        f"**Готово к генерации!**\n\nМодель: {mod}\nПромпт: {prompt}\nВаш баланс: {bal} 🪙",
        reply_markup=builder.as_markup(),
        parse_mode="Markdown"
    )

# --- ФАЗА 3: Generation & Transaction ---
@dp.callback_query(F.data.startswith("gen_"), GenStates.confirm_screen)
async def process_generation(call: types.CallbackQuery, state: FSMContext):
    model_name = call.data.replace("gen_", "")
    await state.update_data(current_model=model_name)
    
    data = await state.get_data()
    prompt = data.get("prompt", "")
    cost = COSTS.get(model_name, 5)
    
    bal = await get_balance(call.from_user.id)
    if bal < cost:
        await call.answer(f"⚠️ Недостаточно кредитов! Нужно {cost}.", show_alert=True)
        return

    # Loading State (Стикеры/бананы запрещены ТЗ)
    status_msg = await call.message.edit_text("🎨 Генерация... Пожалуйста, подождите.")
    
    try:
        translated_prompt = GoogleTranslator(source='auto', target='en').translate(prompt)
    except Exception:
        translated_prompt = prompt

    model_endpoint = MODEL_ENDPOINTS.get(model_name, "nano-banana")
    
    # API Call (уже списывает кредиты на стороне API)
    image_url, err_msg = await generate_image(call.from_user.id, translated_prompt, model_endpoint, cost)
    
    if image_url:
        builder = InlineKeyboardBuilder()
        builder.row(types.InlineKeyboardButton(text="✍️ Редактировать", callback_data="start_gen")) # возвращает в ожидание контента
        builder.row(types.InlineKeyboardButton(text="🆕 Новая генерация", callback_data="start_gen"))
        
        await status_msg.delete()
        await call.message.answer_photo(
            photo=URLInputFile(image_url),
            caption=f"✅ Готово!\n📝 {translated_prompt}",
            reply_markup=builder.as_markup()
        )
        await state.clear()
    else:
        # Error Handling (frozen_balance возвращается на бэкенде)
        await status_msg.edit_text(f"❌ Ошибка! Кредиты сохранены на вашем балансе.\nДетали: {err_msg}")
        await asyncio.sleep(3)
        await status_msg.edit_text("Попробуйте снова:", reply_markup=await main_kb(call.from_user.id))

# --- ФАЗА 4: Partners & Finance ---
@dp.callback_query(F.data == "partners")
async def partners_menu(call: types.CallbackQuery):
    stats = await get_referral_stats(call.from_user.id)
    count = stats.get("referral_count", 0)
    link = stats.get("referral_link", f"https://t.me/your_bot_name?start=r-{call.from_user.id}")
    
    text = f"💰 **Партнерская программа**\n\nПриглашено друзей: {count}\nВаша ссылка:\n`{link}`\n\nПолучайте 10% от всех пополнений рефералов!"
    
    builder = InlineKeyboardBuilder()
    builder.row(types.InlineKeyboardButton(text="💸 Вывести средства", callback_data="withdraw"))
    builder.row(types.InlineKeyboardButton(text="⬅️ Назад", callback_data="cancel"))
    
    await call.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="Markdown")

@dp.callback_query(F.data == "withdraw")
async def withdraw_request(call: types.CallbackQuery):
    await call.answer("Функция вывода находится в разработке (Admin panel required).", show_alert=True)

from bot.api_client import get_or_create_user, get_balance, generate_image, get_referral_stats, create_payment_link

@dp.callback_query(F.data == "add_funds")
async def pay(call: types.CallbackQuery):
    # Warning message
    await call.message.answer("⏳ Создаем защищенную ссылку на оплату...")
    
    # Запрашиваем ссылку у нашего бэкенда (например, на 349 руб)
    amount = 349.0
    description = f"Пополнение баланса NanoBanana для ID {call.from_user.id}"
    
    checkout_url = await create_payment_link(call.from_user.id, amount, description)
    
    if checkout_url:
        builder = InlineKeyboardBuilder()
        builder.row(types.InlineKeyboardButton(text="💳 Оплатить 349 руб", url=checkout_url))
        
        await call.message.answer(
            "Нажмите кнопку ниже, чтобы перейти к защищенной оплате ЮKassa.\n⚠️ Если вы используете VPN, пожалуйста, выключите его перед оплатой.",
            reply_markup=builder.as_markup()
        )
    else:
        await call.message.answer("❌ Ошибка при создании ссылки на оплату. Повторите позже.")

@dp.message()
async def default_handler(message: types.Message):
    await message.answer("Я не понимаю эту команду. Используйте /start.")

async def run():
    logging.basicConfig(level=logging.INFO)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(run())
