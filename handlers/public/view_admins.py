from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.helpers import mention_html
from telegram.ext import ContextTypes, MessageHandler, CallbackQueryHandler, filters

from handlers.admin.moderation_db import get_all_user_roles, get_all_roles_with_levels


# 📌 Получить объект ChatMember или None
async def get_user_or_none(chat_id: int, user_id: int, context: ContextTypes.DEFAULT_TYPE):
    try:
        return await context.bot.get_chat_member(chat_id, user_id)
    except Exception:
        return None


# 📋 Генерация страницы с кастомными админами
async def build_admins_page(chat_id: int, context: ContextTypes.DEFAULT_TYPE, owner_id: int):
    user_roles = get_all_user_roles(chat_id)
    all_roles = get_all_roles_with_levels(chat_id)

    if not user_roles or not all_roles:
        return "❌ В этой группе пока нет кастомных админов.", None

    sorted_roles = sorted(all_roles.items(), key=lambda x: x[1])
    role_to_users = {}
    for user_id, role in user_roles:
        role_to_users.setdefault(role, []).append(user_id)

    lines = ["📋 <b>Кастомные роли:</b>"]
    for role, level in sorted_roles:
        users = role_to_users.get(role, [])
        if users:
            mentions = []
            for uid in users:
                member = await get_user_or_none(chat_id, uid, context)
                if member and member.user.username:
                    mentions.append(f"@{member.user.username}")
                else:
                    mentions.append(mention_html(uid, f"@id{uid}"))
            lines.append(f"• <b>{role}</b> (lvl {level}) — {', '.join(mentions)}")

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📜 Роли", callback_data=f"view_roles|{owner_id}")]
    ])
    return "\n".join(lines), keyboard


# 📜 Генерация страницы с ролями
async def build_roles_page(chat_id: int, owner_id: int):
    roles = get_all_roles_with_levels(chat_id)
    if not roles:
        return "❌ Роли не найдены", None

    sorted_roles = sorted(roles.items(), key=lambda x: x[1])
    lines = ["📖 <b>Список ролей:</b>"]
    for role, lvl in sorted_roles:
        lines.append(f"• <b>{role}</b> — уровень <b>{lvl}</b>")

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("👮 Админы", callback_data=f"view_admins|{owner_id}")]
    ])
    return "\n".join(lines), keyboard


# 🧠 Команда !view-admins
async def view_admins_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    if not message:
        return

    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    text, keyboard = await build_admins_page(chat_id, context, user_id)
    await message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=keyboard)


# 🔁 Обработка переключений между страницами
async def view_admins_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    chat_id = query.message.chat.id
    user_id = query.from_user.id

    try:
        action, owner_id = query.data.split("|")
        owner_id = int(owner_id)
    except ValueError:
        await query.answer("Неверные данные", show_alert=True)
        return

    # 🔒 Защита от чужих кликов
    if user_id != owner_id:
        await query.answer("⛔ Только вызывающий может управлять панелью.", show_alert=True)
        return

    if action == "view_roles":
        text, keyboard = await build_roles_page(chat_id, owner_id)
    elif action == "view_admins":
        text, keyboard = await build_admins_page(chat_id, context, owner_id)
    else:
        return

    await query.edit_message_text(text=text, parse_mode=ParseMode.HTML, reply_markup=keyboard)


# 📦 Регистрация хэндлеров
view_admins_handler_obj = MessageHandler(
    filters.TEXT & filters.Regex(r"^!view-admins"), view_admins_handler
)

view_admins_callback_obj = CallbackQueryHandler(
    view_admins_callback, pattern=r"^view_.*\\|"
)
