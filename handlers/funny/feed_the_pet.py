import sqlite3
import random
import logging
from datetime import datetime, timedelta
from telegram import Update
from telegram.ext import ContextTypes
from core.check_group_chat import only_group_chats
from utils.users import get_user_id_by_username, register_user
from handlers.admin.admin_access import has_access
from handlers.admin.moderation_db import get_user_max_role_level
from telegram.helpers import mention_html
from telegram.constants import ParseMode

DB_PATH = 'database/whale_game.db'


# ====== Database Initialization ======
def init_whale_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS players (
            chat_id INTEGER,
            user_id INTEGER,
            pet_name TEXT,
            weight REAL DEFAULT 0,
            balance REAL DEFAULT 0,
            last_feed TEXT,
            PRIMARY KEY(chat_id, user_id)
        )
    """
    )
    c.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            chat_id INTEGER,
            key TEXT,
            value TEXT,
            PRIMARY KEY(chat_id, key)
        )
    """
    )
    c.execute("""
        CREATE TABLE IF NOT EXISTS game_admins (
            chat_id INTEGER,
            user_id INTEGER,
            PRIMARY KEY(chat_id, user_id)
        )
    """
    )
    conn.commit()
    conn.close()


init_whale_db()


# ====== Helper Functions ======
def get_setting(chat_id: int, key: str, default=None):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT value FROM settings WHERE chat_id=? AND key=?", (chat_id, key))
    row = c.fetchone()
    conn.close()
    return row[0] if row else default


def set_setting(chat_id: int, key: str, value: str):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("REPLACE INTO settings(chat_id, key, value) VALUES(?,?,?)", (chat_id, key, value))
    conn.commit()
    conn.close()


def is_game_admin(chat_id: int, user_id: int):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT 1 FROM game_admins WHERE chat_id=? AND user_id=?", (chat_id, user_id))
    ok = c.fetchone() is not None
    conn.close()
    return ok


# ====== Commands ======
@only_group_chats
async def whale_admin_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Назначить игрового администратора: !whale-admin @user/ID"""
    msg = update.message
    parts = msg.text.strip().split(maxsplit=1)
    if len(parts) < 2:
        return await msg.reply_text("❔ Использование: !whale-admin '@username или ID'")
    arg = parts[1]
    owner = await context.bot.get_chat_member(update.effective_chat.id, update.effective_user.id)
    if owner.status != 'creator':
        return await msg.reply_text("⛔ Только владелец может назначать админов игры.")
    if arg.startswith('@'):
        uid = get_user_id_by_username(arg[1:])
        if not uid:
            return await msg.reply_text("❌ Пользователь не найден.")
    elif arg.isdigit():
        uid = int(arg)
    else:
        return await msg.reply_text("❌ Неверный формат. Укажите @username или ID.")
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("REPLACE INTO game_admins(chat_id, user_id) VALUES(?,?)", (update.effective_chat.id, uid))
    conn.commit()
    conn.close()
    await msg.reply_text(f"✅ Игровой админ назначен: {arg}")


@only_group_chats
async def whale_admins_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Вывести список игровых администраторов: !whale-admins"""
    msg = update.message
    chat_id = update.effective_chat.id
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT user_id FROM game_admins WHERE chat_id=?", (chat_id,))
    rows = c.fetchall()
    conn.close()
    if not rows:
        return await msg.reply_text("❌ Пока нет админов игры.")
    mentions = []
    for (uid,) in rows:
        try:
            member = await context.bot.get_chat_member(chat_id, uid)
            mentions.append(mention_html(uid, member.user.first_name))
        except:
            mentions.append(f"ID {uid}")
    await msg.reply_text("👑 Игровые админы: " + ', '.join(mentions), parse_mode=ParseMode.HTML)


