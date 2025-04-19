import logging
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes
from core.check_group_chat import only_group_chats
from utils.users import get_user_id_by_username, register_user
from handlers.admin.admin_access import has_access
from handlers.admin.moderation_db import get_all_user_roles, get_user_max_role_level

DEBUG_LOG = True


@only_group_chats
async def prefix_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    if not message:
        return

    chat_id = message.chat.id
    user = update.effective_user
    user_id = user.id
    text = message.text.strip()

    # Проверяем статус инициатора
    try:
        initiator_member = await context.bot.get_chat_member(chat_id, user_id)
        is_owner = (initiator_member.status == 'creator')
    except Exception as e:
        logging.error(f"Ошибка проверки статуса инициатора: {e}")
        is_owner = False

    # Определяем цель и префикс
    if message.reply_to_message:
        parts = text.split(maxsplit=1)
        if len(parts) < 2:
            await message.reply_text("Использование: ответом на сообщение + !prefix Префикс")
            return
        prefix = parts[1].strip()
        target = message.reply_to_message.from_user
        target_id = target.id
        mention = target.mention_html()
        if target.username:
            register_user(target)
    else:
        parts = text.split(maxsplit=2)
        if len(parts) < 2:
            await message.reply_text("Использование: !prefix Префикс (для себя) или !prefix @username Префикс")
            return
        if parts[1].startswith('@') or parts[1].isdigit():
            if len(parts) < 3:
                await message.reply_text("Неверный формат. !prefix @username Префикс")
                return
            arg = parts[1]
            prefix = parts[2].strip()
            if arg.startswith('@'):
                uid = get_user_id_by_username(arg[1:])
                if not uid:
                    await message.reply_text("Пользователь не найден.")
                    return
                target_id = uid
                mention = f"<a href='tg://user?id={uid}'>@{arg[1:]}</a>"
            else:
                target_id = int(arg)
                mention = f"<a href='tg://user?id={target_id}'>ID {target_id}</a>"
        else:
            prefix = parts[1].strip()
            target_id = user_id
            mention = user.mention_html()

    # Валидация длины
    if not prefix or len(prefix) > 16:
        await message.reply_text("Префикс должен быть от 1 до 16 символов.")
        return

    # Проверяем смену чужого префикса (игнор для владельца)
    if target_id != user_id and not is_owner:
        if not has_access(chat_id, user_id, "!prefix"):
            await message.reply_text("⛔ У вас нет права использовать !prefix для других.")
            return
        roles = get_all_user_roles(chat_id)
        if not any(uid == user_id for uid, _ in roles):
            await message.reply_text("⛔ У вас должна быть кастомная роль, чтобы менять префикс другим.")
            return
        initiator_level = get_user_max_role_level(chat_id, user_id)
        target_level = get_user_max_role_level(chat_id, target_id)
        if initiator_level >= target_level:
            await message.reply_text(
                "⛔ Вы не можете менять префикс пользователю с более высоким или равным уровнем доступа."
            )
            return

    # Попытка продвинуть пользователя до админа с правом приглашать (если не сам)
    if target_id != user_id:
        try:
            await context.bot.promote_chat_member(
                chat_id=chat_id,
                user_id=target_id,
                can_change_info=False,
                can_delete_messages=False,
                can_invite_users=True,
                can_pin_messages=False,
                can_restrict_members=False,
                can_promote_members=False,
                can_manage_video_chats=False,
                can_manage_topics=False,
                can_edit_messages=False
            )
        except Exception as e:
            logging.error(f"Ошибка промоушена пользователя: {e}")
            # продолжаем

    # Установка custom title
    try:
        await context.bot.set_chat_administrator_custom_title(
            chat_id=chat_id,
            user_id=target_id,
            custom_title=prefix
        )
        await message.reply_text(
            f"Префикс для {mention} установлен: <b>{prefix}</b>",
            parse_mode=ParseMode.HTML
        )
    except Exception as e:
        logging.error(f"Ошибка установки префикса: {e}")
        await message.reply_text(
            "Не удалось установить префикс. Убедитесь, что бот имеет права администратора."
        )
