"""
Модуль просмотра данных смены
Показывает все данные по смене в формате Telegram-сообщения
Автор: Club Assistant Bot
Дата: 2025-11-12
"""

import logging
import sqlite3
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, List
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)

# Moscow timezone (UTC+3)
MSK = timezone(timedelta(hours=3))


async def show_shift_data_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать меню выбора смены для просмотра данных"""
    query = update.callback_query
    if query:
        await query.answer()

    user_id = update.effective_user.id
    db_path = context.bot_data.get('db_path', 'club_assistant.db')

    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Получаем последние 10 смен пользователя
        cursor.execute("""
            SELECT
                s.id, s.admin_id, s.club, s.shift_type, s.shift_date,
                s.opened_at, s.closed_at, s.status,
                a.full_name as admin_name
            FROM active_shifts s
            LEFT JOIN admins a ON s.admin_id = a.user_id
            WHERE s.admin_id = ? OR s.confirmed_by = ?
            ORDER BY s.opened_at DESC
            LIMIT 10
        """, (user_id, user_id))

        shifts = cursor.fetchall()
        conn.close()

        if not shifts:
            text = "❌ У вас пока нет смен для просмотра"
            keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data="main_menu")]]
            reply_markup = InlineKeyboardMarkup(keyboard)

            if query:
                await query.edit_message_text(text, reply_markup=reply_markup)
            else:
                await update.message.reply_text(text, reply_markup=reply_markup)
            return

        text = "📊 <b>Просмотр данных смен</b>\n\n"
        text += "Выберите смену для просмотра:\n\n"

        keyboard = []
        for shift in shifts:
            shift_id = shift['id']
            club = shift['club'].upper()
            shift_type_emoji = "☀️" if shift['shift_type'] == 'morning' else "🌙"
            shift_date = shift['shift_date']
            status_emoji = "🟢" if shift['status'] == 'open' else "⚪️"

            label = f"{status_emoji} {shift_type_emoji} {club} - {shift_date}"
            keyboard.append([InlineKeyboardButton(label, callback_data=f"view_shift_{shift_id}")])

        keyboard.append([InlineKeyboardButton("◀️ Назад в меню", callback_data="main_menu")])
        reply_markup = InlineKeyboardMarkup(keyboard)

        if query:
            await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='HTML')
        else:
            await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='HTML')

    except Exception as e:
        logger.error(f"❌ Error showing shift data menu: {e}")
        error_text = f"❌ Ошибка загрузки меню: {e}"
        if query:
            await query.edit_message_text(error_text)
        else:
            await update.message.reply_text(error_text)


async def show_shift_details(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать детальную информацию о смене"""
    query = update.callback_query
    await query.answer()

    # Извлекаем shift_id из callback_data
    shift_id = int(query.data.split('_')[-1])
    db_path = context.bot_data.get('db_path', 'club_assistant.db')

    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Получаем основную информацию о смене
        cursor.execute("""
            SELECT
                s.id, s.admin_id, s.club, s.shift_type, s.shift_date,
                s.opened_at, s.closed_at, s.status, s.confirmed_by,
                a.full_name as admin_name,
                c.full_name as confirmer_name
            FROM active_shifts s
            LEFT JOIN admins a ON s.admin_id = a.user_id
            LEFT JOIN admins c ON s.confirmed_by = c.user_id
            WHERE s.id = ?
        """, (shift_id,))

        shift = cursor.fetchone()

        if not shift:
            await query.edit_message_text("❌ Смена не найдена")
            conn.close()
            return

        # Формируем текст с данными смены
        text = "📊 <b>Данные смены</b>\n\n"

        # Основная информация
        club_emoji = "🏢"
        shift_type_emoji = "☀️" if shift['shift_type'] == 'morning' else "🌙"
        shift_type_text = "Дневная" if shift['shift_type'] == 'morning' else "Ночная"
        status_emoji = "🟢" if shift['status'] == 'open' else "⚪️"
        status_text = "Открыта" if shift['status'] == 'open' else "Закрыта"

        text += f"{club_emoji} <b>Клуб:</b> {shift['club'].upper()}\n"
        text += f"{shift_type_emoji} <b>Тип смены:</b> {shift_type_text}\n"
        text += f"📅 <b>Дата:</b> {shift['shift_date']}\n"
        text += f"{status_emoji} <b>Статус:</b> {status_text}\n"
        text += f"👤 <b>Админ:</b> {shift['admin_name'] or 'Неизвестно'}\n"

        if shift['confirmer_name']:
            text += f"✅ <b>Подтвердил:</b> {shift['confirmer_name']}\n"

        opened_at = datetime.fromisoformat(shift['opened_at']).strftime('%d.%m.%Y %H:%M')
        text += f"🕐 <b>Открыта:</b> {opened_at}\n"

        if shift['closed_at']:
            closed_at = datetime.fromisoformat(shift['closed_at']).strftime('%d.%m.%Y %H:%M')
            text += f"🕐 <b>Закрыта:</b> {closed_at}\n"

        # Расходы смены
        cursor.execute("""
            SELECT cash_source, amount, reason, created_at
            FROM shift_expenses
            WHERE shift_id = ?
            ORDER BY created_at ASC
        """, (shift_id,))

        expenses = cursor.fetchall()

        if expenses:
            text += "\n💸 <b>Расходы смены:</b>\n"
            total_main = 0
            total_box = 0

            for exp in expenses:
                amount = exp['amount']
                source = exp['cash_source']
                reason = exp['reason']
                source_text = "Основная касса" if source == 'main' else "Коробка"

                text += f"  • {amount:,.0f} ₽ из {source_text}\n"
                text += f"    <i>{reason}</i>\n"

                if source == 'main':
                    total_main += amount
                else:
                    total_box += amount

            text += f"\n<b>Итого расходов:</b>\n"
            if total_main > 0:
                text += f"  • Основная касса: {total_main:,.0f} ₽\n"
            if total_box > 0:
                text += f"  • Коробка: {total_box:,.0f} ₽\n"
            text += f"  <b>Всего: {total_main + total_box:,.0f} ₽</b>\n"

        # Рейтинг уборки (Чек-лист #1)
        cursor.execute("""
            SELECT bar_cleaned, hall_cleaned, notes, rated_at,
                   bar_photo_file_id, hall_photo_file_id
            FROM shift_cleaning_rating
            WHERE shift_id = ? AND rated_at IS NOT NULL
        """, (shift_id,))

        rating = cursor.fetchone()

        if rating:
            text += "\n🧹 <b>Рейтинг уборки:</b>\n"

            if rating['bar_cleaned'] is not None:
                bar_stars = "⭐️" * rating['bar_cleaned']
                text += f"  • Бар: {bar_stars} ({rating['bar_cleaned']}/5)\n"

            if rating['hall_cleaned'] is not None:
                hall_stars = "⭐️" * rating['hall_cleaned']
                text += f"  • Зал: {hall_stars} ({rating['hall_cleaned']}/5)\n"

            if rating['notes']:
                text += f"  📝 Заметки: {rating['notes']}\n"

            if rating['rated_at']:
                rated_at = datetime.fromisoformat(rating['rated_at']).strftime('%d.%m.%Y %H:%M')
                text += f"  🕐 Оценен: {rated_at}\n"

        # Инвентарь (Чек-лист #2)
        cursor.execute("""
            SELECT computers_count, gamepads_count, broken_items,
                   missing_items, notes, submitted_at
            FROM shift_inventory_checklist
            WHERE shift_id = ? AND submitted_at IS NOT NULL
        """, (shift_id,))

        inventory = cursor.fetchone()

        if inventory:
            text += "\n📦 <b>Инвентарь:</b>\n"
            text += f"  • Компьютеры: {inventory['computers_count']}\n"
            text += f"  • Геймпады: {inventory['gamepads_count']}\n"

            if inventory['broken_items']:
                text += f"  ⚠️ Сломано: {inventory['broken_items']}\n"

            if inventory['missing_items']:
                text += f"  ❌ Отсутствует: {inventory['missing_items']}\n"

            if inventory['notes']:
                text += f"  📝 Заметки: {inventory['notes']}\n"

            if inventory['submitted_at']:
                submitted_at = datetime.fromisoformat(inventory['submitted_at']).strftime('%d.%m.%Y %H:%M')
                text += f"  🕐 Проверен: {submitted_at}\n"

        # Отзыв об уборщице (Чек-лист #3, только ночная смена)
        if shift['shift_type'] == 'evening':
            cursor.execute("""
                SELECT rating, review_text, cleaner_was_present,
                       photo_file_id, created_at
                FROM cleaning_service_reviews
                WHERE shift_id = ?
            """, (shift_id,))

            review = cursor.fetchone()

            if review:
                text += "\n⭐ <b>Отзыв об уборщице:</b>\n"

                if review['cleaner_was_present'] is not None:
                    presence_text = "✅ Была" if review['cleaner_was_present'] else "❌ Не была"
                    text += f"  • Присутствие: {presence_text}\n"

                if review['rating']:
                    stars = "⭐️" * review['rating']
                    text += f"  • Оценка: {stars} ({review['rating']}/5)\n"

                if review['review_text']:
                    text += f"  📝 Отзыв: {review['review_text']}\n"

                if review['created_at']:
                    created_at = datetime.fromisoformat(review['created_at']).strftime('%d.%m.%Y %H:%M')
                    text += f"  🕐 Оставлен: {created_at}\n"

        # Финансовые данные смены (если смена закрыта)
        if shift['status'] == 'closed':
            cursor.execute("""
                SELECT fact_cash, fact_card, qr, card2, safe_cash_end, box_cash_end,
                       total_revenue, total_expenses
                FROM finmon_shifts
                WHERE shift_id = ?
            """, (shift_id,))

            finmon = cursor.fetchone()

            if finmon:
                text += "\n💰 <b>Финансовые данные:</b>\n"
                text += f"  • Наличные: {finmon['fact_cash']:,.0f} ₽\n"
                text += f"  • Карта 1: {finmon['fact_card']:,.0f} ₽\n"
                text += f"  • QR: {finmon['qr']:,.0f} ₽\n"
                text += f"  • Карта 2: {finmon['card2']:,.0f} ₽\n"
                text += f"  <b>Выручка: {finmon['total_revenue']:,.0f} ₽</b>\n\n"

                text += f"<b>Остатки:</b>\n"
                text += f"  • Основная касса: {finmon['safe_cash_end']:,.0f} ₽\n"
                text += f"  • Коробка: {finmon['box_cash_end']:,.0f} ₽\n"

        conn.close()

        # Кнопки навигации
        keyboard = [
            [InlineKeyboardButton("🔄 Обновить", callback_data=f"view_shift_{shift_id}")],
            [InlineKeyboardButton("◀️ К списку смен", callback_data="shift_data_menu")],
            [InlineKeyboardButton("◀️ Главное меню", callback_data="main_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='HTML')

    except Exception as e:
        logger.error(f"❌ Error showing shift details: {e}")
        await query.edit_message_text(f"❌ Ошибка загрузки данных смены: {e}")


def create_shift_data_viewer_handlers():
    """Создать обработчики для просмотра данных смен"""
    from telegram.ext import CallbackQueryHandler

    return [
        CallbackQueryHandler(show_shift_data_menu, pattern="^shift_data_menu$"),
        CallbackQueryHandler(show_shift_details, pattern="^view_shift_\d+$")
    ]
