# ========== 0. Импорты критически важных файлов бота ==========

# Хэндлер регистрации пользователей в Базу Данных
from core.register_join_user import on_user_join
from utils.users import register_user

from core.check_group_chat import only_group_chats

from telegram.ext import (
    MessageHandler, CommandHandler, CallbackQueryHandler, ConversationHandler, Application, ChatMemberHandler
)
from telegram.ext import ContextTypes, MessageHandler, filters
from telegram import Update

# ========== 1. Импорты публичных команд ==========

from handlers.public.prefix import prefix_handler

from handlers.public.group import group_handler, group_callback_handler

# Мини игра, которая с 1% шанса выдает рандомному участнику чата блокировку на 1 минуту
from handlers.funny.mute_random import mute_random_handler

from handlers.public.help_bot import help_handler, help_callback_handler

# !export_db — Экспортировать файлы из Database бота
from handlers.bot_administrators.export_database import export_db_conv_handler, export_db_handler_immediate

from handlers.public.welcome_join import welcome_join

# ========== 2. Импорты кастомных команд (админ-команды) ==========

from handlers.admin.revoke_role import revoke_role_handler_obj

# Хэндлер команды !new-role — создание кастомной роли
from handlers.admin.new_admin_handler import new_admin_handler_obj

# Хэндлер команды !grant — назначение кастомной роли участнику
from handlers.admin.grant import grant_admin_handler_obj

# Хэндлер команды !ban - блокирует определенного пользователя в Группе
from handlers.admin.ban_user import ban_handler_obj


# Хэндлер команды !edit-admin — настройка прав роли, и переключение прав через inline
from handlers.admin.edit_admin import (
    edit_admin_handler_obj,
    edit_admin_toggle_cb_obj,
    edit_admin_option_cb_obj,
    edit_admin_text_handler_obj,
    delete_role_cb_obj,
    confirm_delete_cb_obj,
    cancel_delete_cb_obj
)

# Хэндлер команды !view-admins — просмотр списка кастомных ролей и назначенных админов
from handlers.public.view_admins import view_admins_handler_obj, view_admins_callback_obj

from handlers.admin.remove_role import remove_admin_role_handler_obj, confirm_remove_role_cb_obj, cancel_remove_role_cb_obj

from handlers.public.rules_bot import (
    rules_handler, rules_callback_handler, set_rules_start,
    set_rules_receive_page, set_rules_receive_text, set_rules_cancel,
    delete_rules_handler
)


# ========== 3. Импорты команд для развлечения ==========
from handlers.funny.russian_roulette import (
    roulette_handler, join_handler, start_game_handler,
    endgame_handler, shoot_handler, shootme_handler
)

# ========== 4. Импорты команд для Администраторов Бота ==========

# !status — Показать краткую информацию о нагрузке системы
# !debug-all — Вывести расширенную статистику системы
from handlers.bot_administrators.status import status_command, debugall_command

from handlers.bot_administrators.chat_bot import (
    private_message_handler, reply_handler,
    send_photo_caption_handler, send_video_caption_handler,
    export_users_handler, export_chat_handler
)


# этот хэндлер выстрелит сразу, как только кто‑то вошёл в чат (Но он не рабочий)
async def welcome_new_members(update: Update, context: ContextTypes.DEFAULT_TYPE):
    for member in update.message.new_chat_members:
        # skip the bot itself
        if member.id == context.bot.id:
            continue

        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=(
                f"👋 Добро пожаловать, <a href='tg://user?id={member.id}'>"
                f"{member.first_name}</a>!\n"
                "Рады видеть вас в нашей группе — не стесняйтесь представиться :)"
            ),
            parse_mode="HTML"
        )


# 👤 Регистрация пользователей с логированием
async def register_user_handler(update, context):
    if update.effective_user:
        user = update.effective_user
        register_user(user)

        # print(f"🟢 [{datetime.now().strftime('%H:%M:%S')}] Зарегистрирован пользователь @{user.username} (ID: {user.id})")


