import re
import datetime
import sqlite3
import os
from asyncio import get_running_loop, create_task, sleep
from telegram import Update, ChatMember
from telegram.constants import ParseMode
from telegram.ext import ContextTypes, MessageHandler, filters
from telegram.helpers import mention_html

from handlers.admin.admin_access import has_access
from handlers.admin.moderation_db import get_user_max_role_level
from utils.users import get_user_id_by_username
from core.check_group_chat import only_group_chats

# Флаг отладки
DEBUG = True


# Функция для парсинга строкового срока бана.
def parse_duration_string(duration_str: str) -> datetime.timedelta:
    """Парсинг строкового срока бана в timedelta."""
    cleaned = duration_str.lower().replace(" ", "")
    time_pattern = re.compile(r'(\d+(?:r|mo|d|h|m|s))')
    matches = time_pattern.findall(cleaned)
    if not matches:
        raise ValueError("Неверный формат срока бана")
    total_delta = datetime.timedelta()
    for item in matches:
        m = re.match(r'^(\d+)(r|mo|d|h|m|s)$', item)
        if not m:
            raise ValueError("Неверная единица времени")
        amount, unit = int(m.group(1)), m.group(2)
        if unit == 'r':  # год = 365 дней
            delta = datetime.timedelta(days=365 * amount)
        elif unit == 'mo':  # месяц = 32 дня
            if amount > 12:
                raise ValueError("Неверное число месяцев (максимум 12)")
            delta = datetime.timedelta(days=32 * amount)
        elif unit == 'd':
            delta = datetime.timedelta(days=amount)
        elif unit == 'h':
            delta = datetime.timedelta(hours=amount)
        elif unit == 'm':
            delta = datetime.timedelta(minutes=amount)
        elif unit == 's':
            if amount >= 60:
                raise ValueError("Неверное число секунд (максимум 59)")
            delta = datetime.timedelta(seconds=amount)
        else:
            raise ValueError("Неверная единица времени")
        total_delta += delta
    return total_delta


# Функция для объединения списка единиц в строку с пробелами.
def format_duration(units: list) -> str:
    return ' '.join(units)


# Функция для преобразования единиц в читаемый формат (полный текст на русском).
def format_duration_full(formatted: str) -> str:
    """Преобразование к читаемому виду (русский язык)."""
    tokens = formatted.split()
    mapping = {
        'r': lambda n: f"{n} " + ("год" if n == 1 else ("года" if 2 <= n <= 4 else "лет")),
        'mo': lambda n: f"{n} " + ("месяц" if n == 1 else ("месяца" if 2 <= n <= 4 else "месяцев")),
        'd': lambda n: f"{n} " + ("день" if n == 1 else ("дня" if 2 <= n <= 4 else "дней")),
        'h': lambda n: f"{n} " + ("час" if n == 1 else ("часа" if 2 <= n <= 4 else "часов")),
        'm': lambda n: f"{n} " + ("минута" if n == 1 else ("минуты" if 2 <= n <= 4 else "минут")),
        's': lambda n: f"{n} " + ("секунда" if n == 1 else ("секунды" if 2 <= n <= 4 else "секунд")),
    }
    parts = []
    for token in tokens:
        m = re.match(r'^(\d+)(r|mo|d|h|m|s)$', token)
        if m:
            n, u = int(m.group(1)), m.group(2)
            parts.append(mapping[u](n))
    return ' '.join(parts)


# Функция для автоматического разбана через задержку.
async def unban_after_delay(context: ContextTypes.DEFAULT_TYPE, chat_id: int, user_id: int, delay: int):
    await sleep(delay)
    try:
        await context.bot.unban_chat_member(chat_id, user_id, only_if_banned=True)
        if DEBUG:
            print(f"[DEBUG] Пользователь {user_id} разблокирован автоматически через {delay} секунд.")
    except Exception as e:
        if DEBUG:
            print(f"[DEBUG] Ошибка при автоматическом разбане {user_id}: {e}")
    # Здесь можно также удалить запись из таблицы банов, если потребуется.


