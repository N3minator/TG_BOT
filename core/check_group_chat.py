from functools import wraps
from telegram import Update
from telegram.ext import ContextTypes


def only_group_chats(func):
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        chat = update.effective_chat
        if not chat or chat.type == "private":
            #if update.message:
            #    await update.message.reply_text("⛔ Эта команда доступна только в группах.")
            return
        return await func(update, context, *args, **kwargs)
    return wrapper
