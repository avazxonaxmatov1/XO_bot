import asyncio
import logging
import os
import random
from aiohttp import web
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

BOT_TOKEN = "8968950657:AAFpx0i43qs6Jr_cpdoDFh1YKJgsFT0oP8g"  # <-- O'zingizning to'liq tokeningizni yozing

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Foydalanuvchilar ma'lumotlari
user_data = {}  # {user_id: {"score": 0, "nickname": "Ism", "vip": False, "shield": 0}}
vs_bot_games = {}
pvp_queue = None
pvp_games = {}


# FSM State nikni o'zgartirish uchun
class NickState(StatesGroup):
    waiting_for_nick = State()


# --- RENDER SERVER ---
async def handle(request):
    return web.Response(text="Bot 24/7 rejimda ishlamoqda!")


async def start_server():
    app = web.Application()
    app.router.add_get("/", handle)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 8080))
    await web.TCPSite(runner, "0.0.0.0", port).start()


# --- MINGAN FUNKSIYALAR ---
def get_user(user_id, default_name):
    if user_id not in user_data:
        user_data[user_id] = {
            "score": 0,
            "nickname": default_name,
            "vip": False,
            "shield": 0,
        }
    return user_data[user_id]


def get_board_keyboard(board, prefix="pvp"):
    builder = []
    for i in range(3):
        row = []
        for j in range(3):
            idx = i * 3 + j
            text = board[idx] if board[idx] != " " else " "
            row.append(
                InlineKeyboardButton(
                    text=text, callback_data=f"{prefix}_{idx}"
                )
            )
        builder.append(row)
    return InlineKeyboardMarkup(inline_keyboard=builder)


def check_winner(b, mark):
    win_conditions = [
        [0, 1, 2],
        [3, 4, 5],
        [6, 7, 8],
        [0, 3, 6],
        [1, 4, 7],
        [2, 5, 8],
        [0, 4, 8],
        [2, 4, 6],
    ]
    return any(all(b[i] == mark for i in pos) for pos in win_conditions)


# --- MENYU XABARI ---
def main_menu_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="👥 Odam bilan o'ynash", callback_data="play_pvp"
                )
            ],
            [
                InlineKeyboardButton(
                    text="🤖 Bot bilan o'ynash (+10 ball)",
                    callback_data="play_vs_bot",
                )
            ],
            [
                InlineKeyboardButton(
                    text="👤 Profil va Sozlamalar", callback_data="my_profile"
                ),
                InlineKeyboardButton(
                    text="🛒 Do'kon (Magazin)", callback_data="shop_menu"
                ),
            ],
        ]
    )


@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    u = get_user(message.from_user.id, message.from_user.first_name)
    status = " 👑 VIP" if u["vip"] else ""
    await message.answer(
        f"Salom, {u['nickname']}{status}!\n"
        f"X va O o'yiniga xush kelibsiz!\n"
        f"O'yin rejimini tanlang:",
        reply_markup=main_menu_keyboard(),
    )


# --- PROFIL VA NIKNI O'ZGARTIRISH ---
@dp.callback_query(F.data == "my_profile")
async def show_profile(callback: types.CallbackQuery):
    u = get_user(callback.from_user.id, callback.from_user.first_name)
    status = "👑 VIP O'yinchi" if u["vip"] else "Oddiy"

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✏️ Nikni o'zgartirish", callback_data="change_nick"
                )
            ],
            [
                InlineKeyboardButton(
                    text="🔙 Bosh menyu", callback_data="back_main"
                )
            ],
        ]
    )

    await callback.message.edit_text(
        f"👤 **PROFILINGIZ:**\n\n"
        f"✏️ **Nik:** {u['nickname']}\n"
        f"🏆 **Ballar:** {u['score']} ball\n"
        f"🎖 **Status:** {status}\n"
        f"🛡 **Qalqonlar:** {u['shield']} ta",
        parse_mode="Markdown",
        reply_markup=kb,
    )


