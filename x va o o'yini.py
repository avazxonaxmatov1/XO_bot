import asyncio
import logging
import sqlite3
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardMarkup, KeyboardButton
from aiogram.exceptions import TelegramForbiddenError, TelegramBadRequest, TelegramNetworkError

TOKEN = "8968950657:AAFpx0i43qs6Jr_cpdoDFh1YKJgsFT0oP8g"
bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())

waiting_player = None
games = {}

# --- BAZA BILAN ISHLASH FUNKSIYALARI ---
def init_db():
    """Ma'lumotlar bazasini yaratish"""
    conn = sqlite3.connect("game_database.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            nickname TEXT,
            points INTEGER DEFAULT 100,
            hints INTEGER DEFAULT 0,
            blocks INTEGER DEFAULT 0
        )
    """)
    conn.commit()
    conn.close()

def get_user(user_id):
    """Foydalanuvchi ma'lumotlarini bazadan olish"""
    conn = sqlite3.connect("game_database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT nickname, points, hints, blocks FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return {"nickname": row[0], "points": row[1], "hints": row[2], "blocks": row[3]}
    return None

def add_user(user_id, nickname):
    """Yangi foydalanuvchini bazaga qo'shish"""
    conn = sqlite3.connect("game_database.db")
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO users (user_id, nickname, points, hints, blocks) VALUES (?, ?, 100, 0, 0)", (user_id, nickname))
    conn.commit()
    conn.close()

def update_user_field(user_id, field, value):
    """Foydalanuvchi ma'lumotlarini yangilash"""
    conn = sqlite3.connect("game_database.db")
    cursor = conn.cursor()
    cursor.execute(f"UPDATE users SET {field} = ? WHERE user_id = ?", (value, user_id))
    conn.commit()
    conn.close()

# Bazasini ishga tushiramiz
init_db()

class ProfileState(StatesGroup):
    waiting_for_nickname = State()
    waiting_for_new_nickname = State()

def get_main_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🎮 O'yinni boshlash")],
            [KeyboardButton(text="👤 Mening profilim"), KeyboardButton(text="🛒 Do'kon")],
            [KeyboardButton(text="✏️ Nickname'ni almashtirish")]
        ],
        resize_keyboard=True,
        persistent=True
    )

async def send_safe_message(user_id, text, reply_markup=None, parse_mode=None):
    try:
        return await bot.send_message(user_id, text, reply_markup=reply_markup, parse_mode=parse_mode)
    except (TelegramForbiddenError, TelegramBadRequest):
        logging.warning(f"Foydalanuvchi {user_id} ga xabar yuborib bo'lmadi (bloklangan).")
    except TelegramNetworkError:
        logging.error("Internet ulanishida muammo yuzaga keldi.")
    except Exception as e:
        logging.error(f"Xabar yuborishda kutilmagan xatolik: {e}")

def check_winner(b):
    wins = [(0,1,2), (3,4,5), (6,7,8), (0,3,6), (1,4,7), (2,5,8), (0,4,8), (2,4,6)]
    for w in wins:
        if b[w[0]] == b[w[1]] == b[w[2]] != " ":
            return b[w[0]]
    if " " not in b:
        return "Draw"
    return None

def get_board_keyboard(board):
    builder = InlineKeyboardBuilder()
    for i in range(9):
        builder.button(text=board[i], callback_data=f"cell_{i}")
    builder.adjust(3)
    return builder.as_markup()

