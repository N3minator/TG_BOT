import logging
import json
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ChatMember
from telegram.ext import ContextTypes

ADMIN_DB = "database/admin_db.json"
STATS_DB = "database/group_stats.json"


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
            InlineKeyboardButton("📄 Страница 1/3", callback_data=f"group_page1|{caller_id}")
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

    if caller_id and query.from_user.id != caller_id:
        await query.answer("Эту панель вызывал не вы!", show_alert=True)
        return

    chat = update.effective_chat
    try:
        member_count = await context.bot.get_chat_member_count(chat.id)
    except Exception as e:
        logging.error(f"Ошибка при получении количества участников: {type(e).__name__} - {e}")
        member_count = "не удалось получить"

    if action == "group_page1":
        next_page = "page1"
    elif action == "group_page2":
        next_page = "page2"
    elif action == "group_page3":
        next_page = "page3"
    elif action == "group_refresh":
        next_page = current_page
    elif action == "group_next":
        if current_page == "page1":
            next_page = "page2"
        elif current_page == "page2":
            next_page = "page3"
        else:
            next_page = "page1"
    elif action == "group_prev":
        if current_page == "page1":
            next_page = "page3"
        elif current_page == "page2":
            next_page = "page1"
        else:
            next_page = "page2"
    else:
        next_page = current_page

    if next_page == "page1":
        text_content = (
            f"📊 <b>Информация о группе:</b>\n"
            f"🏷 Название: {chat.title}\n"
            f"🆔 ID: {chat.id}\n"
            f"📚 Тип: {chat.type}\n"
        )
        if chat.username:
            text_content += f"👤 Юзернейм: @{chat.username}\n"
        text_content += f"👥 Количество участников: {member_count}\n"
        if action == "group_refresh":
            text_content += f"\n🔄 Обновлено! {datetime.now().strftime('%H:%M:%S')}"

    elif next_page == "page2":
        text_content = "👮 <b>Администраторы группы:</b>\n\n"
        try:
            with open(ADMIN_DB, "r", encoding="utf-8") as f:
                admin_data = json.load(f)
            if str(chat.id) in admin_data and "admins" in admin_data[str(chat.id)]:
                all_admins = admin_data[str(chat.id)]["admins"]
                if all_admins:
                    zam_list = []
                    sor_list = []
                    other_list = []
                    for admin_id, info in all_admins.items():
                        level = info.get("level", "")
                        username = info.get("username") or f"ID {admin_id}"
                        if level == "Заместитель Главы":
                            zam_list.append((admin_id, username, level))
                        elif level == "Соруководитель":
                            sor_list.append((admin_id, username, level))
                        else:
                            other_list.append((admin_id, username, level))

                    if zam_list:
                        text_content += "<b>Заместители Главы:</b>\n"
                        for adm in zam_list:
                            adm_id, adm_name, adm_level = adm
                            text_content += f"• {adm_name} — {adm_level}\n"
                        text_content += "\n"
                    if sor_list:
                        text_content += "<b>Соруководители:</b>\n"
                        for adm in sor_list:
                            adm_id, adm_name, adm_level = adm
                            text_content += f"• {adm_name} — {adm_level}\n"
                        text_content += "\n"
                    if other_list:
                        text_content += "<b>Прочие админы:</b>\n"
                        for adm in other_list:
                            adm_id, adm_name, adm_level = adm
                            text_content += f"• {adm_name} — {adm_level}\n"
                    if not (zam_list or sor_list or other_list):
                        text_content += "Нет администраторов в базе.\n"
                else:
                    text_content += "Нет администраторов в базе.\n"
            else:
                text_content += "Не найдена информация об админах.\n"
        except Exception as e:
            logging.error(f"Ошибка при загрузке {ADMIN_DB}: {e}")
            text_content += f"Ошибка загрузки администраторов: {e}"
        if action == "group_refresh":
            text_content += f"🔄 Обновлено! {datetime.now().strftime('%H:%M:%S')}"

    elif next_page == "page3":
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
            
            """\nПока не работает статистика. Почему? Мне просто - лень.
            
            А ну и ещё тут будет тир лист топ 10 самых активных участников в группе (Будут отображены места, и количество сообщений)
            И топ 5 самых страшных админов, которые больше всех забанили участников за неделю
            
            Статистика сообщений - будет разделена на 3 блока. 1 блок - это количество сообщений за день.
            И так максимум 3 блока. Где потом будет записываться новый блок информации, и перед внесением в статистику его.
            Самый старый блок удалиться. И такой логикой сможем оценивать актив группы за последние 3 дня ^^
            """
        )
        if action == "group_refresh":
            text_content += f"\n🔄 Обновлено! {datetime.now().strftime('%H:%M:%S')}"

    keyboard = [
        [
            InlineKeyboardButton("🔄 Обновить", callback_data=f"group_refresh|{caller_id}|{next_page}"),
            InlineKeyboardButton(
                f"📄 Страница {next_page[-1]}/3",
                callback_data=f"group_{next_page}|{caller_id}"
            )
        ],
        [
            InlineKeyboardButton("⏪ << Назад", callback_data=f"group_prev|{caller_id}|{next_page}"),
            InlineKeyboardButton("Вперёд >> ⏩", callback_data=f"group_next|{caller_id}|{next_page}")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        text=text_content,
        parse_mode="HTML",
        reply_markup=reply_markup
    )