@dp.callback_query(F.data == "change_nick")
async def change_nick_start(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(NickState.waiting_for_nick)
    await callback.message.answer(
        "Yangi nikingizni yuboring (Masalan: Bot_Qiroli):"
    )
    await callback.answer()


@dp.message(NickState.waiting_for_nick)
async def process_nick(message: types.Message, state: FSMContext):
    new_nick = message.text[:20]  # Maksimal 20 harf
    u = get_user(message.from_user.id, message.from_user.first_name)
    u["nickname"] = new_nick

    await state.clear()
    await message.answer(
        f"✅ Nikingiz muvaffaqiyatli o'zgardi: **{new_nick}**",
        parse_mode="Markdown",
        reply_markup=main_menu_keyboard(),
    )


# --- DO'KON (SHOP) MENYUSI ---
@dp.callback_query(F.data == "shop_menu")
async def show_shop(callback: types.CallbackQuery):
    u = get_user(callback.from_user.id, callback.from_user.first_name)

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🛡 Yutqazmaslik qalqoni (30 ball)",
                    callback_data="buy_shield",
                )
            ],
            [
                InlineKeyboardButton(
                    text="👑 VIP Maqom olish (100 ball)",
                    callback_data="buy_vip",
                )
            ],
            [
                InlineKeyboardButton(
                    text="🔙 Bosh menyu", callback_data="back_main"
                )
            ],
        ]
    )

    await callback.message.edit_text(
        f"🛒 **IMKONIYATLAR DO'KONI**\n\n"
        f"Sizning balingiz: **{u['score']} ball**\n\n"
        f"1. 🛡 **Yutqazmaslik qalqoni**: Yutqazganingizda ballaringiz kamaymaydi.\n"
        f"2. 👑 **VIP Maqom**: Profilingizda oltin toj paydo bo'ladi.",
        parse_mode="Markdown",
        reply_markup=kb,
    )


@dp.callback_query(F.data == "buy_shield")
async def buy_shield(callback: types.CallbackQuery):
    u = get_user(callback.from_user.id, callback.from_user.first_name)
    if u["score"] >= 30:
        u["score"] -= 30
        u["shield"] += 1
        await callback.answer(
            "🛡 Qalqon muvaffaqiyatli xarid qilindi!", show_alert=True
        )
        await show_shop(callback)
    else:
        await callback.answer(
            "❌ Mablag' yetarli emas! Sizga 30 ball kerak.", show_alert=True
        )


@dp.callback_query(F.data == "buy_vip")
async def buy_vip(callback: types.CallbackQuery):
    u = get_user(callback.from_user.id, callback.from_user.first_name)
    if u["vip"]:
        await callback.answer(
            "Sizda allaqachon VIP maqomi bor!", show_alert=True
        )
    elif u["score"] >= 100:
        u["score"] -= 100
        u["vip"] = True
        await callback.answer(
            "👑 Tabriklaymiz, siz VIP bo'ldingiz!", show_alert=True
        )
        await show_shop(callback)
    else:
        await callback.answer(
            "❌ Mablag' yetarli emas! Sizga 100 ball kerak.", show_alert=True
        )


@dp.callback_query(F.data == "back_main")
async def back_to_main(callback: types.CallbackQuery):
    await callback.message.edit_text(
        "O'yin rejimini tanlang:", reply_markup=main_menu_keyboard()
    )


