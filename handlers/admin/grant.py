from telegram import Update, ChatMember
from telegram.ext import ContextTypes, MessageHandler, filters
from handlers.admin.moderation_db import (
    assign_user_to_role, role_exists, init_user_roles_db,
    get_user_roles, get_role_level, get_user_max_role_level
)
from handlers.admin.admin_access import has_access
from telegram.helpers import mention_html
import re

from utils.users import get_user_id_by_username
from core.check_group_chat import only_group_chats

init_user_roles_db()


@only_group_chats
async def grant_admin_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    if not message:
        return

    chat = update.effective_chat
    user = update.effective_user

    try:
        member = await context.bot.get_chat_member(chat.id, user.id)
        is_owner = member.status == ChatMember.OWNER
        if not is_owner and not has_access(chat.id, user.id, "!grant"):
            await message.reply_text("⛔ У вас нет доступа к этой команде.")
            return
    except Exception:
        await message.reply_text("❌ Ошибка при проверке прав.")
        return

    # Определяем целевого пользователя
    if message.reply_to_message:
        target_user = message.reply_to_message.from_user
        parts = message.text.strip().split(maxsplit=1)
        if len(parts) < 2:
            await message.reply_text("✏️ Укажите название роли для выдачи.")
            return
        role = parts[1].strip().title()
    else:
        parts = message.text.strip().split(maxsplit=2)
        if len(parts) < 3:
            await message.reply_text("Использование: !grant <@username или user_id> <Роль>")
            return
        target = parts[1].strip()
        role = parts[2].strip().title()

        if target.startswith("@"):
            username = target[1:]
            target_user_id = get_user_id_by_username(username)
            if not target_user_id:
                await message.reply_text("❌ Пользователь не найден.")
                return
            try:
                target_user = (await context.bot.get_chat_member(chat.id, target_user_id)).user
            except Exception:
                await message.reply_text("❌ Пользователь не найден в чате.")
                return
        elif target.isdigit():
            try:
                target_user = (await context.bot.get_chat_member(chat.id, int(target))).user
            except Exception:
                await message.reply_text("❌ Пользователь не найден в чате.")
                return
        else:
            await message.reply_text("Неверный формат идентификатора пользователя. Укажите @username или числовой ID.")
            return

    if not role_exists(chat.id, role):
        await message.reply_text(f"❌ Роль <b>{role}</b> не существует!", parse_mode="HTML")
        return

    # Проверяем, назначена ли уже данная роль у целевого пользователя
    target_roles = get_user_roles(chat.id, target_user.id)
    if role in target_roles:
        await message.reply_text("❌ Данный пользователь уже имеет эту роль.")
        return

    # Проверка прав на выдачу: если вызывающий не владелец,
    # его эффективный уровень определяется как минимальный из всех его ролей.
    my_level = get_user_max_role_level(chat.id, user.id)
    role_level = get_role_level(chat.id, role)
    if not is_owner and role_level <= my_level:
        await message.reply_text("⛔ Вы не можете выдать роль с таким же или более высоким уровнем доступа.")
        return

    # Выдаем роль: добавляем новую запись в таблицу user_roles
    assign_user_to_role(chat.id, target_user.id, role)
    await message.reply_html(
        f"✅ Роль <b>{role}</b> успешно выдана пользователю {mention_html(target_user.id, target_user.full_name)}!"
    )

grant_admin_handler_obj = MessageHandler(
    filters.TEXT & filters.Regex(r"^!grant\b"), grant_admin_handler
)
