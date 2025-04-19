from telegram import Update, ChatMember, User
from telegram.ext import ContextTypes, MessageHandler, filters
from handlers.admin.moderation_db import assign_user_to_role, role_exists, init_user_roles_db
from telegram.helpers import mention_html
import re

init_user_roles_db()


async def grant_admin_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    if not message:
        return

    chat = update.effective_chat
    user = update.effective_user

    try:
        member = await context.bot.get_chat_member(chat.id, user.id)
        if member.status != ChatMember.OWNER:
            await message.reply_text("\u26d4 Только владелец группы может выдавать кастомные роли!")
            return
    except:
        await message.reply_text("\u274c Ошибка при проверке прав.")
        return

    match = re.match(r"!grant(?: @\w+)? (.+)", message.text.strip())
    if not message.reply_to_message or not match:
        await message.reply_text("\u2709\ufe0f Используй: !grant [в ответ на сообщение] <\u0420\u043e\u043b\u044c>")
        return

    role = match.group(1).strip().title()
    target_user: User = message.reply_to_message.from_user

    if not role_exists(chat.id, role):
        await message.reply_text(f"\u274c Роль <b>{role}</b> не существует.", parse_mode="HTML")
        return

    assign_user_to_role(chat.id, target_user.id, role)

    await message.reply_html(
        f"\u2705 Роль <b>{role}</b> успешно выдана пользователю {mention_html(target_user.id, target_user.full_name)}!"
    )


grant_admin_handler_obj = MessageHandler(
    filters.TEXT & filters.Regex(r"^!grant"), grant_admin_handler
)