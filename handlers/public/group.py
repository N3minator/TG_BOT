import logging
import json
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.helpers import mention_html
from telegram.ext import ContextTypes

from core.check_group_chat import only_group_chats
from handlers.admin.moderation_db import (
    get_all_user_roles,
    get_all_roles_with_levels,
    get_admin_permissions_for_role
)

# Статические пути к базам данных
ADMIN_DB = "database/admin_db.json"
STATS_DB = "database/group_stats.json"

# Полный список приватных команд для контроля прав
# Не забываем про edit_admin.py
ALL_COMMANDS = [
    "!ban", "!grant", "!edit-admin", "!new-role",
    "!remove-role", "!revoke", "!set-rules", "!del-rules", "!prefix"
]


@only_group_chats
async def group_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    if not message:
        return

    chat = update.effective_chat
    try:
        member_count = await context.bot.get_chat_member_count(chat.id)
    except Exception as e:
        logging.error(f"Ошибка при получении количества участников: {type(e).__name__} - {e}")
        member_count = "не удалось получить"

    caller_id = update.effective_user.id

    # Страница 1: Общая информация
    info_page1 = (
        f"📊 <b>Информация о группе:</b>\n"
        f"🏷 Название: {chat.title}\n"
        f"🆔 ID: {chat.id}\n"
        f"📚 Тип: {chat.type}\n"
    )
    if chat.username:
        info_page1 += f"👤 Юзернейм: @{chat.username}\n"
    info_page1 += f"👥 Количество участников: {member_count}"

    keyboard = [
        [
            InlineKeyboardButton("🔄 Обновить", callback_data=f"group_refresh|{caller_id}|page1"),
            InlineKeyboardButton("📄 Страница 1/4", callback_data=f"group_page1|{caller_id}")
        ],
        [
            InlineKeyboardButton("⏪ << Назад", callback_data=f"group_prev|{caller_id}|page1"),
            InlineKeyboardButton("Вперёд >> ⏩", callback_data=f"group_next|{caller_id}|page1")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await message.reply_text(info_page1, reply_markup=reply_markup, parse_mode="HTML")


async def group_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    parts = data.split("|")
    action = parts[0]
    try:
        caller_id = int(parts[1])
    except (IndexError, ValueError):
        caller_id = None
    try:
        current_page = parts[2]
    except IndexError:
        current_page = "page1"

    # Защита от чужих кликов
    if caller_id and query.from_user.id != caller_id:
        await query.answer("Эту панель вызывал не вы!", show_alert=True)
        return

    # Выбор следующей страницы
    if action == "group_page1":
        next_page = "page1"
    elif action == "group_page2":
        next_page = "page2"
    elif action == "group_page3":
        next_page = "page3"
    elif action == "group_page4":
        next_page = "page4"
    elif action == "group_refresh":
        next_page = current_page
    elif action == "group_next":
        if current_page == "page1": next_page = "page2"
        elif current_page == "page2": next_page = "page3"
        elif current_page == "page3": next_page = "page4"
        else: next_page = "page1"
    elif action == "group_prev":
        if current_page == "page1": next_page = "page4"
        elif current_page == "page2": next_page = "page1"
        elif current_page == "page3": next_page = "page2"
        else: next_page = "page3"
    else:
        next_page = current_page

    chat = update.effective_chat
    text_content = ""

    # ========== Page 1 ==========
    if next_page == "page1":
        try:
            member_count = await context.bot.get_chat_member_count(chat.id)
        except Exception as e:
            logging.error(f"Ошибка при получении количества участников: {type(e).__name__} - {e}")
            member_count = "не удалось получить"

        text_content = (
            f"📊 <b>Информация о группе:</b>\n"
            f"🏷 Название: {chat.title}\n"
            f"🆔 ID: {chat.id}\n"
            f"📚 Тип: {chat.type}\n"
        )
        if chat.username:
            text_content += f"👤 Юзернейм: @{chat.username}\n"
        text_content += f"👥 Количество участников: {member_count}"
        if action == "group_refresh":
            text_content += f"\n🔄 Обновлено! {datetime.now().strftime('%H:%M:%S')}"

    # ========== Page 2 ==========
    elif next_page == "page2":
        user_roles = get_all_user_roles(chat.id)
        all_roles = get_all_roles_with_levels(chat.id)
        if not user_roles or not all_roles:
            text_content = "❌ В этой группе пока нет кастомных админов."
        else:
            sorted_roles = sorted(all_roles.items(), key=lambda x: x[1])
            role_to_users = {}
            for uid, role in user_roles:
                role_to_users.setdefault(role, []).append(uid)

            lines = ["📋 <b>Кастомные роли:</b>"]
            for role, level in sorted_roles:
                users = role_to_users.get(role, [])
                if not users: continue
                mentions = []
                for uid in users:
                    try:
                        member = await context.bot.get_chat_member(chat.id, uid)
                        if member and member.user.username:
                            mentions.append(f"@{member.user.username}")
                        else:
                            mentions.append(mention_html(uid, f"@id{uid}"))
                    except:
                        mentions.append(mention_html(uid, f"@id{uid}"))
                lines.append(f"• <b>{role}</b> (lvl {level}) — {', '.join(mentions)}")
            text_content = "\n".join(lines)
        if action == "group_refresh":
            text_content += f"\n🔄 Обновлено! {datetime.now().strftime('%H:%M:%S')}"

    # ========== Page 3 ==========
    elif next_page == "page3":
        roles = get_all_roles_with_levels(chat.id)
        if not roles:
            text_content = "❌ Роли не найдены"
        else:
            sorted_roles = sorted(roles.items(), key=lambda x: x[1])
            lines = ["📖 <b>Список ролей, и их разрешения:</b>\n"]
            for role, lvl in sorted_roles:
                lines.append(f"• <b>{role}</b> — уровень доступа <b>{lvl}</b>\n")
                allowed = get_admin_permissions_for_role(chat.id, role)
                denied = [cmd for cmd in ALL_COMMANDS if cmd not in allowed]
                # Разрешённые
                if allowed:
                    lines.append(f"<b>✅ Разрешенные права:</b> {' / '.join(allowed)}\n")
                #else:
                #    lines.append("<b>✅ Разрешенные права:</b> нет\n")
                # Запрещённые
                if denied:
                    lines.append(f"<b>❌ Запрещенные права:</b> {' / '.join(denied)}\n")
                #else:
                #    lines.append("<b>❌ Запрещенных прав:</b> нету\n")
            text_content = "\n".join(lines)
        if action == "group_refresh":
            text_content += f"\n🔄 Обновлено! {datetime.now().strftime('%H:%M:%S')}"

    # ========== Page 4 ==========
    else:  # page4
        try:
            with open(STATS_DB, "r", encoding="utf-8") as f:
                stats_data = json.load(f)
            group_stats = stats_data.get(str(chat.id), {})
            messages = group_stats.get("messages", 0)
            active = group_stats.get("active_users", 0)
            bans = group_stats.get("bans", 0)
        except Exception as e:
            logging.error(f"Ошибка чтения {STATS_DB}: {e}")
            messages, active, bans = 0, 0, 0

        text_content = (
            "📈 <b>Статистика группы:</b>\n\n"
            f"✉️ Сообщений за сутки: <b>{messages}</b>\n"
            f"👥 Активных участников: <b>{active}</b>\n"
            f"⛔️ Бан(ов) за неделю: <b>{bans}</b>\n"
        )
        if action == "group_refresh":
            text_content += f"🔄 Обновлено! {datetime.now().strftime('%H:%M:%S')}"

    # Навигационная клавиатура (для всех страниц)
    page_num = next_page[-1]
    keyboard = [
        [
            InlineKeyboardButton("🔄 Обновить", callback_data=f"group_refresh|{caller_id}|{next_page}"),
            InlineKeyboardButton(f"📄 Страница {page_num}/4", callback_data=f"group_{next_page}|{caller_id}")
        ],
        [
            InlineKeyboardButton("⏪ << Назад", callback_data=f"group_prev|{caller_id}|{next_page}"),
            InlineKeyboardButton("Вперёд >> ⏩", callback_data=f"group_next|{caller_id}|{next_page}")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(text=text_content, parse_mode="HTML", reply_markup=reply_markup)
