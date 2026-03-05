import asyncio
import logging
import sqlite3
from datetime import datetime

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

# ================= CONFIG =================
API_TOKEN = "8594167381:AAG3q0FSs_o3RfqAWZyuRb-blR3Wo7ksiXE"
SUPERADMIN_ID = 7706048424
DATABASE = "kino_bot.db"
MOVIE_CHANNEL_ID = "-1003736304208"

logging.basicConfig(level=logging.INFO)

# ================= STATES =================
class AdminStates(StatesGroup):
    waiting_for_channel = State()
    waiting_for_broadcast = State()

# ================= DATABASE =================
def init_db():
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()

    c.execute("CREATE TABLE IF NOT EXISTS users(user_id INTEGER PRIMARY KEY, username TEXT, joined TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS admins(user_id INTEGER PRIMARY KEY)")
    c.execute("CREATE TABLE IF NOT EXISTS channels(channel_id TEXT PRIMARY KEY)")
    c.execute("CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT)")

    c.execute("INSERT OR IGNORE INTO settings VALUES('mandatory','1')")
    c.execute("INSERT OR IGNORE INTO settings VALUES('movie_channel',?)",(MOVIE_CHANNEL_ID,))
    c.execute("INSERT OR IGNORE INTO admins VALUES(?)",(SUPERADMIN_ID,))

    conn.commit()
    conn.close()

def db(q,p=(),one=False,all=False):
    conn=sqlite3.connect(DATABASE)
    c=conn.cursor()
    c.execute(q,p)
    data=None
    if one:data=c.fetchone()
    if all:data=c.fetchall()
    conn.commit()
    conn.close()
    return data

def is_admin(uid):
    return db("SELECT user_id FROM admins WHERE user_id=?",(uid,),one=True)

# ================= BOT =================
bot=Bot(API_TOKEN)
dp=Dispatcher()

# ================= CHECK SUB =================
async def check_sub(uid):
    mandatory=db("SELECT value FROM settings WHERE key='mandatory'",one=True)[0]
    if mandatory=="0":
        return []

    channels=[x[0] for x in db("SELECT channel_id FROM channels",all=True)]
    not_joined=[]

    for ch in channels:
        try:
            member=await bot.get_chat_member(ch,uid)
            if member.status in ["left","kicked"]:
                not_joined.append(ch)
        except:
            not_joined.append(ch)

    return not_joined

# ================= START =================
@dp.message(Command("start"))
async def start(message: types.Message):
    db("INSERT OR IGNORE INTO users VALUES(?,?,?)",
       (message.from_user.id,message.from_user.username,
        datetime.now().strftime("%Y-%m-%d %H:%M:%S")))

    # Majburiy kanallarni olish
    channels = [x[0] for x in db("SELECT channel_id FROM channels", all=True)]
    not_joined = await check_sub(message.from_user.id)

    builder = InlineKeyboardBuilder()

    for ch in channels:
        try:
            invite = await bot.create_chat_invite_link(chat_id=ch, member_limit=1)
            status = "✅ A'zo bo'lgansiz" if ch not in not_joined else "📢 Qo‘shiling"
            builder.row(
                InlineKeyboardButton(
                    text=f"{ch} - {status}",
                    url=invite.invite_link
                )
            )
        except Exception as e:
            print(e)

    builder.row(InlineKeyboardButton(text="✅ Tekshirish", callback_data="check"))

    await message.answer(
        "Botdan foydalanish uchun majburiy kanallarga a'zo bo'ling:",
        reply_markup=builder.as_markup()
    )

@dp.callback_query(F.data=="check")
async def check_btn(call: CallbackQuery):
    not_joined = await check_sub(call.from_user.id)
    if not not_joined:
        await call.message.edit_text("✅ Tasdiqlandi! Endi kino kodi yuboring.")
    else:
        await call.answer(f"Hali a'zo bo'lmagan kanallar: {', '.join(not_joined)}", show_alert=True)

    await message.answer(
        "Botdan foydalanish uchun kanalga a'zo bo'ling:",
        reply_markup=builder.as_markup()
    )

@dp.callback_query(F.data=="check")
async def check_btn(call:CallbackQuery):
    not_joined=await check_sub(call.from_user.id)
    if not not_joined:
        await call.message.edit_text("✅ Tasdiqlandi! Endi kod yuboring.")
    else:
        await call.answer("Hali a'zo emassiz!",show_alert=True)

