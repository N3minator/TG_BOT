from telegram import Update, ChatMember
from telegram.ext import ContextTypes
from telegram.helpers import mention_html
from core.check_group_chat import only_group_chats


# Приветствие новых участников в группе, с отладочным выводом через print
@only_group_chats
async def welcome_join(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Отладка: выводим события
    print("[welcome_join] handler invoked")
    chat_member = getattr(update, 'chat_member', None)
    print(f"[welcome_join] update.chat_member: {chat_member}")
    if not chat_member:
        print("[welcome_join] Нет chat_member, выходим")
        return

    old_status = chat_member.old_chat_member.status
    new_status = chat_member.new_chat_member.status
    chat = update.effective_chat
    thread_id = getattr(chat, 'message_thread_id', None)
    print(f"[welcome_join] chat_id={chat.id}, thread_id={thread_id}, old_status={old_status}, new_status={new_status}")

    # Проверяем: вход из left/kicked → member/restricted
    if old_status in ['left', 'kicked'] and new_status in ['member', 'restricted']:
        user = chat_member.new_chat_member.user
        print(f"[welcome_join] приветствие для user={user.id} ({user.full_name})")
        try:
            kwargs = {
                'chat_id': chat.id,
                'text': (
                    f"👋 Добро пожаловать, {mention_html(user.id, user.first_name)}!\n"
                    "Рады видеть вас. Ознакомьтесь с правилами и представьтесь :)"
                ),
                'parse_mode': 'HTML'
            }
            if thread_id:
                kwargs['message_thread_id'] = thread_id
            print(f"[welcome_join] отправка сообщения: {kwargs}")
            await context.bot.send_message(**kwargs)
        except Exception as e:
            print(f"[welcome_join] ошибка при отправке: {e}")
    else:
        print("[welcome_join] условие приветствия не выполнено")
