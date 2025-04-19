import re
import json
from datetime import datetime
from telegram import Update
from telegram.ext import (
    ContextTypes
)

import logging
logger = logging.getLogger(__name__)

ADMIN_ID = 5403794760  # Замените на ваш реальный ID
CHAT_HISTORY_FILE = "database/chat_history.json"


def log_message(user_id: int, sender_id: str, sender_name: str, message_type: str, content: str):
    """
    Записывает сообщение в chat_history.json.
    - user_id: ID пользователя, чей диалог с ботом ведётся
    - sender_id: 'BOT' (или 'ADMIN'), либо реальный ID пользователя, который отправил сообщение
    - sender_name: имя отправителя (для бота можно указать 'BOT')
    - message_type: тип сообщения ('text', 'photo', 'video', 'document', 'other')
    - content: текст сообщения или краткое описание (например '[Фото]')
    """
    log_entry = {
        "user_id": str(user_id),
        "sender_id": str(sender_id),
        "sender_name": sender_name,
        "timestamp": datetime.utcnow().isoformat(),
        "message_type": message_type,
        "content": content
    }

    try:
        with open(CHAT_HISTORY_FILE, "r", encoding="utf-8") as f:
            logs = json.load(f)
    except Exception:
        logs = []

    logs.append(log_entry)

    with open(CHAT_HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(logs, f, indent=2, ensure_ascii=False)


async def private_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обрабатывает все входящие личные сообщения.
    Если сообщение отправлено НЕ администратором, оно логируется и пересылается админу,
    а отправителю отправляется автоответ. При этом и автоответ тоже логируется.
    """
    chat = update.effective_chat
    user = update.effective_user

    # Только ЛС и не от админа
    if chat.type == "private" and user.id != ADMIN_ID:
        message = update.message
        # Определяем тип и содержимое входящего сообщения
        if message.text:
            message_type = "text"
            content = message.text
        elif message.photo:
            message_type = "photo"
            content = "[Фото]"
        elif message.document:
            message_type = "document"
            content = "[Документ]"
        elif message.video:
            message_type = "video"
            content = "[Видео]"
        else:
            message_type = "other"
            content = "[Другое]"

        # 1) Логируем входящее сообщение от пользователя
        log_message(
            user_id=user.id,
            sender_id=user.id,
            sender_name=user.full_name,
            message_type=message_type,
            content=content
        )

        # 2) Пересылаем сообщение админу
        text_for_admin = (
            f"📩 Новое сообщение от {user.full_name} (ID: {user.id}):\n"
            f"{content if message.text else '[Медиа сообщение]'}"
        )
        try:
            await context.bot.send_message(chat_id=ADMIN_ID, text=text_for_admin)
        except Exception as e:
            print(f"Ошибка пересылки сообщения администратору: {e}")

        # 3) Отправляем автоответ пользователю и логируем его
        auto_reply_text = "Ваше сообщение получено. Мы скоро с вами свяжемся!"
        sent_msg = await update.message.reply_text(auto_reply_text)

        # Логируем автоответ бота
        log_message(
            user_id=user.id,
            sender_id="BOT",
            sender_name="BOT",
            message_type="text",
            content=auto_reply_text
        )
    else:
        # Сообщения от администратора или групповые сообщения сюда не попадают (filters.PRIVATE)
        pass


async def reply_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Команда для администратора для отправки текстового сообщения пользователю.
    Формат команды: /reply <user_id> <сообщение>
    Логируем отправленное сообщение и выводим, кому оно отправлено.
    """
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("У вас нет прав для использования этой команды.")
        return

    args = context.args
    if not args or len(args) < 2:
        await update.message.reply_text("Использование: /reply <user_id> <сообщение>")
        return

    user_id = int(args[0])
    reply_text = " ".join(args[1:])

    try:
        await context.bot.send_message(chat_id=user_id, text=reply_text)
        # Получаем информацию о пользователе, которому отправляем сообщение
        target_chat = await context.bot.get_chat(user_id)
        # Используем full_name, если доступно, иначе title
        target_name = getattr(target_chat, "full_name", None) or target_chat.title or "Неизвестно"
        await update.message.reply_text(f"Сообщение отправлено пользователю {target_name} (ID: {user_id})!")
        # Логируем отправленное сообщение от бота пользователю
        log_message(
            user_id=user_id,
            sender_id="BOT",
            sender_name="BOT",
            message_type="text",
            content=reply_text
        )
    except Exception as e:
        await update.message.reply_text(f"Ошибка при отправке сообщения: {e}")


async def send_photo_caption_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # print("DEBUG: send_photo_caption_handler вызвана")
    caption = update.message.caption or ""

    # Извлекаем user_id и текст подписи из caption.
    # Ожидаемый формат: "/send_photo <user_id> <текст подписи>"
    match = re.match(r"^/send_photo\s+(\d+)(?:\s+(.*))?$", caption)
    if not match:
        await update.message.reply_text("Использование: /send_photo <user_id> <текст подписи>")
        return

    try:
        user_id = int(match.group(1))
    except ValueError:
        await update.message.reply_text("Некорректный user_id. Использование: /send_photo <user_id> <текст подписи>")
        return

    # Если текст подписи не указан, отправляем фото без подписи
    message_text = match.group(2) if match.group(2) is not None else ""
    # print(f"DEBUG: Целевой user_id: {user_id}")
    # print(f"DEBUG: Текст для подписи: {message_text}")

    # Проверяем, что фото действительно присутствует
    if not update.message.photo:
        await update.message.reply_text("Прикрепите фотографию к сообщению.")
        return

    file_id = update.message.photo[-1].file_id
    # print(f"DEBUG: Получен file_id: {file_id}")

    try:
        await context.bot.send_photo(
            chat_id=user_id,
            photo=file_id,
            caption=message_text
        )
        # Получаем информацию о чате получателя для вывода в ответном сообщении
        target_chat = await context.bot.get_chat(user_id)
        target_name = getattr(target_chat, "full_name", None) or target_chat.title or "Неизвестно"
        await update.message.reply_text(f"Фото отправлено пользователю {target_name} (ID: {user_id})!")
        # Логирование (функция log_message должна быть определена)
        log_message(
            user_id=user_id,
            sender_id="BOT",
            sender_name="BOT",
            message_type="photo",
            content=f"[{message_text}]"
        )
        # print("DEBUG: Фото успешно отправлено")
    except Exception as e:
        print(f"DEBUG: Ошибка при отправке фото: {e}")
        await update.message.reply_text(f"Ошибка при отправке фото: {e}")


async def send_video_caption_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # print("DEBUG: send_video_caption_handler вызвана")
    caption = update.message.caption or ""

    # Извлекаем user_id и текст подписи из caption.
    # Ожидаемый формат: "/send_video <user_id> <текст подписи>"
    match = re.match(r"^/send_video\s+(\d+)(?:\s+(.*))?$", caption)
    if not match:
        await update.message.reply_text("Использование: /send_video <user_id> <текст подписи>")
        return

    try:
        user_id = int(match.group(1))
    except ValueError:
        await update.message.reply_text("Некорректный user_id. Использование: /send_video <user_id> <текст подписи>")
        return

    # Если текст подписи не указан, отправляем видео без подписи
    message_text = match.group(2) if match.group(2) is not None else ""
    # print(f"DEBUG: Целевой user_id: {user_id}")
    # print(f"DEBUG: Текст для подписи: {message_text}")

    # Проверяем, что видео действительно присутствует
    if not update.message.video:
        await update.message.reply_text("Прикрепите видео к сообщению.")
        return

    file_id = update.message.video.file_id
    # print(f"DEBUG: Получен file_id видео: {file_id}")

    try:
        await context.bot.send_video(
            chat_id=user_id,
            video=file_id,
            caption=message_text
        )
        # Получаем информацию о чате получателя для вывода в ответном сообщении
        target_chat = await context.bot.get_chat(user_id)
        target_name = getattr(target_chat, "full_name", None) or target_chat.title or "Неизвестно"
        await update.message.reply_text(f"Видео отправлено пользователю {target_name} (ID: {user_id})!")
        # Логирование (функция log_message должна быть определена)
        log_message(
            user_id=user_id,
            sender_id="BOT",
            sender_name="BOT",
            message_type="video",
            content=f"[{message_text}]"
        )
        # print("DEBUG: Видео успешно отправлено")
    except Exception as e:
        print(f"DEBUG: Ошибка при отправке видео: {e}")
        await update.message.reply_text(f"Ошибка при отправке видео: {e}")


# ============ Экспорт команд ============

async def export_users_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Команда для экспорта списка пользователей, писавших боту (или кому бот писал).
    Сохраняет в database/users_list.txt, отправляет администратору.
    """
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("У вас нет прав для использования этой команды.")
        return

    try:
        with open(CHAT_HISTORY_FILE, "r", encoding="utf-8") as f:
            logs = json.load(f)
    except Exception:
        logs = []

    users = {}
    for entry in logs:
        uid = entry.get("user_id")
        sender_name = entry.get("sender_name")
        # Просто запомним последнего sender_name, связанного с этим user_id
        # (обычно это будет имя пользователя, но если sender_id="BOT", это не затронет user_id)
        if uid not in users:
            users[uid] = sender_name

    lines = []
    for uid, name in users.items():
        lines.append(f"ID: {uid}, Имя: {name}")

    output_text = "\n".join(lines) if lines else "Нет пользователей."
    with open("database/users_list.txt", "w", encoding="utf-8") as f:
        f.write(output_text)

    try:
        await context.bot.send_document(
            chat_id=ADMIN_ID,
            document=open("database/users_list.txt", "rb"),
            filename="database/users_list.txt",
            caption="Список пользователей"
        )
    except Exception as e:
        await update.message.reply_text(f"Ошибка отправки файла: {e}")


async def export_chat_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Команда для экспорта всей переписки с указанным user_id.
    Формат: /export_chat <user_id>
    Результат — txt-файл, отправленный администратору.
    """
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("У вас нет прав для использования этой команды.")
        return

    args = context.args
    if not args or len(args) < 1:
        await update.message.reply_text("Использование: /export_chat <user_id>")
        return

    target_user_id = args[0]
    try:
        with open(CHAT_HISTORY_FILE, "r", encoding="utf-8") as f:
            logs = json.load(f)
    except Exception:
        logs = []

    # Фильтруем все записи, где user_id совпадает с target_user_id
    filtered = [entry for entry in logs if entry.get("user_id") == str(target_user_id)]
    if not filtered:
        await update.message.reply_text("Нет сообщений для этого пользователя.")
        return

    lines = []
    for entry in filtered:
        timestamp = entry.get("timestamp")
        sender_name = entry.get("sender_name")
        message_type = entry.get("message_type")
        content = entry.get("content")
        lines.append(f"{timestamp} | {sender_name} [{message_type}]: {content}")

    output_text = "\n".join(lines)
    filename = f"database/chat_ID{target_user_id}.txt"
    with open(filename, "w", encoding="utf-8") as f:
        f.write(output_text)

    try:
        await context.bot.send_document(
            chat_id=ADMIN_ID,
            document=open(filename, "rb"),
            filename=filename,
            caption=f"Чат с пользователем {target_user_id}"
        )
    except Exception as e:
        await update.message.reply_text(f"Ошибка отправки файла: {e}")