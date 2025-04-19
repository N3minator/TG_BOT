from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ChatMember
from telegram.ext import ContextTypes, MessageHandler, CallbackQueryHandler, filters

from core.check_group_chat import only_group_chats
from handlers.admin.admin_access import has_access
from handlers.admin.moderation_db import (
    role_exists,
    get_admin_permissions_for_role,
    toggle_admin_permission,
    get_all_user_roles,
    get_user_max_role_level,
    get_role_level,
    rename_custom_admin,
    update_role_level,
    delete_custom_admin_role,
    remove_role_from_all_users
)


# ХЭНДЛЕР: !edit-admin <роль> — Открывает меню редактирования прав
@only_group_chats
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
        is_owner = member.status == ChatMember.OWNER

        if not is_owner:
            if not has_access(chat_id, user_id, "!edit-admin"):
                await message.reply_text("⛔ У вас нет доступа к редактированию ролей.")
                return

            user_roles = [r for _, r in get_all_user_roles(chat_id) if _ == user_id]
            if role in user_roles:
                await message.reply_text("⛔ Вы не можете редактировать свою собственную роль.")
                return

            role_level = get_role_level(chat_id, role)
            user_level = get_user_max_role_level(chat_id, user_id)
            if role_level <= user_level:
                await message.reply_text("⛔ Вы не можете редактировать роли с таким же или более высоким уровнем доступа.")
                return

    except Exception:
        await message.reply_text("❌ Не удалось проверить ваши права.")
        return

    if not role_exists(chat_id, role):
        await message.reply_text(f"❌ Роль <b>{role}</b> не существует!", parse_mode="HTML")
        return

    # 👇 Передаём message_id и user_id как panel_owner_id
    await send_admin_permissions_message(context, chat_id, message.message_id, role, user_id)


# ✅ Функция отображения панели с правами
async def send_admin_permissions_message(
    context,
    chat_id,
    message_id,
    role,
    panel_owner_id,
    query=None,
    per_row_cmds=4,      # Количество команд в ряд (до 8 кнопок в 1-м ряду)
    per_row_options=2    # Количество опций в ряд (до 8 кнопок в 1-м ряду)
):
    # Не забываем про group.py
    ALL_COMMANDS = ["!ban", "!grant", "!edit-admin", "!new-role", "!remove-role", "!revoke", "!set-rules", "!del-rules", "!prefix"]
    allowed = get_admin_permissions_for_role(chat_id, role)

    # 🧾 Формирование таблицы прав
    max_len = max(len(cmd) for cmd in ALL_COMMANDS) + 2
    left = [f"✅ {cmd.ljust(max_len)}" for cmd in allowed]
    right = [f"❌ {cmd}" for cmd in ALL_COMMANDS if cmd not in allowed]
    while len(left) < len(right):
        left.append(" " * (max_len + 2))
    while len(right) < len(left):
        right.append("")
    table = "<pre>\n" + "\n".join(f"{a}| {b}" for a, b in zip(left, right)) + "\n</pre>"

    # 🔘 Генерация кнопок команд
    command_buttons = []
    row = []
    for cmd in ALL_COMMANDS:
        emoji = "✅" if cmd in allowed else "❌"
        callback = f"toggle|{cmd}|{role}|{panel_owner_id}"
        row.append(InlineKeyboardButton(f"{emoji} {cmd}", callback_data=callback))
        if len(row) == per_row_cmds:
            command_buttons.append(row)
            row = []
    if row:
        command_buttons.append(row)

    # 🔧 Генерация кнопок настроек (Название / Уровень)
    option_buttons_all = [
        InlineKeyboardButton("✏ Название", callback_data=f"editrole_name|{role}|{panel_owner_id}"),
        InlineKeyboardButton("📊 Уровень", callback_data=f"editrole_level|{role}|{panel_owner_id}"),
        InlineKeyboardButton("🗑️ Удалить Роль", callback_data=f"delete_role|{role}|{panel_owner_id}")
    ]
    option_rows = [
        option_buttons_all[i:i + per_row_options]
        for i in range(0, len(option_buttons_all), per_row_options)
    ]
    command_buttons.extend(option_rows)

    keyboard = InlineKeyboardMarkup(command_buttons)

    # Получаем уровень доступа роли
    lvl = get_role_level(chat_id, role)

    # Формируем текст с отображением уровня, как в view_admins.py
    header_text = f"📋 Права роли <b>{role}</b> (lvl {lvl}):\n\n{table}"

    # Отправка или обновление сообщения
    if query:
        await query.edit_message_text(
            text=header_text,
            parse_mode="HTML",
            reply_markup=keyboard
        )
    else:
        await context.bot.send_message(
            chat_id=chat_id,
            text=header_text,
            parse_mode="HTML",
            reply_markup=keyboard
        )


