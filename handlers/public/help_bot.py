from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes
from datetime import datetime
from core.check_group_chat import only_group_chats

# ✅ ID Администраторов, которым доступна Дополнительная Информация в команде !help (доверенные пользователи)
TRUSTED_USERS = [5403794760]  # Добавь нужные ID

# Кол-во страниц справки (Всегда последняя страница доступна только Админам Бота "В данный момент page5")
ALL_PAGES = ["page1", "page2", "page3", "page4", "page5"]


# === Хэндлер команды /help ===
@only_group_chats
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
            "📘 <b>Доступные команды:</b>\n\n"
            "ℹ️ <code>!group</code> — Информация о текущей группе\n"
            "👥 <code>!view-admins</code> — Список кастомных ролей и админов\n"
            "🏷️ <code>!prefix</code> — Изменить префикс роли пользователя\n"
            "📜 <code>!rules</code> — Просмотреть правила группы"
        ),

        "page2": (
            "⚙️ <b>Управление группой (админы):</b>\n\n"
            "🛠️ <code>!grant</code> — Назначить кастомную роль участнику\n"
            "❌ <code>!revoke</code> — Снять кастомную роль\n"
            "✏️ <code>!edit-admin</code> — Редактировать права и параметры роли\n"
            "➕ <code>!new-role</code> — Создать новую роль\n"
            "🗑️ <code>!remove-role</code> — Удалить роль\n"
            "⛔ <code>!ban</code> — Забанить участника\n"
            "📄 <code>!set-rules</code> — Добавить или изменить правила\n"
            "🗑️ <code>!del-rules</code> — Удалить страницу правил"
        ),

        "page3": (
            "🎮 <b>Развлечения:</b>\n\n"
            
            "⚠️ Есть 0.5% шанс получить блокировку чата на 1 минуту :D\n\n"
            
            "🎯 <b>Русская рулетка:</b>\n"
            "🔫 <code>!roulette</code> — Создать игровое лобби\n"
            "🤝 <code>!join</code> — Присоединиться к лобби\n"
            "▶️ <code>!startgame</code> — Начать игру\n"
            "⏹️ <code>!endgame</code> — Завершить игру вручную\n"
            "💥 <code>!shootme</code> — Выстрелить в себя\n"
            "🎯 <code>!shoot</code> &lt;@user&gt; — Выстрелить в другого игрока\n\n"
            
            "🐳 <b>Накорми «Кита»:</b>\n"
            "🐋 <code>!whale</code> &lt;Имя&gt; — Регистрация вашего питомца\n"
            "✏️ <code>!whale-name</code> &lt;Новое Имя&gt; — Изменить имя питомца\n"
            "🍽️ <code>!feed</code> — Накормить своего питомца (По умолчанию KD 24 часа)\n"
            "🏆 <code>!leaders</code> — Топ‑10 питомцев по весу\n"
            "👤 <code>!profile</code> — Ваш профиль с данными\n"
            "🛠️ <code>!whale-admins</code> — Список игровых админов\n"
            "ℹ️ <code>!info-whale</code> — Показать параметры игры\n\n"

            "👮 <b>Команды для настройки игры:</b>\n"
            "🔑 <code>!set-whale-admin</code> &lt;@user&gt; — Назначить игрового админа\n"
            "❌ <code>!del-whale-admin</code> &lt;@user&gt; — Снять игрового админа\n"
            "🔄 <code>!whale-name</code> &lt;@user&gt; &lt;НовоеИмя&gt; — Переименовать чужого питомца\n\n"

            "<b>Установка параметров:</b><code>!whale-set</code> &lt;ключ&gt; &lt;значение&gt;\n"
            "⏱️ <code>cooldown</code> — Кулдаун (например 10h  45m  30s)\n"
            "⚖️ <code>gain_min</code> — Мин. набор веса при успехе\n"
            "⚖️ <code>gain_max</code> — Макс. набор веса при успехе\n"
            "📉 <code>loss_min</code> — Мин. потеря веса при неудаче\n"
            "📉 <code>loss_max</code> — Макс. потеря веса при неудаче\n"
            "🎯 <code>chance</code> — Вероятность успеха (0–100 %)\n"
            "❤️ <code>coeff</code> — коэффициент перевода 2 кг → 1 ❤️ (например 12 кг переведет в  6 сердечек)\n"
            "🐳 <code>object_name</code> — Название существа (по умолчанию «Кит»)\n"
        ),

        "page4": (
            "📄 <b>Пустая страница:</b>\n\n"
        ),

        "page5": (
            "🔐 <b>Команды Админов Бота:</b>\n\n"
            "📊 <code>!status</code> — Показать нагрузку системы\n"
            "🐞 <code>!debug-all</code> — Вывести подробную диагностику\n"
            "💾 <code>!export_db</code> — Экспорт базы данных бота\n\n"
            "📤 <b>Команды в ЛС:</b>\n"
            "↩️ <code>/reply</code> — Ответ пользователю\n"
            "📸 <code>/send_photo</code> — Отправить фото с подписью\n"
            "🎥 <code>/send_video</code> — Отправить видео с подписью\n"
            "👥 <code>/export_users</code> — Экспорт списка пользователей\n"
            "🗄️ <code>/export_chat</code> — Экспорт истории чата"
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
