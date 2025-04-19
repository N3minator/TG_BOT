from telegram import Update
from telegram.ext import ContextTypes
from utils.users import register_user


async def on_user_join(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_member = update.chat_member

    old_status = chat_member.old_chat_member.status
    new_status = chat_member.new_chat_member.status
    user = chat_member.new_chat_member.user

    print(f"👀 Изменение статуса: {user.full_name} ({user.id}) {old_status} → {new_status}")

    if new_status in ['member', 'restricted'] and old_status in ['left', 'kicked']:
        print(f"📥 Регистрируем нового участника: {user.full_name}")
        register_user(user)
        print(f"✅ Зарегистрирован молчун: {user.full_name} (ID: {user.id})")
    else:
        print("🔕 Не подходит под условия регистрации.")