# ✅ Callback: Переключение прав
async def toggle_permission_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query:
        return

    await query.answer()
    chat_id = query.message.chat.id
    user_id = query.from_user.id

    try:
        # ✅ Разбираем данные: toggle|cmd|role|owner_id
        parts = query.data.split("|")
        if len(parts) != 4:
            await query.answer("❌ Некорректные данные", show_alert=True)
            return

        _, command, role, owner_id = parts
        owner_id = int(owner_id)
    except Exception:
        await query.answer("❌ Ошибка при разборе", show_alert=True)
        return

    # ✅ Защита от чужого взаимодействия
    if user_id != owner_id:
        await query.answer("⛔ Только вызывающий может использовать панель", show_alert=True)
        return

    try:
        member = await context.bot.get_chat_member(chat_id, user_id)
        is_owner = member.status == ChatMember.OWNER

        if not is_owner:
            if not has_access(chat_id, user_id, "!edit-admin"):
                await query.answer("⛔ Нет доступа", show_alert=True)
                return

            if not has_access(chat_id, user_id, command):
                await query.answer(f"⛔ Нет доступа к {command}", show_alert=True)
                return

            user_roles = [r for _, r in get_all_user_roles(chat_id) if _ == user_id]
            if role in user_roles:
                await query.answer("⛔ Нельзя редактировать свою роль", show_alert=True)
                return

            role_level = get_role_level(chat_id, role)
            user_level = get_user_max_role_level(chat_id, user_id)
            if role_level <= user_level:
                await query.answer("⛔ Недостаточно уровня доступа", show_alert=True)
                return

    except:
        await query.answer("❌ Ошибка при проверке", show_alert=True)
        return

    # ✅ Меняем разрешение в базе
    toggle_admin_permission(chat_id, role, command)

    # ✅ Обновляем UI как в edit_admin_handler — через ту же функцию
    await send_admin_permissions_message(
        context=context,
        chat_id=chat_id,
        message_id=query.message.message_id,
        role=role,
        panel_owner_id=owner_id,
        query=query  # 👈 ВАЖНО: чтобы обновлялось сообщение, а не создавалось новое
    )


# 📥 Callback: выбор ✏ Название / 🔢 Уровень
async def edit_admin_option_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id

    await query.answer()

    try:
        action, role, owner_id = query.data.split("|")
        owner_id = int(owner_id)
    except ValueError:
        await query.answer("❌ Некорректные данные", show_alert=True)
        return

    # Проверка: только владелец панели может продолжить
    if user_id != owner_id:
        await query.answer("⛔ Только вызывающий может использовать панель", show_alert=True)
        return

    # Сохраняем данные с использованием owner_id из callback data, а не query.from_user.id
    context.user_data["edit_admin_mode"] = action.replace("editrole_", "")
    context.user_data["edit_admin_target_role"] = role
    context.user_data["edit_admin_owner"] = owner_id

    if context.user_data["edit_admin_mode"] == "name":
        await query.message.reply_text("✏️ Введите новое название роли:")
    elif context.user_data["edit_admin_mode"] == "level":
        await query.message.reply_text("🔢 Введите новый уровень (целое число от 1 до 999):")


# 📤 Обработка текстового ответа
# Обработка текстового ответа при редактировании (имени или уровня)
async def edit_admin_text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    text = message.text.strip()

    # Проверяем, что мы в режиме правки уровня
    if (
        context.user_data.get("edit_admin_owner") != user_id
        or context.user_data.get("edit_admin_mode") != "level"
        or "edit_admin_target_role" not in context.user_data
    ):
        return

    role = context.user_data["edit_admin_target_role"]

    # 1) Валидация числа
    if not text.isdigit():
        await message.reply_text("❌ Уровень должен быть числом.")
        return
    level = int(text)
    if not (1 <= level <= 999):
        await message.reply_text("❌ Уровень должен быть от 1 до 999.")
        return

    # 2) Проверка прав администратора
    member = await context.bot.get_chat_member(chat_id, user_id)
    is_owner = (member.status == ChatMember.OWNER)
    if not is_owner:
        admin_level = get_user_max_role_level(chat_id, user_id)
        # Блокируем, если админ пытается назначить уровень
        # **меньше или равный** своему (численно ≤)
        if level <= admin_level:
            await message.reply_text(
                "⛔ Вы не можете назначить уровень роли равным или выше вашего собственного уровня доступа."
            )
            return

    # 3) Собственно обновляем уровень
    update_role_level(chat_id, role, level)
    await message.reply_text(
        f"✅ Уровень роли <b>{role}</b> обновлён до <b>{level}</b>.",
        parse_mode="HTML"
    )

    # Очищаем сессию правки
    context.user_data.pop("edit_admin_mode", None)
    context.user_data.pop("edit_admin_target_role", None)
    context.user_data.pop("edit_admin_owner", None)


