from telegram.ext import (
    MessageHandler, CommandHandler, CallbackQueryHandler, ConversationHandler, Application, ChatMemberHandler
)
from telegram.ext import filters
from datetime import datetime

# Импорт хэндлеров
from utils.users import register_user
from handlers.prefix import prefix_handler
from handlers.group import group_handler, group_callback_handler
from handlers.admin.add_admin import add_admin_handler
from handlers.admin.list_admins import list_admins_handler
from handlers.admin.remove_admin import remove_admin_handler
from handlers.admin.ban import ban_handler
from handlers.funny.echo.mute_random import mute_random_handler
from handlers.help_bot import help_handler, help_callback_handler
from handlers.status import status_command, debugall_command
from handlers.creator_bot.export_database import export_db_conv_handler, export_db_handler_immediate
from handlers.admin.clear_cmd import clear_cmd_handler_obj, cache_handler_obj
from handlers.creator_bot.restart_bot import restart_handler
from handlers.system.register_join_user import on_user_join
from handlers.rules_bot import (
    rules_handler, rules_callback_handler, set_rules_start,
    set_rules_receive_page, set_rules_receive_text, set_rules_cancel,
    delete_rules_handler
)
from handlers.funny.russian_roulette import (
    roulette_handler, join_handler, start_game_handler,
    endgame_handler, shoot_handler, shootme_handler
)
from handlers.funny.echo.chat_bot import (
    private_message_handler, reply_handler,
    send_photo_caption_handler, send_video_caption_handler,
    export_users_handler, export_chat_handler
)

"""
✅ Принцип работы group=N:
group=0: критически важные хэндлеры (кэш, логирование)

group=1: разговорные хэндлеры, которые требуют исключительности (ConversationHandler)

group=2: команды

group=3+: всё остальное (inline-кнопки, ЛС, fallback)

Проще говоря, чем ниже число - тем выше приоритет загрузки (0 - это максимальный приоритет)
А чем выше число - тем меньше приоритет обработки чего либо
"""


# 👤 Регистрация пользователей с логированием
async def register_user_handler(update, context):
    if update.effective_user:
        user = update.effective_user
        register_user(user)

        # 🔍 Лог регистрации + показатель того что все приоритеты "group" отрабатывают правильно!
        # Ибо регистрация пользователей в самом конце приоритета распределена!
        print(f"🟢 [{datetime.now().strftime('%H:%M:%S')}] Зарегистрирован пользователь @{user.username} (ID: {user.id})")


def setup_all_handlers(app: Application):
    # Регистрация пользователя если он ввел сообщение
    app.add_handler(MessageHandler(filters.ALL, register_user_handler), group=0)

    # 0. Cache-сборщик сообщений
    app.add_handler(cache_handler_obj, group=0)

    # Обработка регистрации вступления в чат — молчуны
    app.add_handler(ChatMemberHandler(on_user_join, ChatMemberHandler.CHAT_MEMBER), group=0)

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

    # 2. Команды (!group, !help и др.)
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"^!group"), group_handler), group=2)
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"^!prefix"), prefix_handler), group=2)
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"^!help"), help_handler), group=2)
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"^!rules"), rules_handler), group=2)
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"^!del-rules"), delete_rules_handler), group=2)
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"^!status"), status_command), group=2)
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"^!debug-all"), debugall_command), group=2)
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"^!add-admin"), add_admin_handler), group=2)
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"^!admins"), list_admins_handler), group=2)
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"^!del-admin"), remove_admin_handler), group=2)
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"^!ban"), ban_handler), group=2)
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"^!roulette"), roulette_handler), group=2)
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"^!join"), join_handler), group=2)
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"^!startgame"), start_game_handler), group=2)
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"^!endgame"), endgame_handler), group=2)
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"^!shootme"), shootme_handler), group=2)
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"^!shoot"), shoot_handler), group=2)
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"^!export_db(?:\s|$).+"), export_db_handler_immediate), group=2)
    app.add_handler(export_db_conv_handler, group=2)
    app.add_handler(clear_cmd_handler_obj, group=2)
    app.add_handler(restart_handler, group=2)

    # 3. Callback кнопки
    app.add_handler(CallbackQueryHandler(group_callback_handler, pattern="^group_"), group=3)
    app.add_handler(CallbackQueryHandler(help_callback_handler, pattern="^help_"), group=3)
    app.add_handler(CallbackQueryHandler(rules_callback_handler, pattern="^rules_"), group=3)

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