# ================= MOVIE =================
async def send_movie(message,code):
    channel=db("SELECT value FROM settings WHERE key='movie_channel'",one=True)[0]
    try:
        await bot.copy_message(message.chat.id,channel,int(code))
    except:
        await message.answer("❌ Kino topilmadi")

@dp.message(F.text.regexp(r"^\d+$"))
async def movie(message:types.Message):
    if await check_sub(message.from_user.id):
        await start(message)
        return
    await send_movie(message,message.text)

# ================= ADMIN PANEL =================
@dp.message(Command("admin"))
async def admin_panel(message:types.Message):
    if not is_admin(message.from_user.id):
        return

    builder=InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="📊 Statistika",callback_data="stats"))
    builder.row(InlineKeyboardButton(text="📢 Kanallar",callback_data="channels"))
    builder.row(InlineKeyboardButton(text="📨 Reklama",callback_data="broadcast"))
    await message.answer("⚙️ Admin Panel",reply_markup=builder.as_markup())

# ================= STATS =================
@dp.callback_query(F.data=="stats")
async def stats(call:CallbackQuery):
    users=db("SELECT COUNT(*) FROM users",one=True)[0]
    ch=db("SELECT COUNT(*) FROM channels",one=True)[0]
    mandatory=db("SELECT value FROM settings WHERE key='mandatory'",one=True)[0]
    status="Yoqilgan" if mandatory=="1" else "O'chirilgan"

    await call.message.answer(
        f"👥 Users: {users}\n"
        f"📢 Kanallar: {ch}\n"
        f"🔒 Majburiy: {status}"
    )
    await call.answer()

# ================= CHANNEL MENU =================
@dp.callback_query(F.data=="channels")
async def channel_menu(call:CallbackQuery):
    channels=[x[0] for x in db("SELECT channel_id FROM channels",all=True)]
    builder=InlineKeyboardBuilder()

    for ch in channels:
        builder.row(
            InlineKeyboardButton(
                text=f"❌ {ch}",
                callback_data=f"del|{ch}"
            )
        )

    builder.row(InlineKeyboardButton(text="➕ Kanal qo'shish",callback_data="add"))
    builder.row(InlineKeyboardButton(text="🔄 Majburiy ON/OFF",callback_data="toggle"))

    await call.message.edit_text("📢 Kanallar:",reply_markup=builder.as_markup())
    await call.answer()

# ================= ADD CHANNEL =================
@dp.callback_query(F.data=="add")
async def add_channel(call:CallbackQuery,state:FSMContext):
    await call.message.answer("Kanal ID yoki @username yuboring:")
    await state.set_state(AdminStates.waiting_for_channel)
    await call.answer()

@dp.message(AdminStates.waiting_for_channel)
async def save_channel(message:types.Message,state:FSMContext):
    try:
        await bot.get_chat(message.text)
        db("INSERT OR IGNORE INTO channels VALUES(?)",(message.text,))
        await message.answer("✅ Kanal qo'shildi")
    except:
        await message.answer("❌ Bot admin emas yoki kanal xato")
    await state.clear()

# ================= DELETE CHANNEL =================
@dp.callback_query(F.data.startswith("del|"))
async def delete_channel(call:CallbackQuery):
    ch=call.data.split("|")[1]
    db("DELETE FROM channels WHERE channel_id=?",(ch,))
    await call.answer("O'chirildi")
    await channel_menu(call)

# ================= TOGGLE =================
@dp.callback_query(F.data=="toggle")
async def toggle(call:CallbackQuery):
    cur=db("SELECT value FROM settings WHERE key='mandatory'",one=True)[0]
    new="0" if cur=="1" else "1"
    db("UPDATE settings SET value=?",(new,))
    await call.answer("O'zgartirildi")
    await channel_menu(call)

# ================= BROADCAST =================
@dp.callback_query(F.data=="broadcast")
async def broadcast(call:CallbackQuery,state:FSMContext):
    await call.message.answer("Reklama yuboring:")
    await state.set_state(AdminStates.waiting_for_broadcast)
    await call.answer()

@dp.message(AdminStates.waiting_for_broadcast)
async def send_broadcast(message:types.Message,state:FSMContext):
    users=[x[0] for x in db("SELECT user_id FROM users",all=True)]
    sent=0
    for u in users:
        try:
            await message.copy_to(u)
            sent+=1
            await asyncio.sleep(0.05)
        except:
            pass
    await message.answer(f"✅ Yuborildi: {sent} ta")
    await state.clear()

# ================= MAIN =================
async def main():
    init_db()
    await dp.start_polling(bot)

if __name__=="__main__":
    asyncio.run(main())
