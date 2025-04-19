import os
from telegram import Update, InputFile
from telegram.ext import ContextTypes, ConversationHandler, MessageHandler, filters

# Пользователи по ID которые имеют права использовать команду !export_db (Проще говоря - Администраторы Бота)
TRUSTED_USERS = [5403794760]

DATABASE_PATH = "database"

DB_DESCRIPTIONS = {
    "admin_db.json": "Информация о администраторах группы и уровнях доступа.",
    "chat_history.json": "История личных сообщений Пользователей с Ботом",
    "cooldowns.json": "Время повторного использования Административных Команд бота в разных Группах",
    "users.json": "Связка username и ID пользователей.",
    "roulette_lobbies.json": "Активные лобби игры 'Русская рулетка'.",
    "roulette_settings.json": "Настройки игры 'Русская рулетка' по группам.",
}

WAITING_FOR_CHOICE = 0


async def export_db_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in TRUSTED_USERS:
        await update.message.reply_text("❌ Вы не являетесь Администратором этого Бота ❌")
        return ConversationHandler.END

    files = os.listdir(DATABASE_PATH)
    files_text = "🗃 <b>Файлы базы данных:</b>\n\n"

    for filename in files:
        desc = DB_DESCRIPTIONS.get(filename, "Описание отсутствует.")
        files_text += f"📄 <code>{filename}</code>\n- <i>{desc}</i>\n\n"

    files_text += (
        "📝 Отправьте название файла, чтобы экспортировать его.\n"
        "Или отправьте <b>all</b>, чтобы экспортировать всю базу."
        f"\n\n⌛ Бот будет ожидать ответ в течении 1-й минуты..."
    )

    sent = await update.message.reply_html(files_text)
    context.user_data["export_prompt_id"] = sent.message_id
    return WAITING_FOR_CHOICE


async def send_real_file(context, chat_id, file_path, file_name):
    try:
        with open(file_path, "rb") as f:
            await context.bot.send_document(
                chat_id=chat_id,
                document=InputFile(f, filename=file_name)
            )
    except Exception as e:
        await context.bot.send_message(chat_id=chat_id, text=f"⚠️ Ошибка при отправке {file_name}: {e}")


async def export_db_choice_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    choice = message.text.strip()
    files = os.listdir(DATABASE_PATH)
    prompt_id = context.user_data.get("export_prompt_id")

    is_reply = (
        message.reply_to_message and message.reply_to_message.message_id == prompt_id
    )
    is_direct = not message.reply_to_message or prompt_id is None

    if not is_reply and not is_direct:
        await message.reply_text("Пожалуйста, ответьте на сообщение со списком файлов или напишите заново !export_db.")
        return WAITING_FOR_CHOICE

    if choice == "all":
        for file in files:
            path = os.path.join(DATABASE_PATH, file)
            if os.path.isfile(path):
                await send_real_file(context, message.chat_id, path, file)
        await message.reply_text("✅ Вся база данных экспортирована.")
    elif choice in files:
        path = os.path.join(DATABASE_PATH, choice)
        if os.path.isfile(path):
            await send_real_file(context, message.chat_id, path, choice)
            await message.reply_html(f"✅ Файл <b>{choice}</b> экспортирован.")
        else:
            await message.reply_text("❌ Файл найден, но не читается.")
    else:
        await message.reply_text("❌ Неверное название файла. Экспорт отменён.")

    return ConversationHandler.END


async def export_db_timeout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⌛ Время вышло. Введите команду заново.")
    return ConversationHandler.END


# Версия с ожиданием выбора файла
export_db_conv_handler = ConversationHandler(
    entry_points=[MessageHandler(filters.Regex(r"^!export_db$"), export_db_handler)],
    states={
        WAITING_FOR_CHOICE: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, export_db_choice_handler)
        ]
    },
    fallbacks=[MessageHandler(filters.ALL, export_db_timeout)],
    conversation_timeout=60
)


# Мгновенная версия — обрабатывает !export_db all или !export_db file.json напрямую
async def export_db_handler_immediate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in TRUSTED_USERS:
        await update.message.reply_text("❌ Вы не являетесь Администратором этого Бота ❌")
        return

    message = update.message
    text = message.text.strip()
    parts = text.split()

    if len(parts) < 2:
        return  # если нет аргументов, пусть сработает обычный handler

    arg = parts[1]
    files = os.listdir(DATABASE_PATH)

    if arg == "all":
        for file in files:
            path = os.path.join(DATABASE_PATH, file)
            if os.path.isfile(path):
                await send_real_file(context, message.chat_id, path, file)
        await message.reply_text("✅ Вся база данных экспортирована.")
    elif arg in files:
        path = os.path.join(DATABASE_PATH, arg)
        if os.path.isfile(path):
            await send_real_file(context, message.chat_id, path, arg)
            await message.reply_html(f"✅ Файл <b>{arg}</b> экспортирован.")
        else:
            await message.reply_text("❌ Файл найден, но не читается.")
    else:
        await message.reply_text("❌ Неверное имя файла. Введите команду заново.")