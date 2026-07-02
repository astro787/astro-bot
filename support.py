from telegram import Update
from telegram.ext import ContextTypes
from config import ADMIN_ID

async def support_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("💬 *Поддержка АстроБота*\n\nНапишите ваш вопрос, и я передам его астрологу.\nОтвет придёт в течение нескольких часов.", parse_mode='Markdown')

async def forward_to_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user; msg = update.message
    text = f"📩 *Новое сообщение*\n👤 *{user.full_name}* (@{user.username or 'нет'})\n🆔 `{user.id}`\n💬 {msg.text}\n\n_Ответить:_ `/reply {user.id} текст`"
    await context.bot.send_message(chat_id=ADMIN_ID, text=text, parse_mode='Markdown')
    await msg.reply_text("✅ *Отправлено!* Астролог ответит в ближайшее время.", parse_mode='Markdown')

async def reply_to_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Нет доступа."); return
    args = update.message.text.split(maxsplit=2)
    if len(args) < 3:
        await update.message.reply_text("❌ Формат: `/reply ID текст`"); return
    try:
        user_id = int(args[1])
        await context.bot.send_message(chat_id=user_id, text=f"💬 *Ответ от астролога:*\n\n{args[2]}\n\n─ @Astromasbot", parse_mode='Markdown')
        await update.message.reply_text(f"✅ Ответ отправлен пользователю {user_id}")
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: {e}")
