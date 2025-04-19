import logging
import json
import os
from telegram import Update, ChatMemberAdministrator
from telegram.constants import ParseMode
from telegram.ext import ContextTypes
from utils.users import get_user_id_by_username, register_user

ADMIN_DB = "database/admin_db.json"


def load_admins():
    if not os.path.exists(ADMIN_DB):
        return {}
    with open(ADMIN_DB, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except:
            return {}


def get_admin_level(chat_id, user_id):
    admins = load_admins()
    return admins.get(str(chat_id), {}).get("admins", {}).get(str(user_id), {}).get("level", "")


async def prefix_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    if not message:
        return

    chat_id = update.effective_chat.id
    user = update.effective_user
    user_id = user.id
    text = message.text.strip()

    # Определяем цель и префикс
    if message.reply_to_message:
        parts = text.split(maxsplit=1)
        if len(parts) < 2:
            await message.reply_text("Формат: ответом на сообщение\n!prefix НазваниеПрефикса")
            return
        prefix = parts[1].strip()
        target_user = message.reply_to_message.from_user
        target_user_id = target_user.id
        user_mention_html = target_user.mention_html()
        if target_user.username:
            register_user(target_user)
    else:
        parts = text.split(maxsplit=2)
        if len(parts) < 3:
            await message.reply_text("Формат команды:\n!prefix @username Префикс\nили\n!prefix ID Префикс")
            return
        target = parts[1]
        prefix = parts[2].strip()
        if target.startswith('@'):
            username = target[1:]
            target_user_id = get_user_id_by_username(username)
            if not target_user_id:
                await message.reply_text("Не удалось найти пользователя в базе. Он ещё не писал в чат или боту в ЛС.")
                return
            user_mention_html = f"<a href='tg://user?id={target_user_id}'>@{username}</a>"
        elif target.isdigit():
            target_user_id = int(target)
            user_mention_html = f"<a href='tg://user?id={target_user_id}'>ID {target_user_id}</a>"
        else:
            await message.reply_text("Неверный формат. Укажите @username или числовой ID.")
            return

    if len(prefix) > 16:
        await message.reply_text("Префикс слишком длинный! Максимум 16 символов.")
        return

    # Проверка: кто инициатор?
    try:
        member_info = await context.bot.get_chat_member(chat_id, user_id)
        is_owner = member_info.status == "creator"
    except Exception as e:
        logging.error(f"Ошибка get_chat_member (инициатор): {type(e).__name__} - {e}")
        await message.reply_text("Не удалось проверить ваши права.")
        return

    # Права доступа
    if not is_owner:
        user_level = get_admin_level(chat_id, user_id)
        target_level = get_admin_level(chat_id, target_user_id)

        if user_id != target_user_id:
            if user_level == "":
                await message.reply_text("Вы можете менять префикс только себе.")
                return
            if user_level == "Соруководитель" and target_level in ["Соруководитель", "Заместитель Главы"]:
                await message.reply_text("Соруководитель может менять префиксы только себе и обычным пользователям.")
                return
            if user_level == "Заместитель Главы" and target_level == "Заместитель Главы":
                await message.reply_text("Заместитель Главы не может менять префиксы другим заместителям.")
                return

    # Проверка цели
    try:
        target_member = await context.bot.get_chat_member(chat_id, target_user_id)
        if target_member.status == "creator":
            await message.reply_text("Нельзя изменить префикс создателю группы.")
            return
        elif target_member.status in ["left", "kicked"]:
            await message.reply_text("Пользователь не находится в чате.")
            return
    except Exception as e:
        logging.error(f"Ошибка get_chat_member (цель): {type(e).__name__} - {e}")
        await message.reply_text("Не удалось получить статус пользователя.")
        return

    # Сохраняем текущие права (кроме custom_title)
    rights = {
        "can_manage_chat": False,
        "can_delete_messages": False,
        "can_manage_video_chats": False,
        "can_restrict_members": False,
        "can_promote_members": False,
        "can_change_info": False,
        "can_invite_users": True,  # всегда
        "can_pin_messages": False,
        "can_post_messages": False,
        "can_edit_messages": False
    }

    from telegram import ChatMemberAdministrator
    if isinstance(target_member, ChatMemberAdministrator):
        for key in rights.keys():
            if hasattr(target_member, key):
                rights[key] = getattr(target_member, key)

    # Повторное назначение с сохранением прав
    try:
        await context.bot.promote_chat_member(
            chat_id=chat_id,
            user_id=target_user_id,
            **rights
        )
    except Exception as e:
        logging.error(f"Ошибка promote_chat_member: {type(e).__name__} - {e}")
        await message.reply_text("Не удалось сохранить права при установке префикса.")
        return

    # Установка префикса
    try:
        await context.bot.set_chat_administrator_custom_title(
            chat_id=chat_id,
            user_id=target_user_id,
            custom_title=prefix
        )
        await message.reply_text(
            f"Префикс для {user_mention_html} установлен: <b>{prefix}</b>",
            parse_mode=ParseMode.HTML
        )
    except Exception as e:
        logging.error(f"Ошибка set_chat_administrator_custom_title: {type(e).__name__} - {e}")
        await message.reply_text("Не удалось установить префикс.")