# --- BOT BILAN O'YNASH REJIMI ---
@dp.callback_query(F.data == "play_vs_bot")
async def start_vs_bot(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    vs_bot_games[user_id] = [" "] * 9

    await callback.message.edit_text(
        "🤖 Bot bilan o'yin boshlandi! Siz **❌** siz, yurishingizni tanlang:",
        parse_mode="Markdown",
        reply_markup=get_board_keyboard(vs_bot_games[user_id], prefix="vsbot"),
    )


@dp.callback_query(F.data.startswith("vsbot_"))
async def process_vs_bot_move(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    u = get_user(user_id, callback.from_user.first_name)

    if user_id not in vs_bot_games:
        await callback.answer(
            "O'yin topilmadi, qaytadan /start bosing.", show_alert=True
        )
        return

    idx = int(callback.data.split("_")[1])
    board = vs_bot_games[user_id]

    if board[idx] != " ":
        await callback.answer("Bu katak band!", show_alert=True)
        return

    board[idx] = "❌"

    if check_winner(board, "❌"):
        u["score"] += 10
        del vs_bot_games[user_id]
        await callback.message.edit_text(
            f"🎉 **{u['nickname']} g'olib bo'ldingiz!**\nSizga **+10 ball** berildi!\nJami balingiz: {u['score']}",
            parse_mode="Markdown",
        )
        return

    if " " not in board:
        del vs_bot_games[user_id]
        await callback.message.edit_text("🤝 **Durang!** Birorta ham bo'sh joy qolmadi.")
        return

    empty_indices = [i for i, val in enumerate(board) if val == " "]
    bot_move = random.choice(empty_indices)
    board[bot_move] = "⭕"

    if check_winner(board, "⭕"):
        del vs_bot_games[user_id]
        await callback.message.edit_text(
            "🤖 **Bot g'olib bo'ldi!** Qaytadan urinib ko'ring."
        )
        return

    await callback.message.edit_reply_markup(
        reply_markup=get_board_keyboard(board, prefix="vsbot")
    )


# --- ODAM BILAN O'YNASH (PvP) ---
@dp.callback_query(F.data == "play_pvp")
async def start_pvp(callback: types.CallbackQuery):
    global pvp_queue
    user_id = callback.from_user.id

    if pvp_queue == user_id:
        await callback.answer("Siz allaqachon raqib kutmoqdasiz!", show_alert=True)
        return

    if pvp_queue is None:
        pvp_queue = user_id
        await callback.message.edit_text(
            "⏳ Raqib kutilmoqda... Boshqa o'yinchi ham qo'shilishini kuting."
        )
    else:
        player1 = pvp_queue
        player2 = user_id
        pvp_queue = None

        game_data = {
            "p1": player1,
            "p2": player2,
            "turn": player1,
            "board": [" "] * 9,
        }
        pvp_games[player1] = game_data
        pvp_games[player2] = game_data

        u1 = get_user(player1, "O'yinchi 1")
        u2 = get_user(player2, "O'yinchi 2")

        await bot.send_message(
            player1,
            f"🎮 Raqib topildi: **{u2['nickname']}**!\nSiz **❌** siz. Yurishingizni tanlang:",
            parse_mode="Markdown",
            reply_markup=get_board_keyboard(game_data["board"], prefix="pvp"),
        )
        await bot.send_message(
            player2,
            f"🎮 Raqib topildi: **{u1['nickname']}**!\nSiz **⭕** siz. Raqib yurishini kuting...",
            parse_mode="Markdown",
            reply_markup=get_board_keyboard(game_data["board"], prefix="pvp"),
        )


@dp.callback_query(F.data.startswith("pvp_"))
async def process_pvp_move(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    if user_id not in pvp_games:
        await callback.answer(
            "Faol o'yiningiz yo'q! /start bosing.", show_alert=True
        )
        return

    game = pvp_games[user_id]
    if game["turn"] != user_id:
        await callback.answer("Hozir raqibingizning navbati!", show_alert=True)
        return

    idx = int(callback.data.split("_")[1])
    board = game["board"]

    if board[idx] != " ":
        await callback.answer("Bu katak band!", show_alert=True)
        return

    mark = "❌" if user_id == game["p1"] else "⭕"
    board[idx] = mark
    next_player = game["p2"] if user_id == game["p1"] else game["p1"]
    game["turn"] = next_player

    if check_winner(board, mark):
        u_win = get_user(user_id, "G'olib")
        u_win["score"] += 15
        await bot.send_message(
            user_id,
            f"🎉 **Siz g'olib bo'ldingiz!** (+15 ball)\nJami ball: {u_win['score']}",
        )
        await bot.send_message(next_player, "💔 **Siz yutqazdingiz.**")
        del pvp_games[game["p1"]]
        del pvp_games[game["p2"]]
        return

    if " " not in board:
        await bot.send_message(game["p1"], "🤝 **Durang!**")
        await bot.send_message(game["p2"], "🤝 **Durang!**")
        del pvp_games[game["p1"]]
        del pvp_games[game["p2"]]
        return

    kb = get_board_keyboard(board, prefix="pvp")
    await bot.send_message(
        next_player,
        f"Sizning navbatingiz ({'❌' if mark == '⭕' else '⭕'}):",
        reply_markup=kb,
    )
    await callback.message.edit_text(
        "Raqibingiz yurishini kuting...", reply_markup=kb
    )


async def main():
    logging.basicConfig(level=logging.INFO)
    await start_server()
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
