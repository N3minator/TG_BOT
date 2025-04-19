import random
from asyncio import sleep
from telegram import Update, ChatPermissions
from telegram.ext import ContextTypes

# Настройки
MUTE_CHANCE = 0.01   # 0.01 = это 1% шанс / 0.1 = 10% шанс / 0.005 = 0.5% шанс
MUTE_DURATION = 60   # в секундах


async def mute_random_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    if not message or not message.text or not update.effective_user:
        return

    chat_id = message.chat_id
    user_id = message.from_user.id

    # Рандомный шанс
    if random.random() < MUTE_CHANCE:
        try:
            # Мут на 1 минуту
            await context.bot.restrict_chat_member(
                chat_id,
                user_id,
                permissions=ChatPermissions(can_send_messages=False),
                until_date=message.date.timestamp() + MUTE_DURATION
            )

            await message.reply_text("Лошарам слово не давали :D")

            # Через минуту снимаем мут
            await sleep(MUTE_DURATION)
            await context.bot.restrict_chat_member(
                chat_id,
                user_id,
                permissions=ChatPermissions(can_send_messages=True)
            )
        except Exception as e:
            print(f"[mute_random_handler] Ошибка: {e}")
