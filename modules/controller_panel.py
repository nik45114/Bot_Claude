"""
Модуль панели контролёра
Автор: Club Assistant Bot
Дата: 2025-11-09
"""

import logging
import sqlite3
from datetime import datetime, timezone, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CallbackQueryHandler

logger = logging.getLogger(__name__)

# Moscow timezone (UTC+3)
MSK = timezone(timedelta(hours=3))


async def show_controller_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать панель контролёра"""
    query = update.callback_query
    if query:
        await query.answer()

    db_path = context.bot_data.get('db_path', '/opt/club_assistant/club_assistant.db')

    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Получаем открытые смены
        cursor.execute("""
            SELECT a.id, a.admin_id, a.club, a.shift_type, a.opened_at, ad.full_name
            FROM active_shifts a
            LEFT JOIN admins ad ON a.admin_id = ad.user_id
            WHERE a.status = 'open'
            ORDER BY a.opened_at DESC
        """)
        active_shifts = cursor.fetchall()

        # Получаем последние закрытые смены (за сегодня)
        today = datetime.now(MSK).date()
        cursor.execute("""
            SELECT f.shift_id, f.admin_id, f.club, f.shift_type, f.closed_at,
                   f.total_revenue, f.total_expenses, ad.full_name
            FROM finmon_shifts f
            LEFT JOIN admins ad ON f.admin_id = ad.user_id
            WHERE DATE(f.closed_at, '+3 hours') = ?
            ORDER BY f.closed_at DESC
            LIMIT 10
        """, (today.isoformat(),))
        closed_shifts = cursor.fetchall()

        # Получаем график дежурств на сегодня
        cursor.execute("""
            SELECT d.admin_id, d.club, d.shift_type, d.admin_name
            FROM duty_schedule d
            WHERE d.date = ?
            ORDER BY d.club, d.shift_type
        """, (today.isoformat(),))
        duty_schedule = cursor.fetchall()

        conn.close()

        # Формируем текст (без Markdown - используем HTML)
        text = f"👁 <b>Панель большого брата</b>\n\n"
        text += f"📅 {today.strftime('%d.%m.%Y')}\n\n"

        # Открытые смены
        text += f"🟢 <b>Открытые смены ({len(active_shifts)}):</b>\n"
        if active_shifts:
            for shift in active_shifts:
                opened_time = datetime.fromisoformat(shift['opened_at']).astimezone(MSK).strftime('%H:%M')
                admin_name = shift['full_name'] or f"ID:{shift['admin_id']}"
                shift_emoji = "☀️" if shift['shift_type'] == 'morning' else "🌙"
                text += f"  {shift_emoji} {shift['club']} - {admin_name} (с {opened_time})\n"
        else:
            text += "  <i>Нет открытых смен</i>\n"

        text += f"\n📊 <b>Закрытые смены сегодня ({len(closed_shifts)}):</b>\n"
        if closed_shifts:
            for shift in closed_shifts[:5]:  # Показываем только 5 последних
                closed_time = datetime.fromisoformat(shift['closed_at']).astimezone(MSK).strftime('%H:%M')
                admin_name = shift['full_name'] or f"ID:{shift['admin_id']}"
                shift_emoji = "☀️" if shift['shift_type'] == 'morning' else "🌙"
                revenue = shift['total_revenue'] or 0
                text += f"  {shift_emoji} {shift['club']} - {admin_name}: {revenue:,.0f}₽ ({closed_time})\n"
        else:
            text += "  <i>Нет закрытых смен</i>\n"

        text += f"\n📋 <b>График дежурств на сегодня:</b>\n"
        if duty_schedule:
            for duty in duty_schedule:
                admin_name = duty['admin_name'] or f"ID:{duty['admin_id']}" if duty['admin_id'] else "Не назначено"
                shift_emoji = "☀️" if duty['shift_type'] == 'morning' else "🌙"
                text += f"  {shift_emoji} {duty['club']} - {admin_name}\n"
        else:
            text += "  <i>График не заполнен</i>\n"

    except Exception as e:
        logger.error(f"Error in show_controller_panel: {e}")
        text = f"👁 **Панель большого брата**\n\n❌ Ошибка загрузки данных: {e}"

    keyboard = [
        [InlineKeyboardButton("🔄 Обновить", callback_data="controller_panel")],
        [InlineKeyboardButton("◀️ Назад в главное меню", callback_data="main_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    if query:
        try:
            await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='HTML')
        except Exception as e:
            logger.error(f"Error editing message: {e}")
            await query.message.reply_text(text, reply_markup=reply_markup, parse_mode='HTML')
    else:
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='HTML')


async def handle_controller_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик callback для панели контролёра"""
    query = update.callback_query
    await query.answer()

    if query.data == "controller_panel":
        await show_controller_panel(update, context)
        return

    # Кнопка назад
    if query.data == "main_menu":
        # Возвращаем в главное меню - обработается в основном обработчике
        return


def create_controller_callback_handler():
    """Создать обработчик для callback кнопок контролёра"""
    return CallbackQueryHandler(
        handle_controller_callback,
        pattern="^(controller_panel)$"
    )