# Функции для работы с базой банов (bans.db).
# Расширенная схема для хранения:
#   - Данных группы
#   - Данных администратора
#   - Данных забаненного
#   - Причины и срока бана (в человекочитаемом виде)
def init_bans_db():
    """Инициализация SQLite для банов."""
    db_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'database')
    os.makedirs(db_dir, exist_ok=True)
    db_path = os.path.join(db_dir, 'bans.db')
    with sqlite3.connect(db_path) as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS bans (
                chat_id INTEGER,
                group_name TEXT,
                admin_user_id INTEGER,
                admin_username TEXT,
                admin_first_name TEXT,
                admin_last_name TEXT,
                banned_user_id INTEGER,
                banned_username TEXT,
                banned_first_name TEXT,
                banned_last_name TEXT,
                reason TEXT,
                duration TEXT,
                unban_time TEXT,
                PRIMARY KEY (chat_id, banned_user_id)
            )
        ''')
        conn.commit()


def save_ban(
    chat_id: int, group_name: str,
    admin_user_id: int, admin_username: str, admin_first_name: str, admin_last_name: str,
    banned_user_id: int, banned_username: str, banned_first_name: str, banned_last_name: str,
    reason: str, duration: str, unban_time: str
):
    """Сохранение инфо о бане."""
    db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'database', 'bans.db')
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            '''INSERT OR REPLACE INTO bans(
                chat_id, group_name, admin_user_id, admin_username, admin_first_name, admin_last_name,
                banned_user_id, banned_username, banned_first_name, banned_last_name, reason, duration, unban_time
            ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
            (
                chat_id, group_name, admin_user_id, admin_username, admin_first_name, admin_last_name,
                banned_user_id, banned_username, banned_first_name, banned_last_name, reason, duration, unban_time
            )
        )
        conn.commit()


# Функция для определения цели бана.
async def resolve_target(message: Update.message, context: ContextTypes.DEFAULT_TYPE, chat) -> object:
    if message.reply_to_message:
        if DEBUG:
            print(f"[DEBUG] Цель выбрана через reply: {message.reply_to_message.from_user}")
        return message.reply_to_message.from_user
    tokens = message.text.split(maxsplit=2)
    if len(tokens) < 2:
        return None
    potential_target = tokens[1]
    if potential_target.startswith('@'):
        username_clean = potential_target.lstrip('@').strip().lower()
        if DEBUG:
            print(f"[DEBUG] Обнаружено имя с '@': '{potential_target}', очищенное: '{username_clean}'")
        try:
            loop = get_running_loop()
            target_id = await loop.run_in_executor(None, get_user_id_by_username, username_clean)
            if DEBUG:
                print(f"[DEBUG] Результат get_user_id_by_username: {target_id}")
            if not target_id:
                return None
            member_obj = await context.bot.get_chat_member(chat.id, target_id)
            return member_obj.user
        except Exception as e:
            if DEBUG:
                print(f"[DEBUG] Ошибка при получении пользователя по username: {e}")
            return None
    else:
        try:
            target_id = int(potential_target)
            if DEBUG:
                print(f"[DEBUG] Принят числовой ID: {target_id}")
            member_obj = await context.bot.get_chat_member(chat.id, target_id)
            return member_obj.user
        except Exception as e:
            if DEBUG:
                print(f"[DEBUG] Ошибка при получении пользователя по ID: {e}")
            return None


# Функция для извлечения причины и срока бана.
def extract_reason_and_duration(text: str):
    """Извлечение причины и сроков из текста команды."""
    time_pattern = re.compile(r'(\d+(?:r|mo|d|h|m|s))', re.IGNORECASE)
    matches = list(time_pattern.finditer(text.replace('\n', ' ')))
    if not matches:
        raise ValueError("Не указан корректный срок бана (например: 7d, 1r2mo, 3h30m)")
    units = [m.group(1) for m in matches]
    reason = text
    for u in units:
        reason = reason.replace(u, '')
    reason = reason.strip() or 'Без причины'
    delta = parse_duration_string(''.join(units))
    formatted_units = ' '.join(units)
    return reason, formatted_units, delta


