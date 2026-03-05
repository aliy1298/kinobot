import os
import asyncio
import logging
import sqlite3
from datetime import datetime
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.exceptions import TelegramBadRequest

# --- CONFIGURATION ---
API_TOKEN = '8594167381:AAG3q0FSs_o3RfqAWZyuRb-blR3Wo7ksiXE'
SUPERADMIN_ID = 7706048424
DATABASE = 'kino_bot.db'
MOVIE_CHANNEL_ID = "-1003736304208" # Bu yerga kinolar yuklangan kanal ID sini yozing

# --- LOGGING ---
logging.basicConfig(level=logging.INFO)

# --- STATES ---
class AdminStates(StatesGroup):
    waiting_for_broadcast = State()
    waiting_for_channel = State()
    waiting_for_new_admin = State()
    waiting_for_movie_channel = State()

# --- DATABASE SETUP ---
def init_db():
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, username TEXT, joined_date TEXT)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS admins (user_id INTEGER PRIMARY KEY, added_by INTEGER)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS channels (channel_id TEXT PRIMARY KEY)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)''')
    
    # Default settings
    cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", ('mandatory_enabled', '1'))
    cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", ('movie_channel', MOVIE_CHANNEL_ID))
    
    # Add superadmin to admins table
    cursor.execute("INSERT OR IGNORE INTO admins (user_id, added_by) VALUES (?, ?)", (SUPERADMIN_ID, 0))
    
    conn.commit()
    conn.close()

# DB Helper Functions
def db_query(query, params=(), fetchone=False, fetchall=False):
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute(query, params)
    res = None
    if fetchone: res = cursor.fetchone()
    elif fetchall: res = cursor.fetchall()
    conn.commit()
    conn.close()
    return res

def is_admin(user_id):
    res = db_query("SELECT user_id FROM admins WHERE user_id = ?", (user_id,), fetchone=True)
    return res is not None

# --- BOT INITIALIZATION ---
bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# --- UTILS ---
async def check_subscriptions(user_id):
    enabled = db_query("SELECT value FROM settings WHERE key = 'mandatory_enabled'", fetchone=True)[0]
    if enabled == '0': return []
    
    channels = [row[0] for row in db_query("SELECT channel_id FROM channels", fetchall=True)]
    not_subscribed = []
    for channel in channels:
        try:
            member = await bot.get_chat_member(chat_id=channel, user_id=user_id)
            if member.status not in ['member', 'administrator', 'creator']:
                not_subscribed.append(channel)
        except Exception:
            continue
    return not_subscribed

# --- HANDLERS ---

@dp.message(Command("start"))
async def start_cmd(message: types.Message):
    db_query("INSERT OR IGNORE INTO users (user_id, username, joined_date) VALUES (?, ?, ?)", 
             (message.from_user.id, message.from_user.username, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
    
    not_subscribed = await check_subscriptions(message.from_user.id)
    if not_subscribed:
        builder = InlineKeyboardBuilder()
        for ch in not_subscribed:
            builder.row(InlineKeyboardButton(text=f"A'zo bo'lish", url=f"https://t.me/{ch.replace('@', '')}"))
        builder.row(InlineKeyboardButton(text="✅ Tekshirish", callback_data="check_sub"))
        await message.answer("Botdan foydalanish uchun quyidagi kanallarga a'zo bo'ling:", reply_markup=builder.as_markup())
        return

    # Check if user sent a movie code
    args = message.text.split()
    if len(args) > 1:
        code = args[1]
        await send_movie(message, code)
    else:
        await message.answer("Assalomu alaykum! Kino kodini yuboring.")

@dp.callback_query(F.data == "check_sub")
async def check_sub_cb(callback: CallbackQuery):
    not_subscribed = await check_subscriptions(callback.from_user.id)
    if not not_subscribed:
        await callback.message.edit_text("Rahmat! Endi kino kodini yuborishingiz mumkin.")
    else:
        await callback.answer("Hamma kanallarga a'zo bo'lmadingiz!", show_alert=True)

async def send_movie(message, code):
    movie_channel = db_query("SELECT value FROM settings WHERE key = 'movie_channel'", fetchone=True)[0]
    try:
        # Copy the message from the channel using the ID (code)
        await bot.copy_message(chat_id=message.chat.id, from_chat_id=movie_channel, message_id=int(code))
    except Exception as e:
        await message.answer("Kino topilmadi yoki kod xato. Iltimos, tekshirib qayta yuboring.")

@dp.message(F.text.isdigit())
async def handle_movie_code(message: types.Message):
    not_subscribed = await check_subscriptions(message.from_user.id)
    if not_subscribed:
        await start_cmd(message)
        return
    await send_movie(message, message.text)

# --- ADMIN PANEL ---

@dp.message(Command("admin"))
async def admin_cmd(message: types.Message):
    if not is_admin(message.from_user.id): return
    
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="📊 Statistika", callback_data="adm_stats"))
    builder.row(InlineKeyboardButton(text="🔗 Kanallar", callback_data="adm_channels"))
    builder.row(InlineKeyboardButton(text="📢 Reklama", callback_data="adm_broadcast"))
    builder.row(InlineKeyboardButton(text="👑 Adminlar", callback_data="adm_admins"))
    builder.row(InlineKeyboardButton(text="⚙️ Sozlamalar", callback_data="adm_settings"))
    
    await message.answer("🚀 Admin Panelga xush kelibsiz:", reply_markup=builder.as_markup())

@dp.callback_query(F.data == "adm_stats")
async def adm_stats_cb(callback: CallbackQuery):
    u_count = db_query("SELECT COUNT(*) FROM users", fetchone=True)[0]
    a_count = db_query("SELECT COUNT(*) FROM admins", fetchone=True)[0]
    c_count = db_query("SELECT COUNT(*) FROM channels", fetchone=True)[0]
    
    text = f"📊 **Bot Statistikasi:**\n\n" \
           f"👥 Foydalanuvchilar: {u_count}\n" \
           f"👑 Adminlar: {a_count}\n" \
           f"📢 Majburiy kanallar: {c_count}"
    await callback.message.answer(text)
    await callback.answer()

@dp.callback_query(F.data == "adm_channels")
async def adm_channels_cb(callback: CallbackQuery):
    channels = [row[0] for row in db_query("SELECT channel_id FROM channels", fetchall=True)]
    builder = InlineKeyboardBuilder()
    for ch in channels:
        builder.row(InlineKeyboardButton(text=f"❌ {ch}", callback_data=f"del_ch|{ch}"))
    builder.row(InlineKeyboardButton(text="➕ Kanal qo'shish", callback_data="add_ch"))
    
    enabled = db_query("SELECT value FROM settings WHERE key = 'mandatory_enabled'", fetchone=True)[0]
    status_text = "✅ Yoqilgan" if enabled == '1' else "❌ O'chirilgan"
    builder.row(InlineKeyboardButton(text=f"Holat: {status_text}", callback_data="toggle_mandatory"))
    builder.row(InlineKeyboardButton(text="⬅️ Orqaga", callback_data="adm_back"))
    
    await callback.message.edit_text("🔗 Majburiy kanallarni boshqarish:", reply_markup=builder.as_markup())

@dp.callback_query(F.data == "toggle_mandatory")
async def toggle_mandatory_cb(callback: CallbackQuery):
    current = db_query("SELECT value FROM settings WHERE key = 'mandatory_enabled'", fetchone=True)[0]
    new_val = '0' if current == '1' else '1'
    db_query("UPDATE settings SET value = ? WHERE key = 'mandatory_enabled'", (new_val,))
    await adm_channels_cb(callback)

@dp.callback_query(F.data == "add_ch")
async def add_ch_cb(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer("Kanal username'ini yuboring (masalan: @kanal_nomi):")
    await state.set_state(AdminStates.waiting_for_channel)
    await callback.answer()

@dp.callback_query(F.data.startswith("del_ch|"))
async def del_ch_cb(callback: CallbackQuery):
    ch_id = callback.data.split("|")[1]
    db_query("DELETE FROM channels WHERE channel_id = ?", (ch_id,))
    await adm_channels_cb(callback)

@dp.callback_query(F.data == "adm_admins")
async def adm_admins_cb(callback: CallbackQuery):
    if callback.from_user.id != SUPERADMIN_ID:
        await callback.answer("Faqat Superadmin uchun!", show_alert=True)
        return
    
    admins = db_query("SELECT user_id FROM admins", fetchall=True)
    builder = InlineKeyboardBuilder()
    for (a_id,) in admins:
        if a_id == SUPERADMIN_ID: continue
        builder.row(InlineKeyboardButton(text=f"❌ {a_id}", callback_data=f"del_adm|{a_id}"))
    builder.row(InlineKeyboardButton(text="➕ Admin qo'shish", callback_data="add_adm"))
    builder.row(InlineKeyboardButton(text="⬅️ Orqaga", callback_data="adm_back"))
    await callback.message.edit_text("👑 Adminlarni boshqarish:", reply_markup=builder.as_markup())

@dp.callback_query(F.data == "add_adm")
async def add_adm_cb(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer("Yangi admin ID sini yuboring:")
    await state.set_state(AdminStates.waiting_for_new_admin)
    await callback.answer()

@dp.callback_query(F.data.startswith("del_adm|"))
async def del_adm_cb(callback: CallbackQuery):
    a_id = callback.data.split("|")[1]
    db_query("DELETE FROM admins WHERE user_id = ?", (a_id,))
    await adm_admins_cb(callback)

@dp.callback_query(F.data == "adm_broadcast")
async def adm_broadcast_cb(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer("Reklama xabarini yuboring (Forward, Rasm, Video, Text hammasi o'tadi):")
    await state.set_state(AdminStates.waiting_for_broadcast)
    await callback.answer()

@dp.callback_query(F.data == "adm_settings")
async def adm_settings_cb(callback: CallbackQuery):
    current = db_query("SELECT value FROM settings WHERE key = 'movie_channel'", fetchone=True)[0]
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="Kino kanalini o'zgartirish", callback_data="set_movie_ch"))
    builder.row(InlineKeyboardButton(text="⬅️ Orqaga", callback_data="adm_back"))
    await callback.message.edit_text(f"⚙️ Sozlamalar:\n\nKino kanali: {current}", reply_markup=builder.as_markup())

@dp.callback_query(F.data == "set_movie_ch")
async def set_movie_ch_cb(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer("Kino kanali ID yoki username'ini yuboring:")
    await state.set_state(AdminStates.waiting_for_movie_channel)
    await callback.answer()

@dp.callback_query(F.data == "adm_back")
async def adm_back_cb(callback: CallbackQuery):
    await admin_cmd(callback.message)
    await callback.message.delete()

# --- FSM PROCESSORS ---

@dp.message(AdminStates.waiting_for_channel)
async def proc_add_ch(message: types.Message, state: FSMContext):
    db_query("INSERT OR IGNORE INTO channels (channel_id) VALUES (?)", (message.text,))
    await message.answer(f"{message.text} qo'shildi.")
    await state.clear()

@dp.message(AdminStates.waiting_for_new_admin)
async def proc_add_adm(message: types.Message, state: FSMContext):
    if message.text.isdigit():
        db_query("INSERT OR IGNORE INTO admins (user_id, added_by) VALUES (?, ?)", (int(message.text), message.from_user.id))
        await message.answer(f"ID {message.text} admin qilindi.")
        await state.clear()
    else:
        await message.answer("Faqat raqam yuboring!")

@dp.message(AdminStates.waiting_for_movie_channel)
async def proc_set_movie_ch(message: types.Message, state: FSMContext):
    db_query("UPDATE settings SET value = ? WHERE key = 'movie_channel'", (message.text,))
    await message.answer(f"Kino kanali {message.text} ga o'zgartirildi.")
    await state.clear()

@dp.message(AdminStates.waiting_for_broadcast)
async def proc_broadcast(message: types.Message, state: FSMContext):
    users = [row[0] for row in db_query("SELECT user_id FROM users", fetchall=True)]
    count = 0
    msg = await message.answer(f"Yuborilmoqda: 0/{len(users)}")
    for i, u_id in enumerate(users):
        try:
            await message.copy_to(u_id)
            count += 1
            if count % 20 == 0:
                await msg.edit_text(f"Yuborilmoqda: {count}/{len(users)}")
            await asyncio.sleep(0.05)
        except Exception:
            pass
    await msg.edit_text(f"Tugatildi. {count} ta foydalanuvchiga yuborildi.")
    await state.clear()

async def main():
    init_db()
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
