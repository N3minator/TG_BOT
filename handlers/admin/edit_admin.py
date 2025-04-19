from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, MessageHandler, filters
from handlers.admin.admin_access import has_access
from handlers.admin.moderation_db import role_exists
from telegram.constants import ChatMember


async def edit_admin_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    if not message:
        return

    chat_id = update.effective_chat.id
    user_id = update.effective_user.id

    parts = message.text.strip().split(maxsplit=1)
    if len(parts) < 2:
        await message.reply_text("✏️ Используй: !edit-admin НазваниеРоли")
        return

    role = parts[1].strip().title()

    try:
        member = await context.bot.get_chat_member(chat_id, user_id)
        if member.status != ChatMember.OWNER:
            if not has_access(chat_id, user_id, "!edit-admin"):
                await message.reply_text("⛔ У вас нет доступа к редактированию ролей.")
                return
    except:
        await message.reply_text("❌ Не удалось проверить ваши права.")
        return

    if not role_exists(chat_id, role):
        await message.reply_text(f"❌ Роль <b>{role}</b> не существует!", parse_mode="HTML")
        return

    # UI
    keyboard = [
        [
            InlineKeyboardButton("+ !ban", callback_data=f"add_!ban:{role}"),
            InlineKeyboardButton("- !ban", callback_data=f"remove_!ban:{role}")
        ],
        [
            InlineKeyboardButton("⏳ Кулдауны", callback_data=f"cooldowns:{role}"),
            InlineKeyboardButton("📤 Назначить", callback_data=f"assign:{role}"),
            InlineKeyboardButton("🗑 Удалить", callback_data=f"delete:{role}")
        ]
    ]

    await message.reply_text(
        f"🛠 Настройка роли: <b>{role}</b>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


edit_admin_handler_obj = MessageHandler(
    filters.TEXT & filters.Regex(r"^!edit-admin"), edit_admin_handler
)
