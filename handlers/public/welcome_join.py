from telegram import Update, ChatMember
from telegram.ext import ContextTypes
from telegram.helpers import mention_html
from core.check_group_chat import only_group_chats

# Приветствие новых участников в группе
@only_group_chats
async def welcome_join(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_member = update.chat_member
    old_status = chat_member.old_chat_member.status
    new_status = chat_member.new_chat_member.status
    # Если пользователь вошёл в чат из состояния left или kicked
    if old_status in ['left', 'kicked'] and new_status in ['member', 'restricted']:
        user = chat_member.new_chat_member.user
        # Отправляем приветственное сообщение с упоминанием
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=(
                f"👋 Добро пожаловать, {mention_html(user.id, user.first_name)}!\n"
                "Рады видеть вас в нашей группе. Ознакомьтесь с правилами и представьтесь :)"
            ),
            parse_mode="HTML"
        )

# Регистрация хэндлера в setup_handlers.py:
# from handlers.public.welcome_join import welcome_join
# app.add_handler(ChatMemberHandler(welcome_join, ChatMemberHandler.CHAT_MEMBER), group=0)
