from telegram import Update, ChatMember
from telegram.ext import ContextTypes, MessageHandler, filters
from handlers.admin.moderation_db import create_custom_admin, init_moderation_db, get_user_max_role_level
from handlers.admin.admin_access import has_permission_to_create_admin

init_moderation_db()  # Вызов при импорте


async def new_admin_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    if not message:
        return

    chat = update.effective_chat
    user = update.effective_user

    # Проверка: является ли user владельцем или имеет право
    try:
        member = await context.bot.get_chat_member(chat.id, user.id)
        is_owner = member.status == ChatMember.OWNER
        if not is_owner and not has_permission_to_create_admin(chat.id, user.id):
            await message.reply_text("⛔ У вас нет доступа к созданию кастомных ролей.")
            return
    except Exception:
        await message.reply_text("❌ Не удалось проверить ваши права.")
        return

    parts = message.text.strip().split(maxsplit=2)
    if len(parts) < 3:
        await message.reply_text("✉️ Укажите роль и уровень!\n\n<b>!new-role Роль 1</b>", parse_mode="HTML")
        return

    role_title = parts[1].strip().title()
    if len(role_title) > 32:
        await message.reply_text("❌ Название слишком длинное (max 32)")
        return

    try:
        level = int(parts[2].strip())
    except ValueError:
        await message.reply_text("❌ Уровень должен быть цифрой")
        return

    # Проверка: пользователь не может создать роль с уровнем равным или выше своего
    if not is_owner:
        user_level = get_user_max_role_level(chat.id, user.id)
        if level <= user_level:
            await message.reply_text(f"⛔ Вы не можете создать роль с уровнем {level}, уровни которые вы можете создать: {user_level + 1} и ниже.")
            return

    success = create_custom_admin(chat.id, role_title, user.id, level)
    if success:
        await message.reply_text(f"✅ Роль <b>{role_title}</b> (lvl {level}) создана!", parse_mode="HTML")
    else:
        await message.reply_text(f"❌ Роль <b>{role_title}</b> уже существует!", parse_mode="HTML")


new_admin_handler_obj = MessageHandler(
    filters.TEXT & filters.Regex(r"^!new-role"), new_admin_handler
)
