from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes
from datetime import datetime

# ✅ ID Администраторов, которым доступна Дополнительная Информация в команде !help (доверенные пользователи)
TRUSTED_USERS = [5403794760]  # Добавь нужные ID

# Кол-во страниц справки (Всегда последняя страница доступна только Админам Бота "В данный момент page5")
ALL_PAGES = ["page1", "page2", "page3", "page4", "page5"]


# === Хэндлер команды /help ===
async def help_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    available_pages = get_available_help_pages(user_id)
    page = available_pages[0]
    await update.message.reply_text(
        text=generate_help_page(page),
        reply_markup=generate_help_keyboard(user_id, page, available_pages),
        parse_mode="HTML"
    )


# === Обработка нажатий на кнопки ===
async def help_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data.split("|")  # help_action|user_id|page

    if len(data) < 3:
        return

    action, sender_id, current_page = data[0], data[1], data[2]

    if str(query.from_user.id) != sender_id:
        await query.answer("Вы не вызывали эту справку!", show_alert=True)
        return

    # Получаем доступные страницы для этого пользователя
    available_pages = get_available_help_pages(int(sender_id))
    current_index = available_pages.index(current_page)

    # Логика переключения страниц
    if action == "help_refresh":
        next_page = current_page
    elif action == "help_next":
        next_page = available_pages[(current_index + 1) % len(available_pages)]
    elif action == "help_prev":
        next_page = available_pages[(current_index - 1) % len(available_pages)]
    elif action.startswith("help_page"):
        next_page = f"page{action[-1]}"
        if next_page not in available_pages:
            next_page = current_page
    else:
        next_page = current_page

    # Текст и кнопки
    text_content = generate_help_page(next_page)
    if action == "help_refresh":
        text_content += f"\n\n🔄 Обновлено: {datetime.now().strftime('%H:%M:%S')}"

    await query.edit_message_text(
        text=text_content,
        reply_markup=generate_help_keyboard(sender_id, next_page, available_pages),
        parse_mode="HTML"
    )


# === Содержимое страниц ===
def generate_help_page(page: str) -> str:
    help_texts = {
        "page1": (
            "<b>📘 Доступные команды для пользователей:</b>\n\n"
            "<code>!group</code> — Информация о группе\n"
            "<code>!admins</code> — Список администраторов\n"
            "<code>!prefix</code> — Изменить префикс роли (сохраняет права при смене)\n"
            "<code>!rules</code> — Просмотреть правила группы"
        ),

        "page2": (
            "⚙️ <b>Управление группой (для администраторов):</b>\n\n"
            "<code>!add-admin</code> — Назначить администратора\n"
            "<code>!del-admin</code> — Удалить администратора\n"
            "<code>!ban</code> — Забанить участника\n"
            "<code>!set-rules</code> — Добавить или изменить правила на текущей странице\n"
            "<code>!del-rules</code> — Удалить текущую страницу правил\n"
            "<code>!clear-cmd</code> — Удалить N количество сообщений, связанных с ответом бота + взаимодействия с ним. (В разработке)"
        ),

        "page3": (
            "🎮 <b>Развлечения:</b>\n\n"
            "🎯 <b>Русская рулетка:</b>\n\n"
            "<code>!roulette</code> — Создать игровое лобби\n"
            "<code>!join</code> — Присоединиться к лобби\n"
            "<code>!startgame</code> — Начать игру\n"
            "<code>!endgame</code> — Завершить игру вручную\n"
            "<code>!shootme</code> — Выстрелить в себя\n"
            "<code>!shoot @user</code> — Выстрелить в другого игрока"
            "Так же есть 1% шанс вероятности - словить блокировку чата на 1-ну минуту :D"
        ),

        "page4": (
            "📄 <b>Пустая страница:</b>\n\n"
        ),

        "page5": (
            "🔐 <b>Команды для Администраторов Бота:</b>\n\n"
            "<code>!status</code> — Показать краткую информацию о нагрузке системы\n"
            "<code>!debug-all</code> — Вывести расширенную статистику системы\n"
            "<code>!export_db</code> — Экспортировать файлы из Database бота\n"
            "<code>!restart</code> — Перезапустить бота (Пока не стабильно работает!)\n"
            "\n📤 <b>Команды в ЛС:</b>\n\n"
            "<code>/reply</code> — Ответ пользователю\n"
            "<code>/send_photo</code> — Отправить фото с подписью\n"
            "<code>/send_video</code> — Отправить видео с подписью\n"
            "<code>/export_users</code> — Экспорт всех пользователей\n"
            "<code>/export_chat</code> — Экспорт истории сообщений"
        )
    }
    return help_texts.get(page, "❌ Страница не найдена")


# === Кнопки навигации ===
def generate_help_keyboard(user_id: int, page: str, available_pages) -> InlineKeyboardMarkup:
    page_number = available_pages.index(page) + 1
    total_pages = len(available_pages)
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🔄 Обновить", callback_data=f"help_refresh|{user_id}|{page}"),
            InlineKeyboardButton(f"📄 Страница {page_number}/{total_pages}", callback_data=f"help_page{page_number}|{user_id}|{page}")
        ],
        [
            InlineKeyboardButton("⏪ << Назад", callback_data=f"help_prev|{user_id}|{page}"),
            InlineKeyboardButton("Вперёд >> ⏩", callback_data=f"help_next|{user_id}|{page}")
        ]
    ])


# === Определение доступных страниц по ID ===
def get_available_help_pages(user_id: int):
    if user_id in TRUSTED_USERS:
        return ALL_PAGES
    return ALL_PAGES[:-1]  # Если пользователь не Администратор Бота - то всегда самая последняя страница не будет видна
