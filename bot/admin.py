import os
import asyncio
from typing import List
from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from backend.database import AsyncSessionLocal
from backend import services

admin_router = Router()

def get_admin_ids() -> List[int]:
    ids_str = os.getenv("ADMIN_IDS", "")
    return [int(x.strip()) for x in ids_str.split(",") if x.strip().isdigit()]

class AdminFilter:
    async def __call__(self, message: Message) -> bool:
        return message.from_user.id in get_admin_ids()

# Attach filter to router
admin_router.message.filter(AdminFilter())
admin_router.callback_query.filter(AdminFilter())

class AdminStates(StatesGroup):
    waiting_for_user_query = State()
    waiting_for_balance_amount = State()
    waiting_for_broadcast_msg = State()

def get_admin_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="📊 Статистика", callback_data="admin_stats")
    kb.button(text="👤 Управление пользователем", callback_data="admin_manage_user")
    kb.button(text="📢 Рассылка", callback_data="admin_broadcast")
    kb.adjust(1)
    return kb.as_markup()

def get_back_admin_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="🔙 Назад в меню админа", callback_data="admin_menu")
    return kb.as_markup()

# --- HANDLERS ---
@admin_router.message(Command("admin"))
async def cmd_admin(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("👑 **Панель Администратора**\nВыберите раздел:", reply_markup=get_admin_kb(), parse_mode="Markdown")

@admin_router.callback_query(F.data == "admin_menu")
async def process_admin_menu(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("👑 **Панель Администратора**\nВыберите раздел:", reply_markup=get_admin_kb(), parse_mode="Markdown")

@admin_router.callback_query(F.data == "admin_stats")
async def process_admin_stats(callback: CallbackQuery):
    async with AsyncSessionLocal() as db:
        stats = await services.get_admin_stats(db)
        
    text = (
        f"📊 **Статистика Бота**\n\n"
        f"👥 Пользователи:\n"
        f"• Всего: **{stats['total_users']}**\n"
        f"• Новых за сегодня: **{stats['new_users_today']}**\n\n"
        f"🎨 Генерации:\n"
        f"• Всего: **{stats['total_gens']}**\n"
        f"• За сегодня: **{stats['gens_today']}**\n"
    )
    await callback.message.edit_text(text, reply_markup=get_back_admin_kb(), parse_mode="Markdown")

# --- USER MANAGEMENT ---
@admin_router.callback_query(F.data == "admin_manage_user")
async def process_manage_user(callback: CallbackQuery, state: FSMContext):
    await state.set_state(AdminStates.waiting_for_user_query)
    await callback.message.edit_text("Введите ID или @username пользователя для поиска:", reply_markup=get_back_admin_kb())

@admin_router.message(AdminStates.waiting_for_user_query)
async def process_user_query(message: Message, state: FSMContext):
    query = message.text.strip()
    async with AsyncSessionLocal() as db:
        user = await services.search_user(db, query)
        
    if not user:
        await message.answer(f"❌ Пользователь не найден.\nПопробуйте еще раз или вернитесь в меню.", reply_markup=get_back_admin_kb())
        return
        
    text = (
        f"👤 **Профиль {user.name or 'Без имени'}**\n"
        f"ID: `{user.id}`\n\n"
        f"💳 Текущий баланс: **{user.balance:.2f}**\n"
        f"❄️ Заморозок: {user.frozen_balance:.2f}\n"
        f"🤖 Активная модель: {user.model_preference}\n"
        f"📅 Регистрация: {user.created_at.strftime('%Y-%m-%d %H:%M') if user.created_at else 'Unknown'}\n"
    )
    
    kb = InlineKeyboardBuilder()
    kb.button(text="💰 Начислить баланс", callback_data=f"admin_add_bal:{user.id}")
    kb.button(text="📉 Списать баланс", callback_data=f"admin_sub_bal:{user.id}")
    kb.button(text="🔙 Назад", callback_data="admin_menu")
    kb.adjust(1)
    
    await state.clear()
    await message.answer(text, reply_markup=kb.as_markup(), parse_mode="Markdown")

@admin_router.callback_query(F.data.startswith("admin_add_bal:"))
@admin_router.callback_query(F.data.startswith("admin_sub_bal:"))
async def process_balance_action(callback: CallbackQuery, state: FSMContext):
    action, user_id = callback.data.split(":")[0], callback.data.split(":")[1]
    is_add = action == "admin_add_bal"
    
    await state.update_data(target_user_id=int(user_id), is_add=is_add)
    await state.set_state(AdminStates.waiting_for_balance_amount)
    
    verb = "начислить" if is_add else "списать"
    await callback.message.edit_text(f"Введите количество кредитов, которое нужно {verb} пользователю `{user_id}`:", reply_markup=get_back_admin_kb(), parse_mode="Markdown")

@admin_router.message(AdminStates.waiting_for_balance_amount)
async def process_balance_amount(message: Message, state: FSMContext):
    try:
        amount = float(message.text.strip().replace(",", "."))
    except ValueError:
        await message.answer("❌ Пожалуйста, введите число (например: 10).", reply_markup=get_back_admin_kb())
        return
        
    data = await state.get_data()
    user_id = data['target_user_id']
    is_add = data['is_add']
    
    if not is_add:
        amount = -amount
        
    async with AsyncSessionLocal() as db:
        user = await services.update_user_balance(db, user_id, amount)
        
    await state.clear()
    
    verb_past = "Начислено" if is_add else "Списано"
    abs_amount = abs(amount)
    await message.answer(f"✅ Успешно {verb_past.lower()} **{abs_amount}** кр.\nНовый баланс пользователя: **{user.balance:.2f}**", reply_markup=get_back_admin_kb(), parse_mode="Markdown")

# --- BROADCAST ---
@admin_router.callback_query(F.data == "admin_broadcast")
async def process_broadcast_start(callback: CallbackQuery, state: FSMContext):
    await state.set_state(AdminStates.waiting_for_broadcast_msg)
    await callback.message.edit_text(
        "📢 **Рассылка сообщений**\nПришлите сообщение (можно с фото или кнопками-ссылками), которое нужно отправить всем пользователям.", 
        reply_markup=get_back_admin_kb(),
        parse_mode="Markdown"
    )

@admin_router.message(AdminStates.waiting_for_broadcast_msg)
async def process_broadcast_msg(message: Message, state: FSMContext, bot: Bot):
    await state.clear()
    msg_wait = await message.answer("⏳ Собираю аудиторию для рассылки...")
    
    from sqlalchemy.future import select
    from backend import models
    
    async with AsyncSessionLocal() as db:
        res = await db.execute(select(models.User.id))
        user_ids = [row[0] for row in res.fetchall()]
        
    success = 0
    failed = 0
    
    await msg_wait.edit_text(f"🚀 Начинаю рассылку для {len(user_ids)} пользователей. Пожалуйста, подождите...")
    
    for uid in user_ids:
        try:
            await message.send_copy(chat_id=uid)
            success += 1
        except Exception:
            failed += 1
        await asyncio.sleep(0.05) # Telegram API limits ~30 msgs per sec
            
    await msg_wait.edit_text(f"✅ **Рассылка завершена!**\n\n🎯 Успешно доставлено: {success}\n❌ Заблокировали бота: {failed}", reply_markup=get_back_admin_kb(), parse_mode="Markdown")
