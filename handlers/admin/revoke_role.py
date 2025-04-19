import sqlite3
import os
from telegram import Update, ChatMember
from telegram.ext import ContextTypes, MessageHandler, filters
from telegram.helpers import mention_html
from utils.users import get_user_id_by_username

from handlers.admin.moderation_db import get_user_roles, get_role_level, get_user_max_role_level
from handlers.admin.admin_access import has_access

# Функция для удаления роли у конкретного пользователя
def remove_role_from_user(chat_id: int, user_id: int, role: str):
    # Используем фиксированный путь, как в других модулях
    DB_PATH = os.path.join("database", "moderation.db")
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "DELETE FROM user_roles WHERE chat_id=? AND user_id=? AND role=?",
            (chat_id, user_id, role)
        )
        conn.commit()


# Основной обработчик команды !revoke
async def revoke_role_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    if not message:
        return

    chat = update.effective_chat
    invoker = update.effective_user

    # 1) Проверяем статус в чате
    try:
        invoker_member = await context.bot.get_chat_member(chat.id, invoker.id)
    except Exception:
        await message.reply_text("❌ Не удалось проверить ваши права.")
        return
    is_owner = invoker_member.status == ChatMember.OWNER

    # 2) Если не владелец — проверяем через has_access
    if not is_owner and not has_access(chat.id, invoker.id, "!revoke"):
        await message.reply_text("⛔ У вас нет прав для снятия ролей.")
        return

    # Разбираем входящие данные: если команда вызвана через reply, то извлекаем целевого пользователя из него
    if message.reply_to_message:
        target_user = message.reply_to_message.from_user
        parts = message.text.strip().split(maxsplit=1)
        if len(parts) < 2:
            await message.reply_text("✏️ Укажите название роли, которую нужно снять.")
            return
        role = parts[1].strip().title()
    else:
        parts = message.text.strip().split(maxsplit=2)
        if len(parts) < 3:
            await message.reply_text("Использование: !revoke <@username или user_id> <Роль>")
            return
        target = parts[1].strip()
        role = parts[2].strip().title()

        # Определяем целевого пользователя по @username или ID
        if target.startswith("@"):
            username = target[1:]
            target_user_id = get_user_id_by_username(username)
            if not target_user_id:
                await message.reply_text("❌ Пользователь не найден в базе. Он ещё не писал в чат.")
                return
            try:
                target_user = (await context.bot.get_chat_member(chat.id, target_user_id)).user
            except Exception:
                await message.reply_text("❌ Пользователь не найден в чате.")
                return
        elif target.isdigit():
            target_user_id = int(target)
            try:
                target_user = (await context.bot.get_chat_member(chat.id, target_user_id)).user
            except Exception:
                await message.reply_text("❌ Пользователь не найден в чате.")
                return
        else:
            await message.reply_text("Неверный формат идентификатора пользователя. Укажите @username или числовой ID.")
            return

    # Проверяем, назначена ли указанная роль у целевого пользователя
    target_roles = get_user_roles(chat.id, target_user.id)
    if role not in target_roles:
        await message.reply_text("❌ У данного пользователя нет такой роли.")
        return

    # Проверка прав на снятие: если вызывающий не владелец,
    # то его максимальный уровень должен быть выше (т.е. числово меньше) уровня удаляемой роли
    target_role_level = get_role_level(chat.id, role)
    invoker_max_level = get_user_max_role_level(chat.id, invoker.id)
    if not is_owner and target_role_level <= invoker_max_level:
        await message.reply_text("⛔ Вы не можете снять роль с таким же или более высоким уровнем доступа.")
        return

    # Снимаем роль: удаляем запись из таблицы user_roles для данного пользователя и роли
    remove_role_from_user(chat.id, target_user.id, role)

    invoker_mention = f"@{invoker.username}" if invoker.username else mention_html(invoker.id, invoker.first_name)
    target_mention = f"@{target_user.username}" if target_user.username else mention_html(target_user.id, target_user.first_name)
    await message.reply_html(f"✅ Роль <b>{role}</b> была снята у {target_mention} Администратором {invoker_mention}!")

# Регистрация хэндлера для команды !revoke
revoke_role_handler_obj = MessageHandler(filters.TEXT & filters.Regex(r"^!revoke\b"), revoke_role_handler)
