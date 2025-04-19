# handlers/funny/russian_roulette.py

import json
import asyncio
import random
from telegram import Update
from telegram.ext import ContextTypes
from datetime import datetime

from utils.users import get_user_id_by_username
from core.check_group_chat import only_group_chats

LOBBY_DB = "database/roulette_lobbies.json"
SETTINGS_DB = "database/roulette_settings.json"


# === Авто-таймер хода ===
async def auto_shoot_timeout(chat_id, context, player_id):
    await asyncio.sleep(60)
    lobby = context.chat_data.get(chat_id)
    if not lobby or lobby.get("waiting") != player_id:
        return

    await context.bot.send_message(
        chat_id=chat_id,
        text=f"⏱ Время вышло! Игрок <a href='tg://user?id={player_id}'>@{lobby['player_names'][player_id]}</a> сам стреляет в себя",
        parse_mode="HTML"
    )
    await shootme_forced(chat_id, context, player_id)


# === Принудительный выстрел в себя ===
async def shootme_forced(chat_id, context, user_id):
    lobby = context.chat_data.get(chat_id)
    if not lobby or lobby["state"] != "active":
        return

    if not lobby["bullets"]:
        return

    lobby["waiting"] = None
    result = lobby["bullets"].pop(0)
    if result == "blank":
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"🔫 <a href='tg://user?id={user_id}'>@{lobby['player_names'][user_id]}</a> стреляет в себя — <b>Промах!</b>",
            parse_mode="HTML"
        )
        await show_status(chat_id, context, lobby)
        lobby["waiting"] = user_id
        asyncio.create_task(auto_shoot_timeout(chat_id, context, user_id))
    else:
        lobby["dead"].append(user_id)
        lobby["alive"].remove(user_id)
        lobby["bullets"] = lobby["original_bullets"].copy()
        random.shuffle(lobby["bullets"])
        if lobby["current_index"] >= len(lobby["alive"]):
            lobby["current_index"] = 0

        await context.bot.send_message(
            chat_id=chat_id,
            text=f"💥 <a href='tg://user?id={user_id}'>@{lobby['player_names'][user_id]}</a> убит!",
            parse_mode="HTML"
        )
        await show_status(chat_id, context, lobby)
        await next_turn_or_end(chat_id, context, lobby)


# === Завершение игры ===
@only_group_chats
async def endgame_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    chat_id = str(message.chat_id)
    user_id = str(message.from_user.id)

    lobby = context.chat_data.get(chat_id)
    if not lobby:
        return await message.reply_text("Нет активной игры для завершения.")

    if lobby["host"] != user_id:
        return await message.reply_text("Только хост может завершить игру!")

    del context.chat_data[chat_id]
    await message.reply_text("❌ Игра была завершена хостом.")


# === Проверка: ход игрока ===
def is_player_turn(chat_id, context, user_id):
    lobby = context.chat_data.get(chat_id)
    return (
        lobby and lobby.get("state") == "active"
        and lobby.get("waiting") == user_id
    )


# === Показ статуса игры ===
async def show_status(chat_id, context, lobby):
    alive = [f"<a href='tg://user?id={pid}'>@{lobby['player_names'][pid]}</a>" for pid in lobby['alive']]
    dead = [f"<a href='tg://user?id={pid}'>@{lobby['player_names'][pid]}</a>" for pid in lobby['dead']]
    bullets = lobby.get("bullets", [])
    blanks = bullets.count("blank")
    live = bullets.count("live")

    await context.bot.send_message(
        chat_id=chat_id,
        text=(
            f"💥 Патроны: {blanks} холостых, {live} боевых\n"
            f"🙂 Живые: {len(alive)} — {', '.join(alive)}\n"
            f"☠️ Мертвые: {len(dead)} — {', '.join(dead) if dead else '—'}"
        ),
        parse_mode="HTML"
    )


# === Следующий ход или конец игры ===
async def next_turn_or_end(chat_id, context, lobby):
    if len(lobby["alive"]) == 1:
        winner_id = lobby["alive"][0]
        winner_name = lobby["player_names"].get(winner_id, winner_id)
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"🏆 Победитель: <a href='tg://user?id={winner_id}'>@{winner_name}</a>",
            parse_mode="HTML"
        )
        del context.chat_data[chat_id]
    else:
        current_player = lobby["alive"][lobby["current_index"]]
        lobby["waiting"] = current_player
        current_name = lobby["player_names"].get(current_player, "Игрок")
        await context.bot.send_message(
            chat_id=chat_id,
            text=(
                f"🔁 Сейчас ходит: <a href='tg://user?id={current_player}'>@{current_name}</a>\n"
                f"Команды: \n<code>!shootme</code> или <code>!shoot @username</code> или ответом на сообщение\n"
                f"⏳ У тебя 60 секунд на ход!"
            ),
            parse_mode="HTML"
        )
        asyncio.create_task(auto_shoot_timeout(chat_id, context, current_player))


# === Ход: выстрел в себя ===
@only_group_chats
async def shootme_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    chat_id = str(message.chat_id)
    user_id = str(message.from_user.id)

    if not is_player_turn(chat_id, context, user_id):
        return await message.reply_text("⛔ Сейчас не ваш ход!")

    lobby = context.chat_data.get(chat_id)
    lobby["waiting"] = None  # сбрасываем таймер немедленно
    await shootme_forced(chat_id, context, user_id)


