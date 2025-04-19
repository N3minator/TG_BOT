from telegram import Update, ChatMember
from telegram.ext import ContextTypes, MessageHandler, filters
from telegram.helpers import mention_html
from handlers.admin.moderation_db import delete_custom_admin_role, role_exists, remove_role_from_all_users
from handlers.admin.admin_access import has_access


async def remove_admin_role_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    if not message:
        return

    chat = update.effective_chat
    user = update.effective_user

    parts = message.text.strip().split(maxsplit=1)
    if len(parts) < 2:
        await message.reply_text("✏️ Используй команду вот так:\n!remove-admin-role НазваниеРоли")
        return

    role = parts[1].strip().title()

    # Проверка владельца или доступа к этой команде
    try:
        member = await context.bot.get_chat_member(chat.id, user.id)
        if member.status != ChatMember.OWNER:
            if not has_access(chat.id, user.id, "!remove-admin-role"):
                await message.reply_text("⛔ У вас нет прав для удаления ролей.")
                return
    except:
        await message.reply_text("❌ Не удалось проверить ваши права.")
        return

    if not role_exists(chat.id, role):
        await message.reply_text(f"❌ Роль <b>{role}</b> не найдена.", parse_mode="HTML")
        return

    delete_custom_admin_role(chat.id, role)
    remove_role_from_all_users(chat.id, role)

    await message.reply_text(f"🗑 Роль <b>{role}</b> и все связанные назначения были удалены.", parse_mode="HTML")


remove_admin_role_handler_obj = MessageHandler(
    filters.TEXT & filters.Regex(r"^!remove-admin-role"), remove_admin_role_handler
)
