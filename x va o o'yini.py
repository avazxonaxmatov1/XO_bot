import asyncio
import logging
import os
import random
from aiohttp import web
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

# Bot tokeningizni kiriting
BOT_TOKEN = "8968950657:AAFpx0i43qs6Jr_cpdoDFh1YKJgsFT0oP8g"  # <-- Shu yerga o'zingizning to'liq tokeningizni yozing

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Foydalanuvchilar ballari va o'yin holatlari
user_scores = {}
vs_bot_games = {}


# --- RENDER O'CHIB QOLMASLIGI UCHUN VEB-SERVER ---
async def handle(request):
    return web.Response(text="Bot 24/7 rejimda ishlamoqda!")


async def start_server():
    app = web.Application()
    app.router.add_get("/", handle)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 8080))
    await web.TCPSite(runner, "0.0.0.0", port).start()


# --- TIK-TAK-TOE (X va O) BOT KODI ---
def get_bot_game_keyboard(board):
    builder = []
    for i in range(3):
        row = []
        for j in range(3):
            idx = i * 3 + j
            text = board[idx] if board[idx] != " " else " "
            row.append(
                InlineKeyboardButton(text=text, callback_data=f"vsbot_{idx}")
            )
        builder.append(row)
    return InlineKeyboardMarkup(inline_keyboard=builder)


def check_winner(b, mark):
    win_conditions = [
        [0, 1, 2],
        [3, 4, 5],
        [6, 7, 8],  # Qatorlar
        [0, 3, 6],
        [1, 4, 7],
        [2, 5, 8],  # Ustunlar
        [0, 4, 8],
        [2, 4, 6],  # Diagonallar
    ]
    return any(all(b[i] == mark for i in pos) for pos in win_conditions)


@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    if user_id not in user_scores:
        user_scores[user_id] = 0

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🤖 Bot bilan o'ynash (+10 ball)",
                    callback_data="play_vs_bot",
                )
            ],
            [
                InlineKeyboardButton(
                    text="🏆 Mening ballarim", callback_data="my_score"
                )
            ],
        ]
    )
    await message.answer(
        f"Salom, {message.from_user.first_name}!\n"
        f"X va O o'yiniga xush kelibsiz!\n"
        f"Boshqa odamni kutmasdan bot bilan o'ynashingiz mumkin.",
        reply_markup=kb,
    )


@dp.callback_query(F.data == "my_score")
async def show_score(callback: types.CallbackQuery):
    score = user_scores.get(callback.from_user.id, 0)
    await callback.answer(f"Sizning balingiz: {score}", show_alert=True)


@dp.callback_query(F.data == "play_vs_bot")
async def start_vs_bot(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    vs_bot_games[user_id] = [" "] * 9  # Bo'sh taxta

    await callback.message.edit_text(
        "Bot bilan o meyorida o'yin boshlandi! Siz **X** siz, yurishingizni tanlang:",
        parse_mode="Markdown",
        reply_markup=get_bot_game_keyboard(vs_bot_games[user_id]),
    )


@dp.callback_query(F.data.startswith("vsbot_"))
async def process_vs_bot_move(callback: types.CallbackQuery):
    user_id = callback.from_user.id
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

    # O'yinchining yurishi (X)
    board[idx] = "❌"

    if check_winner(board, "❌"):
        user_scores[user_id] = user_scores.get(user_id, 0) + 10
        del vs_bot_games[user_id]
        await callback.message.edit_text(
            f"🎉 **Siz g'olib bo'ldingiz!**\nSizga **+10 ball** berildi!\nJami balingiz: {user_scores[user_id]}",
            parse_mode="Markdown",
        )
        return

    if " " not in board:
        del vs_bot_games[user_id]
        await callback.message.edit_text("🤝 **Durang!** Birorta ham bo'sh joy qolmadi.")
        return

    # Botning yurishi (O)
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
        reply_markup=get_bot_game_keyboard(board)
    )


async def main():
    logging.basicConfig(level=logging.INFO)
    await start_server()  # Render uchishining oldini oluvchi veb-server
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