# === Ход: выстрел в другого ===
@only_group_chats
async def shoot_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    chat_id = str(message.chat_id)
    user_id = str(message.from_user.id)

    if not is_player_turn(chat_id, context, user_id):
        return await message.reply_text("⛔ Сейчас не ваш ход!")

    lobby = context.chat_data.get(chat_id)
    lobby["waiting"] = None  # сбрасываем таймер перед действиями

    if message.reply_to_message:
        target_user = message.reply_to_message.from_user
        target_user_id = str(target_user.id)
    else:
        parts = message.text.strip().split()
        if len(parts) < 2 or not parts[1].startswith("@"):
            return await message.reply_text("Укажите цель через @username или ответом на сообщение.")

        username = parts[1][1:]
        target_user_id = get_user_id_by_username(username)
        if not target_user_id:
            return await message.reply_text("❌ Игрок с таким именем не найден среди живых участников.")

    if target_user_id not in lobby["alive"]:
        return await message.reply_text("Игрок уже мертв или не участвует в игре.")

    result = lobby["bullets"].pop(0)
    if result == "blank":
        await context.bot.send_message(
            chat_id=chat_id,
            text=(
                f"🔫 <a href='tg://user?id={user_id}'>@{lobby['player_names'][user_id]}</a> выстрелил в <a href='tg://user?id={target_user_id}'>@{lobby['player_names'][target_user_id]}</a> — <b>Промах!</b>"
            ),
            parse_mode="HTML"
        )
        lobby["current_index"] = (lobby["current_index"] + 1) % len(lobby["alive"])
    else:
        lobby["dead"].append(target_user_id)
        lobby["alive"].remove(target_user_id)
        lobby["bullets"] = lobby["original_bullets"].copy()
        random.shuffle(lobby["bullets"])
        await context.bot.send_message(
            chat_id=chat_id,
            text=(
                f"🔫 <a href='tg://user?id={user_id}'>@{lobby['player_names'][user_id]}</a> выстрелил в <a href='tg://user?id={target_user_id}'>@{lobby['player_names'][target_user_id]}</a> — 💀 <b>Убит!</b>"
            ),
            parse_mode="HTML"
        )
        if lobby["current_index"] >= len(lobby["alive"]):
            lobby["current_index"] = 0

    await show_status(chat_id, context, lobby)
    await next_turn_or_end(chat_id, context, lobby)


# === Хендлер начала игры !roulette ===
@only_group_chats
async def roulette_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    chat_id = str(message.chat_id)
    user_id = str(message.from_user.id)

    if chat_id in context.chat_data and context.chat_data[chat_id].get("state") in ["lobby", "active"]:
        return await message.reply_text("В этой группе уже запущена игра!")

    context.chat_data[chat_id] = {
        "state": "lobby",
        "host": user_id,
        "players": [user_id],
        "player_names": {user_id: message.from_user.first_name},
        "joined_time": datetime.now().timestamp()
    }

    await message.reply_html(
        f"🎲 <b>{message.from_user.first_name}</b> предлагает сыграть в <b>Русскую рулетку!</b>\n\n"
        f"Чтобы присоединиться, напишите <code>!join</code>\n"
        f"Хост может начать игру раньше командой <code>!startgame</code>\n"
        f"⏳ У вас есть 2 минуты на регистрацию!"
    )


# === Хендлер подключения к игре !join ===
@only_group_chats
async def join_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    chat_id = str(message.chat_id)
    user = message.from_user
    user_id = str(user.id)

    lobby = context.chat_data.get(chat_id)
    if not lobby or lobby.get("state") != "lobby":
        return

    if user_id in lobby["players"]:
        return await message.reply_text("Вы уже в игре!")

    lobby["players"].append(user_id)
    lobby["player_names"][user_id] = user.first_name

    await message.reply_html(f"✅ <b>{user.first_name}</b> присоединился к игре!")


# === Хендлер запуска игры !startgame ===
@only_group_chats
async def start_game_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    chat_id = str(message.chat_id)
    user_id = str(message.from_user.id)

    lobby = context.chat_data.get(chat_id)
    if not lobby or lobby.get("state") != "lobby":
        return await message.reply_text("Нет активной лобби для запуска.")

    if lobby["host"] != user_id:
        return await message.reply_text("Только хост может начать игру.")

    if len(lobby["players"]) < 2:
        del context.chat_data[chat_id]
        return await message.reply_text("Недостаточно игроков. Игра отменена.")

    blanks = 5
    lives = 1
    bullets = ["blank"] * blanks + ["live"] * lives
    random.shuffle(bullets)

    random.shuffle(lobby["players"])
    lobby.update({
        "state": "active",
        "alive": lobby["players"].copy(),
        "dead": [],
        "bullets": bullets,
        "original_bullets": bullets.copy(),
        "current_index": 0,
        "waiting": None
    })

    await message.reply_text("💥 Игра начинается!")
    await show_status(chat_id, context, lobby)
    await next_turn_or_end(chat_id, context, lobby)