@only_group_chats
async def whale_admin_remove(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Снять игрового админа: !whale-admin-remove @user/ID"""
    msg = update.message
    parts = msg.text.strip().split(maxsplit=1)
    if len(parts) < 2:
        return await msg.reply_text("❔ Использование: !whale-admin-remove '@username или ID'")
    arg = parts[1]
    owner = await context.bot.get_chat_member(update.effective_chat.id, update.effective_user.id)
    if owner.status != 'creator':
        return await msg.reply_text("⛔ Только владелец может снимать админов игры.")
    if arg.startswith('@'):
        uid = get_user_id_by_username(arg[1:])
        if not uid:
            return await msg.reply_text("❌ Пользователь не найден.")
    elif arg.isdigit():
        uid = int(arg)
    else:
        return await msg.reply_text("❌ Неверный формат аргумента.")
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM game_admins WHERE chat_id=? AND user_id=?", (update.effective_chat.id, uid))
    conn.commit()
    conn.close()
    await msg.reply_text(f"🗑️ Игровой админ удалён: {arg}")


@only_group_chats
async def set_game_setting(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """!whale-set <key> <value>"""
    msg = update.message
    parts = msg.text.strip().split(maxsplit=2)
    if len(parts) < 3:
        return await msg.reply_text("❔ Использование: !whale-set <ключ> <значение>")
    key, value = parts[1], parts[2]
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    member = await context.bot.get_chat_member(chat_id, user_id)
    if member.status != 'creator' and not is_game_admin(chat_id, user_id):
        return await msg.reply_text("⛔ Нет прав менять настройки игры.")

    valid_keys = {'cooldown','gain_min','gain_max','loss_min','loss_max','chance','coeff','object_name'}
    if key not in valid_keys:
        return await msg.reply_text("❌ Неверный ключ. Допустимые: " + ', '.join(valid_keys))

    # Validate numeric relationships
    try:
        if key in ('gain_min','gain_max','loss_min','loss_max','chance','coeff'):
            num = int(value)
            if num < 0:
                raise ValueError
        prefix = ''
        # For relational keys, fetch counterpart
        if key == 'gain_min':
            gm = int(get_setting(chat_id,'gain_max','10'))
            if num > gm:
                return await msg.reply_text(f"❌ gain_min ({num}) не может быть больше gain_max ({gm}).")
        if key == 'gain_max':
            gn = int(get_setting(chat_id,'gain_min','1'))
            if num < gn:
                return await msg.reply_text(f"❌ gain_max ({num}) не может быть меньше gain_min ({gn}).")
        if key == 'loss_min':
            lm = int(get_setting(chat_id,'loss_max','5'))
            if num > lm:
                return await msg.reply_text(f"❌ loss_min ({num}) не может быть больше loss_max ({lm}).")
        if key == 'loss_max':
            ln = int(get_setting(chat_id,'loss_min','1'))
            if num < ln:
                return await msg.reply_text(f"❌ loss_max ({num}) не может быть меньше loss_min ({ln}).")
        if key == 'chance' and not (0 <= num <= 100):
            return await msg.reply_text("❗ chance должен быть от 0 до 100.")
    except ValueError:
        return await msg.reply_text("❗ Значение должно быть целым числом.")

    # Save setting
    set_setting(chat_id, key, value)
    await msg.reply_text(f"⚙️ Настройка <b>{key}</b> установлена в <b>{value}</b>", parse_mode=ParseMode.HTML)


@only_group_chats
async def set_whale_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    parts = msg.text.strip().split(maxsplit=2)
    if len(parts) < 2:
        return await msg.reply_text("❔ Использование: !whale-name НовоеИмя или !whale-name @user НовоеИмя")
    chat_id = update.effective_chat.id
    caller_id = update.effective_user.id
    if len(parts) == 2:
        target_id = caller_id
        new_name = parts[1].strip()
    else:
        arg, new_name = parts[1], parts[2].strip()
        if arg.startswith('@'):
            target_id = get_user_id_by_username(arg[1:])
            if not target_id:
                return await msg.reply_text("❌ Пользователь не найден.")
        elif arg.isdigit():
            target_id = int(arg)
        else:
            return await msg.reply_text("❌ Неверный формат. Используйте @username или ID.")
    if not 1 <= len(new_name) <= 16 or '\n' in new_name:
        return await msg.reply_text("❗ Имя питомца должно быть 1–16 символов без переносов.")
    if target_id != caller_id:
        member = await context.bot.get_chat_member(chat_id, caller_id)
        if member.status != 'creator' and not is_game_admin(chat_id, caller_id):
            return await msg.reply_text("⛔ Нет прав менять имя другого питомца.")
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT 1 FROM players WHERE chat_id=? AND user_id=?", (chat_id, target_id))
    if not c.fetchone():
        conn.close()
        return await msg.reply_text("❗ Питомец не зарегистрирован. Используйте !whale 'Имя питомца'.")
    c.execute("UPDATE players SET pet_name=? WHERE chat_id=? AND user_id=?", (new_name, chat_id, target_id))
    conn.commit()
    conn.close()
    await msg.reply_text(
        f"{'✅ Ваш питомец' if target_id==caller_id else f'✅ Питомец пользователя'} успешно переименован в <b>{new_name}</b>",
        parse_mode=ParseMode.HTML
    )


@only_group_chats
async def register_whale(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    parts = msg.text.strip().split(maxsplit=1)
    if len(parts) < 2:
        return await msg.reply_text("❔ Использование: !whale 'Имя питомца'")
    name = parts[1].strip()
    if not 1 <= len(name) <= 16 or '\n' in name:
        return await msg.reply_text("❗ Имя питомца должно быть от 1 до 16 символов без переносов.")
    chat_id = update.effective_chat.id
    uid = update.effective_user.id
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT 1 FROM players WHERE chat_id=? AND user_id=?", (chat_id, uid))
    if c.fetchone():
        conn.close()
        return await msg.reply_text("❗ У вас уже есть питомец. Используйте !whale-name для переименования.")
    c.execute("INSERT INTO players(chat_id,user_id,pet_name,weight,balance,last_feed) VALUES(?,?,?,?,?,?)",
              (chat_id, uid, name, 0, 0, None))
    conn.commit()
    conn.close()
    await msg.reply_text(f"❗ Ваш питомец '{name}' зарегистрирован! Используйте !feed для кормёжки.")


@only_group_chats
async def feed_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    chat_id = update.effective_chat.id
    uid = update.effective_user.id
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT pet_name,weight,balance,last_feed FROM players WHERE chat_id=? AND user_id=?", (chat_id, uid))
    row = c.fetchone()
    if not row:
        conn.close()
        return await msg.reply_text("❗ У вас нет питомца. Зарегистрируйте через !whale 'Имя питомца'")
    name, weight, balance, last_feed = row
    now = datetime.utcnow()

    # Parse cooldown combination
    raw_cd = get_setting(chat_id, 'cooldown', '24h') or '24h'
    total_sec = 0
    for token in raw_cd.split():
        if token.endswith('h') and token[:-1].isdigit():
            total_sec += int(token[:-1])*3600
        elif token.endswith('m') and token[:-1].isdigit():
            total_sec += int(token[:-1])*60
        elif token.endswith('s') and token[:-1].isdigit():
            total_sec += int(token[:-1])
        elif token.isdigit():
            total_sec += int(token)*3600
    cd_delta = timedelta(seconds=total_sec)

    if last_feed:
        last = datetime.fromisoformat(last_feed)
        if now < last + cd_delta:
            rem = last + cd_delta - now
            hrs = rem.seconds//3600
            mins = (rem.seconds%3600)//60
            secs = rem.seconds%60
            conn.close()
            return await msg.reply_text(f"⏳ Ждите ещё: {hrs} ч {mins} мин {secs} сек.")

    # Settings
    gain_min = int(get_setting(chat_id,'gain_min','1'))
    gain_max = int(get_setting(chat_id,'gain_max','10'))
    loss_min = int(get_setting(chat_id,'loss_min','1'))
    loss_max = int(get_setting(chat_id,'loss_max','5'))
    chance = int(get_setting(chat_id,'chance','50'))
    coeff = int(get_setting(chat_id,'coeff','2'))

    # Outcome
    if random.randint(1,100) <= chance:
        delta = random.randint(gain_min, gain_max)
        weight += delta
        balance += delta//coeff

        if delta > gain_max * 0.7:
            text = f"😲 Ого, {name} сел роскошную еду, и поправился на {delta} кг и вы получили {delta // coeff} сердечек ❤️"
        else:
            text = f"😋 Отлично! {name} поправился на {delta} кг и вы заработали {delta // coeff} сердечек ❤️"
    else:
        delta = random.randint(loss_min, loss_max)
        weight = max(0, weight-delta)

        if delta > loss_max * 0.7:
            text = f"🥴 Упс, {name} сел отвратительную еду, и похудел на {delta} кг."
        else:
            text = f"🫤 Упс, {name} сел плохую еду, и похудел на {delta} кг."

    c.execute("UPDATE players SET weight=?,balance=?,last_feed=? WHERE chat_id=? AND user_id=?",
              (weight, balance, now.isoformat(), chat_id, uid))
    conn.commit()
    conn.close()
    await msg.reply_text(text)


@only_group_chats
async def leaders_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # !leaders
    msg = update.message
    chat_id = update.effective_chat.id
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT user_id, pet_name, weight FROM players WHERE chat_id=? ORDER BY weight DESC LIMIT 10", (chat_id,))
    rows = c.fetchall()
    conn.close()
    if not rows:
        return await msg.reply_text("👤 Нет игроков.")
    lines = []
    for idx, (uid, name, wt) in enumerate(rows, 1):
        try:
            member = await context.bot.get_chat_member(chat_id, uid)
            mention = mention_html(uid, member.user.first_name)
        except:
            mention = mention_html(uid, f"id{uid}")
        if idx == 1:
            lines.append(f"🏆 Место в рейтинге 1: <b>{name}</b>")
            lines.append(f"⚖️ Вес: {wt} кг")
            lines.append(f"👤 Владелец: {mention}\n")
        else:
            lines.append(f"🎖️ Место в рейтинге {idx}: <b>{name}</b>")
            lines.append(f"⚖️ Вес: {wt} кг")
            lines.append(f"👤 Владелец: {mention}\n")
    await msg.reply_text("\n".join(lines), parse_mode=ParseMode.HTML)


@only_group_chats
async def info_whale(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать текущие настройки игры: !info-whale"""
    chat_id = update.effective_chat.id
    # Default values
    defaults = {
        'cooldown': '24h',
        'gain_min': '1', 'gain_max': '10',
        'loss_min': '1', 'loss_max': '5',
        'chance': '50', 'coeff': '2',
        'object_name': 'Кит'
    }
    # Fetch settings
    cfg = {}
    for key, defval in defaults.items():
        cfg[key] = get_setting(chat_id, key, defval)
    # Human-readable cooldown
    total_sec = 0
    for token in cfg['cooldown'].split():
        if token.endswith('h') and token[:-1].isdigit(): total_sec += int(token[:-1]) * 3600
        elif token.endswith('m') and token[:-1].isdigit(): total_sec += int(token[:-1]) * 60
        elif token.endswith('s') and token[:-1].isdigit(): total_sec += int(token[:-1])
        elif token.isdigit(): total_sec += int(token) * 3600
    cd = timedelta(seconds=total_sec)
    hrs, rem = divmod(cd.seconds, 3600)
    mins, secs = divmod(rem, 60)
    cooldown_str = f"{hrs}ч {mins}м {secs}с"
    # Build message
    text = (
        f"🏷 <b>Параметры игры '{cfg['object_name']}'</b> 🏷\n"
        f"⏱ <b>Кулдаун:</b> {cooldown_str}\n"
        f"⚖️ <b>Успех:</b> {cfg['gain_min']}–{cfg['gain_max']} кг\n"
        f"📉 <b>Неудача:</b> {cfg['loss_min']}–{cfg['loss_max']} кг\n"
        f"🎯 <b>Шанс успеха:</b> {cfg['chance']}%\n"
        f"❤️ <b>Коэффициент сердец:</b> 1 сердце за {cfg['coeff']} кг\n"
        f"🐳 <b>Объект:</b> {cfg['object_name']}"
    )
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)


@only_group_chats
async def profile_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    chat_id = update.effective_chat.id
    uid = update.effective_user.id
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT pet_name,weight,balance FROM players WHERE chat_id=? AND user_id=?", (chat_id, uid))
    row = c.fetchone()
    if not row:
        conn.close()
        return await msg.reply_text("❗ У вас нет питомца. Зарегистрируйте через !whale 'Имя питомца'")
    name, weight, balance = row
    c.execute("SELECT COUNT(*)+1 FROM players WHERE chat_id=? AND weight>?", (chat_id, weight))
    rank = c.fetchone()[0]
    conn.close()
    text = (
        f"📋 <b>Ваш профиль:</b>\n"
        f"🐳 Питомец: <b>{name}</b>\n"
        f"⚖️ Вес: <b>{weight}</b> кг\n"
        f"🏆 Место в рейтинге: <b>{rank}</b>\n"
        f"❤️ Сердца: <b>{balance}</b>"
    )
    await msg.reply_text(text, parse_mode=ParseMode.HTML)
