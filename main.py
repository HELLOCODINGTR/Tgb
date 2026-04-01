import logging
from datetime import datetime, time, timedelta
from collections import defaultdict
from telegram import Update, ChatPermissions
from telegram.ext import (
    ApplicationBuilder, MessageHandler, filters,
    ContextTypes, CommandHandler
)

TOKEN = "8443660295:AAFqgx4NYi7jICIDreqsXIQXCshqAT1U8Vg"

user_consecutive = defaultdict(list)
last_messages = defaultdict(str)
deleted_today = defaultdict(int)
muted_users = {}

logging.basicConfig(level=logging.INFO)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not msg.text:
        return

    user = msg.from_user
    chat_id = msg.chat_id
    user_id = user.id
    text = msg.text.strip()

    should_delete = False

    if last_messages[(chat_id, user_id)] == text:
        should_delete = True
    else:
        last_messages[(chat_id, user_id)] = text

    if msg.reply_to_message:
        user_consecutive[(chat_id, user_id)] = []
    else:
        user_consecutive[(chat_id, user_id)].append(msg.message_id)
        if len(user_consecutive[(chat_id, user_id)]) > 7:
            should_delete = True

    if should_delete:
        try:
            await context.bot.delete_message(chat_id=chat_id, message_id=msg.message_id)
            deleted_today[(chat_id, user_id)] += 1

            if deleted_today[(chat_id, user_id)] >= 20:
                if user_id not in muted_users:
                    await mute_user(context, chat_id, user_id, user.first_name)
                    muted_users[user_id] = chat_id
        except Exception as e:
            logging.error(f"Silme hatası: {e}")

async def mute_user(context, chat_id, user_id, name):
    now = datetime.now()
    midnight = datetime.combine(now.date() + timedelta(days=1), time(0, 0))
    await context.bot.restrict_chat_member(
        chat_id=chat_id,
        user_id=user_id,
        permissions=ChatPermissions(can_send_messages=False),
        until_date=midnight
    )
    await context.bot.send_message(
        chat_id=chat_id,
        text=f"⚠️ {name} bugün 20'den fazla tekrarlı mesaj attığı için gece 12:00'a kadar yazma hakkı askıya alındı."
    )

async def daily_report(context: ContextTypes.DEFAULT_TYPE):
    chat_id = context.job.chat_id
    if not deleted_today:
        await context.bot.send_message(chat_id=chat_id, text="📊 Bugün hiç tekrarlı mesaj tespit edilmedi.")
        return

    lines = ["📊 *Günlük Tekrarlı Mesaj Raporu*\n"]
    for (cid, uid), count in deleted_today.items():
        if cid == chat_id:
            try:
                member = await context.bot.get_chat_member(chat_id=cid, user_id=uid)
                name = member.user.first_name
            except:
                name = str(uid)
            lines.append(f"• {name}: {count} mesaj silindi")

    await context.bot.send_message(chat_id=chat_id, text="\n".join(lines), parse_mode="Markdown")

async def reset_daily(context: ContextTypes.DEFAULT_TYPE):
    deleted_today.clear()
    muted_users.clear()

async def setup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    jobs = context.job_queue

    jobs.run_daily(daily_report, time=time(10, 0), chat_id=chat_id, name=f"report_{chat_id}")
    jobs.run_daily(reset_daily, time=time(0, 0), chat_id=chat_id, name=f"reset_{chat_id}")

    await update.message.reply_text("✅ Bot aktif! Tekrarlı mesajlar izleniyor.")

if __name__ == "__main__":
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("setup", setup))
    app.add_handler(MessageHandler(filters.TEXT & filters.ChatType.GROUPS, handle_message))
    app.run_polling()