async def delete_role_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query:
        return
    await query.answer()

    chat_id = query.message.chat.id
    user_id = query.from_user.id
    _, role, owner_id_str = query.data.split("|")
    owner_id = int(owner_id_str)

    # Защита: только владелец панели может удалить
    if user_id != owner_id:
        await query.answer("⛔ Только вызывающий может использовать эту команду", show_alert=True)
        return

    # Проверяем существование роли
    if not role_exists(chat_id, role):
        await query.answer("❌ Роль не существует.", show_alert=True)
        return

    # Получаем статус и уровни
    try:
        member = await context.bot.get_chat_member(chat_id, user_id)
        is_owner = member.status == ChatMember.OWNER
    except Exception:
        await query.answer("❌ Не удалось проверить ваши права.", show_alert=True)
        return

    # Если не владелец, применяем проверку уровней как в remove_role.py
    if not is_owner:
        if not has_access(chat_id, user_id, "!remove-role"):
            await query.answer("⛔ У вас нет прав для удаления ролей.", show_alert=True)
            return

        # Нельзя удалять собственную роль
        user_roles = [r for uid, r in get_all_user_roles(chat_id) if uid == user_id]
        if role in user_roles:
            await query.answer("⛔ Вы не можете удалить свою собственную роль.", show_alert=True)
            return

        target_level = get_role_level(chat_id, role)
        user_level = get_user_max_role_level(chat_id, user_id)
        # Блокируем, если уровень пользователя не выше цели
        if user_level >= target_level:
            await query.answer(
                "⛔ Вы не можете удалить роль с таким же или более высоким уровнем доступа.",
                show_alert=True
            )
            return

    # Если проверки пройдены, запрашиваем подтверждение удаления
    mention = member.user.username and f"@{member.user.username}" or \
              f"<a href='tg://user?id={user_id}'>Пользователь</a>"
    confirmation_text = f"⚠️ {mention} Вы уверены, что хотите удалить роль <b>{role}</b>?"
    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("✅", callback_data=f"confirm_del|{role}|{owner_id}"),
        InlineKeyboardButton("❌", callback_data=f"cancel_del|{role}|{owner_id}")
    ]])
    await query.edit_message_text(text=confirmation_text, parse_mode="HTML", reply_markup=keyboard)


# Callback: Подтверждение удаления
async def confirm_delete_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query:
        return
    await query.answer()

    chat_id = query.message.chat.id
    user_id = query.from_user.id
    _, role, owner_id_str = query.data.split("|")
    owner_id = int(owner_id_str)

    # Только вызывающий может подтвердить
    if user_id != owner_id:
        await query.answer("⛔ Только вызывающий может подтвердить удаление.", show_alert=True)
        return

    # Проверяем, что роль ещё существует
    if not role_exists(chat_id, role):
        await query.edit_message_text(f"❌ Роль <b>{role}</b> уже не существует.", parse_mode="HTML")
        return

    # Удаляем роль и все назначения
    delete_custom_admin_role(chat_id, role)
    remove_role_from_all_users(chat_id, role)

    await query.edit_message_text(f"🗑️ Роль <b>{role}</b> успешно удалена.", parse_mode="HTML")


# Callback для отмены удаления
async def cancel_delete_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query:
        return
    await query.answer("Отменено")
    # Здесь можно либо обновить панель, либо просто сообщить об отмене
    await query.edit_message_text("❌ Удаление отменено.")


edit_admin_option_cb_obj = CallbackQueryHandler(edit_admin_option_callback, pattern=r"^editrole_")
edit_admin_text_handler_obj = MessageHandler(filters.TEXT & ~filters.COMMAND, edit_admin_text_handler)

# ✅ Объекты хэндлеров для регистрации в setup_handlers.py

# Регистрируем обработчик для кнопки "Удалить Роль"
delete_role_cb_obj = CallbackQueryHandler(delete_role_callback, pattern=r"^delete_role\|")
# Регистрируем обработчик для подтверждения удаления
confirm_delete_cb_obj = CallbackQueryHandler(confirm_delete_callback, pattern=r"^confirm_del\|")
# Регистрируем обработчик для отмены удаления
cancel_delete_cb_obj = CallbackQueryHandler(cancel_delete_callback, pattern=r"^cancel_del\|")

edit_admin_handler_obj = MessageHandler(filters.Regex(r"^!edit-admin\b"), edit_admin_handler)
edit_admin_toggle_cb_obj = CallbackQueryHandler(toggle_permission_callback, pattern=r"^toggle\|")
