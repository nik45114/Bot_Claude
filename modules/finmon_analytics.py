"""
Финансовая аналитика - просмотр данных в Telegram
"""

import logging
import sqlite3
from datetime import datetime, timedelta, timezone
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)
MSK = timezone(timedelta(hours=3))

async def show_finance_analytics(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать финансовую аналитику"""
    query = update.callback_query
    if query:
        await query.answer()

    user_id = update.effective_user.id
    owner_id = context.bot_data.get('owner_id')

    if user_id != owner_id:
        text = "❌ Доступ запрещен"
        if query:
            await query.answer(text, show_alert=True)
        return

    db_path = context.bot_data.get('db_path', 'club_assistant.db')
    
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        today = datetime.now(MSK).date()
        week_ago = today - timedelta(days=7)

        cursor.execute("""
            SELECT COUNT(*) as c, SUM(total_revenue) as r 
            FROM finmon_shifts WHERE DATE(closed_at) = ?
        """, (today.isoformat(),))
        today_stats = cursor.fetchone()

        cursor.execute("""
            SELECT COUNT(*) as c, SUM(total_revenue) as r
            FROM finmon_shifts WHERE DATE(closed_at) >= ?
        """, (week_ago.isoformat(),))
        week_stats = cursor.fetchone()

        conn.close()

        text = "📊 <b>Финансовая аналитика</b>\n\n"
        text += f"📅 Сегодня: {today_stats['c'] or 0} смен, {today_stats['r'] or 0:,.0f} ₽\n"
        text += f"📈 За 7 дней: {week_stats['c'] or 0} смен, {week_stats['r'] or 0:,.0f} ₽\n"

        keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data="main_menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        if query:
            await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='HTML')
        else:
            await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='HTML')
    except Exception as e:
        logger.error(f"Error: {e}")

def create_finance_analytics_handlers():
    from telegram.ext import CallbackQueryHandler
    return [CallbackQueryHandler(show_finance_analytics, pattern="^finance_analytics$")]
