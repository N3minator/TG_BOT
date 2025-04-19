from telegram import Update, ChatMember, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, MessageHandler, CallbackQueryHandler, filters
from telegram.helpers import mention_html

from core.check_group_chat import only_group_chats
from handlers.admin.moderation_db import (
    delete_custom_admin_role,
    role_exists,
    remove_role_from_all_users,
    get_all_user_roles,
    get_role_level,
    get_user_max_role_level
)
from handlers.admin.admin_access import has_access


@only_group_chats
async def remove_admin_role_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    if not message:
        return

    chat = update.effective_chat
    user = update.effective_user

    # Сначала проверим права пользователя (даже до разбора команды)
    try:
        member = await context.bot.get_chat_member(chat.id, user.id)
    except Exception:
        await message.reply_text("❌ Не удалось проверить ваши права.")
        return

    is_owner = member.status == ChatMember.OWNER
    if not is_owner:
        if not has_access(chat.id, user.id, "!remove-role"):
            await message.reply_text("⛔ У вас нет прав для удаления ролей.")
            return

    # Теперь разбираем входящие аргументы
    parts = message.text.strip().split(maxsplit=1)
    if len(parts) < 2:
        await message.reply_text("✏️ Используй команду вот так:\n!remove-role Название Роли")
        return

    role = parts[1].strip().title()

    # Проверка прав доступа и условий удаления для НЕ-владельца
    try:
        if not is_owner:
            # Нельзя удалять собственную роль
            user_roles = [r for uid, r in get_all_user_roles(chat.id) if uid == user.id]
            if role in user_roles:
                await message.reply_text("⛔ Вы не можете удалить свою собственную роль.")
                return

            target_level = get_role_level(chat.id, role)
            user_level = get_user_max_role_level(chat.id, user.id)

            # Блокируем, если пользователь не выше цели (правильная проверка уровней)
            if user_level >= target_level:
                await message.reply_text(
                    "⛔ Вы не можете удалить роль с таким же или более высоким уровнем доступа."
                )
                return
    except Exception:
        await message.reply_text("❌ Не удалось проверить ваши права.")
        return

    if not role_exists(chat.id, role):
        await message.reply_text(f"❌ Роль <b>{role}</b> не найдена.", parse_mode="HTML")
        return

    # Формируем упоминание пользователя
    if member.user.username:
        mention = f"@{member.user.username}"
    else:
        mention = f"<a href='tg://user?id={user.id}'>Пользователь</a>"
    confirmation_text = f"⚠️ {mention} Вы точно уверены, что хотите удалить роль <b>{role}</b>?"

    # Формируем inline клавиатуру с кнопками подтверждения и отмены
    confirm_button = InlineKeyboardButton("✅", callback_data=f"confirm_del_role|{role}|{user.id}")
    cancel_button = InlineKeyboardButton("❌", callback_data=f"cancel_del_role|{role}|{user.id}")
    keyboard = InlineKeyboardMarkup([[confirm_button, cancel_button]])

    await message.reply_text(confirmation_text, parse_mode="HTML", reply_markup=keyboard)


async def confirm_remove_role_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query:
        return
    await query.answer()

    chat_id = query.message.chat.id
    user_id = query.from_user.id

    parts = query.data.split("|")
    if len(parts) != 3:
        await query.answer("❌ Некорректные данные", show_alert=True)
        return
    _, role, owner_id_str = parts
    owner_id = int(owner_id_str)

    if user_id != owner_id:
        await query.answer("⛔ Только вызывающий может подтвердить удаление.", show_alert=True)
        return

    if not role_exists(chat_id, role):
        await query.edit_message_text(f"❌ Роль <b>{role}</b> уже не существует.", parse_mode="HTML")
        return

    delete_custom_admin_role(chat_id, role)
    remove_role_from_all_users(chat_id, role)

    await query.edit_message_text(f"🗑 Роль <b>{role}</b> успешно удалена.", parse_mode="HTML")


async def cancel_remove_role_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query:
        return
    await query.answer("Отменено")
    await query.edit_message_text("❌ Удаление отменено.")


remove_admin_role_handler_obj = MessageHandler(
    filters.TEXT & filters.Regex(r"^!remove-role"), remove_admin_role_handler
)

confirm_remove_role_cb_obj = CallbackQueryHandler(confirm_remove_role_callback, pattern=r"^confirm_del_role\|")
cancel_remove_role_cb_obj = CallbackQueryHandler(cancel_remove_role_callback, pattern=r"^cancel_del_role\|")