# Основная функция обработки команды !ban.
@only_group_chats
async def ban_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    if not message:
        return
    chat = update.effective_chat
    invoker = update.effective_user

    # 0. Проверка права бана
    try:
        member = await context.bot.get_chat_member(chat.id, invoker.id)
        is_owner = (member.status == ChatMember.OWNER)
    except Exception as e:
        await message.reply_text(f"❌ Не удалось проверить ваши права: {e}")
        return
    if not is_owner and not has_access(chat.id, invoker.id, "!ban"):
        await message.reply_text("⛔ У вас нет прав для бана.")
        return

    # 1. Определяем цель
    target_user = await resolve_target(message, context, chat)
    if not target_user:
        await message.reply_text("❌ Укажите пользователя (reply, @username или ID)")
        return

    # 2. Извлекаем причину и срок
    parts = message.text.split(maxsplit=2)
    if len(parts) < 3:
        await message.reply_text("❌ Укажите причину и срок бана. Пример: !ban @user Оскорбления 7d")
        return
    reason, formatted_units, delta = extract_reason_and_duration(parts[2])
    human_readable = format_duration_full(formatted_units)

    # 3. Вычисляем время окончания бана
    ban_until = datetime.datetime.now(datetime.timezone.utc) + delta
    ban_until_ts = int(ban_until.timestamp())
    # для БД в GMT+2
    gmt2 = datetime.timezone(datetime.timedelta(hours=2))
    ban_until_str = ban_until.astimezone(gmt2).isoformat()

    # 4. Проверяем уровни доступа
    try:
        target_member = await context.bot.get_chat_member(chat.id, target_user.id)
    except Exception as e:
        await message.reply_text(f"❌ Не удалось получить данные о пользователе: {e}")
        return
    if target_member.status == ChatMember.OWNER:
        await message.reply_text("⛔ Нельзя забанить владельца группы.")
        return

    inv_level = float('inf') if is_owner else get_user_max_role_level(chat.id, invoker.id)
    tgt_level = get_user_max_role_level(chat.id, target_user.id)
    if not is_owner and inv_level >= tgt_level:
        await message.reply_text("⛔ Нельзя забанить пользователя с равным или более высоким уровнем доступа.")
        return

    # 5. Выполняем бан
    try:
        await context.bot.ban_chat_member(chat.id, target_user.id, until_date=ban_until_ts)
    except Exception as e:
        await message.reply_text(f"❌ Не удалось забанить пользователя: {e}")
        return

    # 6. Сохраняем
    try:
        init_bans_db()
        save_ban(
            chat.id, chat.title,
            invoker.id, invoker.username or '', invoker.first_name or '', invoker.last_name or '',
            target_user.id, target_user.username or '', target_user.first_name or '', target_user.last_name or '',
            reason, human_readable, ban_until_str
        )
    except Exception as e:
        if DEBUG:
            print(f"[DEBUG] Ошибка сохранения бана: {e}")

    # 7. Планируем автоматический разбан
    create_task(unban_after_delay(context, chat.id, target_user.id, int(delta.total_seconds())))

    # 8. Уведомления
    inv_mention = f"@{invoker.username}" if invoker.username else mention_html(invoker.id, invoker.first_name)
    tgt_mention = f"@{target_user.username}" if target_user.username else mention_html(target_user.id, target_user.first_name)
    group_msg = (
        f"🚫 Забанен: {tgt_mention}\n"
        f"👮 Забанил: {inv_mention}\n"
        f"📝 Причина: {reason}\n"
        f"⏱ Срок: {human_readable}"
    )
    private_msg = (
        f"🚫 Вас забанили в чате <b>{chat.title}</b>!\n"
        f"👮 Забанил: {inv_mention}\n"
        f"📝 Причина: {reason}\n"
        f"⏱ Срок: {human_readable}"
    )
    await context.bot.send_message(chat.id, group_msg, parse_mode=ParseMode.HTML)
    try:
        await context.bot.send_message(target_user.id, private_msg, parse_mode=ParseMode.HTML)
    except Exception:
        if DEBUG:
            print(f"[DEBUG] Не удалось отправить ЛС бана пользователю {target_user.id}")

# Регистрация хэндлера
ban_handler_obj = MessageHandler(filters.TEXT & filters.Regex(r"^!ban\b"), ban_handler)