@dp.message(Command("start"))
async def start_cmd(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    user = get_user(user_id)

    if not user:
        await send_safe_message(user_id, "Salom! 'X va O' o'yiniga xush kelibsiz.\nIltimos, Nickname kiriting:")
        await state.set_state(ProfileState.waiting_for_nickname)
    else:
        nickname = user["nickname"]
        await send_safe_message(user_id, f"Xush kelibsiz, {nickname}! Sizning ballaringiz saqlangan.", reply_markup=get_main_keyboard())

@dp.message(ProfileState.waiting_for_nickname)
async def process_nickname(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    nickname = message.text.strip()

    if len(nickname) < 2 or len(nickname) > 20:
        await send_safe_message(user_id, "Nickname 2 dan 20 gacha belgidan iborat bo'lsin. Qayta kiriting:")
        return

    add_user(user_id, nickname)
    await state.clear()
    await send_safe_message(user_id, f"Ajoyib, {nickname}! Sizga 100 boshlang'ich ball berildi. 🎉", reply_markup=get_main_keyboard())

@dp.message(F.text == "✏️ Nickname'ni almashtirish")
async def change_nickname_cmd(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    user = get_user(user_id)
    if not user:
        await send_safe_message(user_id, "Iltimos, avval /start buyrug'ini bosing!", reply_markup=get_main_keyboard())
        return

    await send_safe_message(user_id, "Yangi Nickname'ni kiriting (2 dan 20 gacha belgi):")
    await state.set_state(ProfileState.waiting_for_new_nickname)

@dp.message(ProfileState.waiting_for_new_nickname)
async def process_new_nickname(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    new_nickname = message.text.strip()

    if len(new_nickname) < 2 or len(new_nickname) > 20:
        await send_safe_message(user_id, "Nickname 2 dan 20 gacha belgidan iborat bo'lsin. Qayta kiriting:")
        return

    update_user_field(user_id, "nickname", new_nickname)
    await state.clear()
    await send_safe_message(user_id, f"Nickname muvaffaqiyatli o'zgartirildi! Yangi ismingiz: **{new_nickname}** 🎉", reply_markup=get_main_keyboard(), parse_mode="Markdown")

@dp.message(F.text == "👤 Mening profilim")
async def show_profile(message: types.Message):
    user_id = message.from_user.id
    u = get_user(user_id)
    if not u:
        await send_safe_message(user_id, "Iltimos, avval /start buyrug'ini bosing!", reply_markup=get_main_keyboard())
        return

    text = (
        f"👤 **Foydalanuvchi profili**\n\n"
        f"🏷 **Nickname:** {u['nickname']}\n"
        f"🏆 **Jamg'arilgan ball:** {u['points']} ball\n"
        f"💡 **Kichik yordamlar:** {u['hints']} ta\n"
        f"🛡 **Avto-blok yordamlari:** {u['blocks']} ta"
    )
    await send_safe_message(user_id, text, reply_markup=get_main_keyboard(), parse_mode="Markdown")

@dp.message(F.text == "🛒 Do'kon")
async def show_shop(message: types.Message):
    user_id = message.from_user.id
    builder = InlineKeyboardBuilder()
    builder.button(text="💡 Kichik yordam (300 ball)", callback_data="buy_hint")
    builder.button(text="🛡 Avto-blok yordami (500 ball)", callback_data="buy_block")
    builder.adjust(1)

    await send_safe_message(user_id, "🛒 **Do'kon**\n\nBallaringiz evaziga o'yindagi yordamlarni sotib oling:", reply_markup=builder.as_markup(), parse_mode="Markdown")

@dp.callback_query(F.data.startswith("buy_"))
async def process_buy(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    u = get_user(user_id)
    if not u:
        await callback.answer("Avval /start bosing!", show_alert=True)
        return

    item = callback.data.split("_")[1]

    if item == "hint":
        if u["points"] >= 300:
            update_user_field(user_id, "points", u["points"] - 300)
            update_user_field(user_id, "hints", u["hints"] + 1)
            await callback.answer("💡 Kichik yordam sotib olindi!", show_alert=True)
        else:
            await callback.answer("Mablag' yetarli emas! Sizga 300 ball kerak.", show_alert=True)
    elif item == "block":
        if u["points"] >= 500:
            update_user_field(user_id, "points", u["points"] - 500)
            update_user_field(user_id, "blocks", u["blocks"] + 1)
            await callback.answer("🛡 Avto-blok yordami sotib olindi!", show_alert=True)
        else:
            await callback.answer("Mablag' yetarli emas! Sizga 500 ball kerak.", show_alert=True)

@dp.message(Command("play"))
@dp.message(F.text == "🎮 O'yinni boshlash")
async def play_cmd(message: types.Message):
    global waiting_player
    user_id = message.from_user.id
    u = get_user(user_id)

    if not u:
        await send_safe_message(user_id, "Iltimos, avval /start buyrug'ini yuboring va Nickname kiriting!", reply_markup=get_main_keyboard())
        return

    user_nick = u["nickname"]

    if waiting_player is None:
        waiting_player = user_id
        await send_safe_message(user_id, f"Raqib kutilmoqda, {user_nick}... Ikkinchi o'yinchi '🎮 O'yinni boshlash' tugmasini bosishi kerak.")
    elif waiting_player == user_id:
        await send_safe_message(user_id, f"{user_nick}, siz allaqachon navbatdasiz! Ikkinchi o'yinchini kuting.")
    else:
        p1, p2 = waiting_player, user_id
        waiting_player = None
        game_id = f"{p1}_{p2}"

        games[game_id] = {
            "board": [" "] * 9,
            "turn": p1,
            "p1": p1,
            "p2": p2,
            "sym": {p1: "❌", p2: "⭕"}
        }

        p1_nick = get_user(p1)["nickname"]
        p2_nick = get_user(p2)["nickname"]

        markup = get_board_keyboard(games[game_id]["board"])
        await send_safe_message(p1, f"Raqib topildi ({p2_nick})! Sizning yurishingiz (❌):", reply_markup=markup)
        await send_safe_message(p2, f"Raqib topildi ({p1_nick})! Birinchi yurish raqibda (⭕):", reply_markup=markup)

@dp.callback_query(F.data.startswith("cell_"))
async def handle_cell(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    cell_idx = int(callback.data.split("_")[1])

    game_id = None
    for g_id, g_data in games.items():
        if user_id in (g_data["p1"], g_data["p2"]):
            game_id = g_id
            break

    if not game_id:
        await callback.answer("Aktiv o'yin topilmadi.", show_alert=True)
        return

    game = games[game_id]

    if game["turn"] != user_id:
        await callback.answer("Hozir raqibning yurish navbati!", show_alert=True)
        return

    if game["board"][cell_idx] != " ":
        await callback.answer("Bu katakcha band!", show_alert=True)
        return

    symbol = game["sym"][user_id]
    game["board"][cell_idx] = symbol
    next_player = game["p2"] if user_id == game["p1"] else game["p1"]
    game["turn"] = next_player

    winner = check_winner(game["board"])
    markup = get_board_keyboard(game["board"])

    if winner:
        p1, p2 = game["p1"], game["p2"]
        u1 = get_user(p1)
        u2 = get_user(p2)

        if winner == "Draw":
            update_user_field(p1, "points", u1["points"] + 5)
            update_user_field(p2, "points", u2["points"] + 5)
            text = "O'yin durang bilan yakunlandi! 🤝\nHar ikkala o'yinchiga +5 ball berildi."
        else:
            winner_id = p1 if symbol == "❌" else p2
            loser_id = p2 if symbol == "❌" else p1

            winner_user = get_user(winner_id)
            loser_user = get_user(loser_id)

            update_user_field(winner_id, "points", winner_user["points"] + 15)
            update_user_field(loser_id, "points", max(0, loser_user["points"] - 5))

            winner_nick = winner_user["nickname"]
            loser_nick = loser_user["nickname"]

            text = (
                f"O'yin tugadi! G'olib: 🏆 {winner_nick} ({symbol})\n\n"
                f"🎉 {winner_nick}: +15 ball\n"
                f"💔 {loser_nick}: -5 ball"
            )

        await send_safe_message(p1, text, reply_markup=get_main_keyboard())
        await send_safe_message(p2, text, reply_markup=get_main_keyboard())
        
        del games[game_id]
    else:
        next_nick = get_user(next_player)["nickname"]
        await send_safe_message(next_player, f"{next_nick}, sizning navbatingiz ({game['sym'][next_player]}):", reply_markup=markup)
        try:
            await callback.message.edit_reply_markup(reply_markup=markup)
        except Exception:
            pass

async def main():
    logging.basicConfig(level=logging.INFO)
    await bot.delete_webhook(drop_pending_updates=True)
    
    while True:
        try:
            await dp.start_polling(bot)
        except TelegramNetworkError:
            logging.error("Internet ulanishi uzildi. 5 soniyadan so'ng qayta ulanadi...")
            await asyncio.sleep(5)
        except Exception as e:
            logging.error(f"Kutilmagan xatolik: {e}")
            await asyncio.sleep(5)

if __name__ == "__main__":
    asyncio.run(main())
