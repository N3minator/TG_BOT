import json
import os
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes, ConversationHandler, MessageHandler, filters

RULES_DB = "database/rules_db.json"
MAX_RULES_PAGES = 10

# Conversation states for ConversationHandler
ASK_PAGE, ASK_TEXT = range(2)

# Загружаем правила из файла


def load_rules():
    if not os.path.exists(RULES_DB):
        return {}
    with open(RULES_DB, 'r', encoding='utf-8') as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return {}

# Сохраняем правила в файл


def save_rules(data):
    with open(RULES_DB, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

# Получаем текст правил для нужной страницы


def get_rules_for_page(chat_id: str, page: int) -> str:
    rules = load_rules().get(str(chat_id), [])
    if 0 < page <= len(rules):
        return rules[page - 1]
    return "На сервере в данный момент нету правил."

# Генерируем inline-кнопки с информацией о страницах


def generate_rules_keyboard(user_id: int, page: int, total_pages: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🔄 Обновить", callback_data=f"rules_refresh|{user_id}|{page}"),
            InlineKeyboardButton(f"📄 Страница {page}/{total_pages}", callback_data="noop")
        ],
        [
            InlineKeyboardButton("⏪ << Назад", callback_data=f"rules_prev|{user_id}|{page}"),
            InlineKeyboardButton("Вперёд >> ⏩", callback_data=f"rules_next|{user_id}|{page}")
        ]
    ])


# Основной обработчик команды !rules
async def rules_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    chat_id = str(update.effective_chat.id)

    rules = load_rules().get(chat_id, [])
    page = 1
    total = max(1, len(rules))
    text = get_rules_for_page(chat_id, page)

    await update.message.reply_text(
        text=text,
        reply_markup=generate_rules_keyboard(user_id, page, total),
        parse_mode="HTML"
    )


# Обработка нажатий на кнопки (переключение страниц)
async def rules_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data.split("|")  # rules_action|user_id|page

    if len(data) < 3:
        return

    action, sender_id, current_page = data[0], data[1], int(data[2])

    if str(query.from_user.id) != sender_id:
        await query.answer("Вы не вызывали эту панель!", show_alert=True)
        return

    chat_id = str(update.effective_chat.id)
    rules = load_rules().get(chat_id, [])
    total_pages = max(1, len(rules))

    if action == "rules_next":
        next_page = current_page + 1 if current_page < total_pages else 1
    elif action == "rules_prev":
        next_page = current_page - 1 if current_page > 1 else total_pages
    elif action == "rules_refresh":
        next_page = current_page
    else:
        return

    text = get_rules_for_page(chat_id, next_page)
    if action == "rules_refresh":
        from datetime import datetime
        text += f"\n🔄 Обновлено: {datetime.now().strftime('%H:%M:%S')}"

    await query.edit_message_text(
        text=text,
        reply_markup=generate_rules_keyboard(sender_id, next_page, total_pages),
        parse_mode="HTML"
    )


# === Установка правил через !set-rules ===
async def set_rules_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user
    member = await context.bot.get_chat_member(chat.id, user.id)
    if member.status != "creator":
        await update.message.reply_text("Только владелец группы может устанавливать правила.")
        return ConversationHandler.END

    context.user_data['chat_id'] = str(chat.id)

    text_parts = update.message.text.strip().split()
    if len(text_parts) == 2 and text_parts[1].isdigit():
        page = int(text_parts[1])
        if not (1 <= page <= MAX_RULES_PAGES):
            await update.message.reply_text("Страница должна быть от 1 до 10")
            return ConversationHandler.END

        rules = load_rules().get(context.user_data['chat_id'], [])
        if page > len(rules) + 1:
            await update.message.reply_text("Нельзя создать эту страницу — предыдущая ещё пустая")
            return ConversationHandler.END

        context.user_data['page'] = page
        await update.message.reply_text("Отправьте текст правил для этой страницы")
        return ASK_TEXT

    await update.message.reply_text("На какую страницу вы хотите внести изменения? (1-10)")
    return ASK_PAGE


async def set_rules_receive_page(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        page = int(update.message.text.strip())
        if not (1 <= page <= MAX_RULES_PAGES):
            raise ValueError
    except ValueError:
        await update.message.reply_text("Введите число от 1 до 10")
        return ASK_PAGE

    chat_id = context.user_data['chat_id']
    rules = load_rules().get(chat_id, [])

    if page > len(rules) + 1:
        await update.message.reply_text("Нельзя создавать новую страницу, пока предыдущая не заполнена.")
        return ConversationHandler.END

    context.user_data['page'] = page
    await update.message.reply_text("Отправьте текст правил для этой страницы")
    return ASK_TEXT


async def set_rules_receive_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = context.user_data['chat_id']
    page = context.user_data['page']
    rules_data = load_rules()
    rules = rules_data.get(chat_id, [])

    while len(rules) < page:
        rules.append("")

    rules[page - 1] = update.message.text.strip()
    rules_data[chat_id] = rules
    save_rules(rules_data)

    await update.message.reply_text(f"✅ Правила для страницы {page} сохранены!")
    return ConversationHandler.END


async def set_rules_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Отменено")
    return ConversationHandler.END


# === Удаление страницы правил через !del-rules X ===
async def delete_rules_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user
    member = await context.bot.get_chat_member(chat.id, user.id)

    if member.status != "creator":
        await update.message.reply_text("Удаление разрешено только владельцу группы.")
        return

    args = update.message.text.strip().split()
    if len(args) != 2 or not args[1].isdigit():
        await update.message.reply_text("Используйте: !del-rules <номер страницы>")
        return

    page_to_delete = int(args[1])
    chat_id = str(chat.id)
    rules_data = load_rules()
    rules = rules_data.get(chat_id, [])

    if not (1 <= page_to_delete <= len(rules)):
        await update.message.reply_text("Страница не существует или уже пуста.")
        return

    del rules[page_to_delete - 1]  # Удаление страницы
    rules_data[chat_id] = rules  # Перезапись
    save_rules(rules_data)

    await update.message.reply_text(f"🗑 Страница {page_to_delete} успешно удалена и порядок обновлён.")