# ========== 2. Основная функция регистрации всех хэндлеров ==========
def setup_all_handlers(app: Application):

    filters_group_only = filters.ChatType.GROUPS | filters.ChatType.SUPERGROUP

    # Регистрирует новых вступивших пользователей в Группу (Не обязательно писать в чат)
    app.add_handler(ChatMemberHandler(on_user_join, ChatMemberHandler.CHAT_MEMBER), group=0)

    # Регистрация пользователя если он ввел сообщение (Дополнительный метод)
    app.add_handler(MessageHandler(filters.ALL, register_user_handler), group=0)

    # Приветствует новых участников Группы
    app.add_handler(ChatMemberHandler(welcome_join, ChatMemberHandler.CHAT_MEMBER), group=0)

    # 1. ConversationHandler (!set-rules)
    set_rules_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.TEXT & filters.Regex(r"^!set-rules"), set_rules_start)],
        states={
            0: [MessageHandler(filters.TEXT & filters.Regex(r"^\d+$"), set_rules_receive_page)],
            1: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_rules_receive_text)]
        },
        fallbacks=[MessageHandler(filters.COMMAND, set_rules_cancel)],
        allow_reentry=True,
        conversation_timeout=60
    )
    app.add_handler(set_rules_conv, group=1)

    # 2. Обработчики команд
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"^!group"), group_handler), group=2)

    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"^!prefix"), prefix_handler), group=2)

    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"^!help"), help_handler), group=2)

    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"^!rules"), rules_handler), group=2)

    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"^!del-rules"), delete_rules_handler), group=2)

    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"^!status"), status_command), group=2)

    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"^!debug-all"), debugall_command), group=2)

    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"^!roulette"), roulette_handler), group=2)

    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"^!join"), join_handler), group=2)

    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"^!startgame"), start_game_handler), group=2)

    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"^!endgame"), endgame_handler), group=2)

    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"^!shootme"), shootme_handler), group=2)

    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"^!shoot"), shoot_handler), group=2)

    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"^!export_db(?:\s|$).+"), export_db_handler_immediate), group=2)
    app.add_handler(export_db_conv_handler, group=2)
    # Команда !new-role
    app.add_handler(new_admin_handler_obj, group=2)
    # Команда !grant - для назначения Админом в Группе (Админы - кастомные)
    app.add_handler(grant_admin_handler_obj, group=2)
    # Команда !view-admins - для просмотра всех кастомных ролей в Группе
    app.add_handler(view_admins_handler_obj, group=2)
    app.add_handler(view_admins_callback_obj, group=2)
    # Команда !edit-admin - Вызывает inline с управлением Роли
    app.add_handler(edit_admin_handler_obj, group=2)
    # Команда !remove-role - Удаляет роль полностью
    app.add_handler(remove_admin_role_handler_obj, group=2)
    # Команда !ban - блокирует определенного пользователя в Группе
    app.add_handler(ban_handler_obj, group=2)
    # Команда !revoke - Снимает кастомную роль с участника
    app.add_handler(revoke_role_handler_obj, group=2)

    # 3. Callback кнопки
    app.add_handler(CallbackQueryHandler(group_callback_handler, pattern="^group_"), group=3)
    app.add_handler(CallbackQueryHandler(help_callback_handler, pattern="^help_"), group=3)
    app.add_handler(CallbackQueryHandler(rules_callback_handler, pattern="^rules_"), group=3)
    # Callback — переключение прав ✅/❌
    app.add_handler(edit_admin_toggle_cb_obj, group=3)
    # Callback — Название / Уровень
    app.add_handler(edit_admin_option_cb_obj, group=3)
    # Обработка текста (новое название или уровень)
    app.add_handler(edit_admin_text_handler_obj, group=3)

    # Добавляем хэндлеры для кнопки "Удалить Роль" с подтверждением:
    app.add_handler(delete_role_cb_obj, group=3)
    app.add_handler(confirm_delete_cb_obj, group=3)
    app.add_handler(cancel_delete_cb_obj, group=3)

    # Добавляем хэндлеры для подтверждения удаления роли в команде !remove-role:
    app.add_handler(confirm_remove_role_cb_obj, group=3)
    app.add_handler(cancel_remove_role_cb_obj, group=3)

    # 4. Команды в ЛС
    app.add_handler(CommandHandler("reply", reply_handler), group=4)
    app.add_handler(CommandHandler("send_photo", send_photo_caption_handler), group=4)
    app.add_handler(CommandHandler("send_video", send_video_caption_handler), group=4)
    app.add_handler(CommandHandler("export_users", export_users_handler), group=4)
    app.add_handler(CommandHandler("export_chat", export_chat_handler), group=4)

    # 5. Медиа с caption
    app.add_handler(MessageHandler(filters.PHOTO & filters.CaptionRegex(r"^/send_photo\s+\d+"), send_photo_caption_handler), group=4)
    app.add_handler(MessageHandler(filters.VIDEO & filters.CaptionRegex(r"^/send_video\s+\d+"), send_video_caption_handler), group=4)

    # 6. Сообщения в ЛС
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, private_message_handler), group=5)

    # 7. Прочее в группах
    app.add_handler(MessageHandler(filters.TEXT & ~filters.Regex(r"^!"), mute_random_handler), group=6)