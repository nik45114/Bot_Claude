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
            SELECT f.id, f.admin_id, f.club, f.shift_type, f.closed_at,
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
        [InlineKeyboardButton("📋 Текущие чек-листы", callback_data="ctrl_current_checklists")],
        [InlineKeyboardButton("📂 Архив отчётов", callback_data="ctrl_archive")],
        [InlineKeyboardButton("👁 Чек-лист Глаза", callback_data="ctrl_duty_checklist")],
        [InlineKeyboardButton("🔍 Проверка клубов", callback_data="ctrl_club_check")],
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


async def show_current_checklists_club_select(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать выбор клуба для просмотра текущих чек-листов"""
    query = update.callback_query
    await query.answer()

    text = "📋 <b>Текущие чек-листы админов</b>\n\n"
    text += "Выберите клуб:"

    keyboard = [
        [InlineKeyboardButton("🏔 Север", callback_data="ctrl_club_checklist_Север")],
        [InlineKeyboardButton("🌊 Рио", callback_data="ctrl_club_checklist_Рио")],
        [InlineKeyboardButton("◀️ Назад", callback_data="controller_panel")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='HTML')


async def show_current_checklists(update: Update, context: ContextTypes.DEFAULT_TYPE, club: str):
    """Показать текущие чек-листы админов для выбранного клуба"""
    query = update.callback_query
    await query.answer()

    db_path = context.bot_data.get('db_path', '/opt/club_assistant/club_assistant.db')

    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Получаем активные смены для выбранного клуба
        cursor.execute("""
            SELECT a.id, a.admin_id, a.shift_type, a.opened_at, ad.full_name
            FROM active_shifts a
            LEFT JOIN admins ad ON a.admin_id = ad.user_id
            WHERE a.status = 'open' AND a.club = ?
            ORDER BY a.opened_at DESC
        """, (club,))
        active_shifts = cursor.fetchall()

        text = f"📋 <b>Текущие чек-листы - {club}</b>\n\n"

        if not active_shifts:
            text += "<i>Нет открытых смен</i>"
        else:
            for shift in active_shifts:
                admin_name = shift['full_name'] or f"ID:{shift['admin_id']}"
                shift_emoji = "☀️" if shift['shift_type'] == 'morning' else "🌙"
                opened_time = datetime.fromisoformat(shift['opened_at']).astimezone(MSK).strftime('%H:%M')

                # Получаем прогресс чек-листа
                cursor.execute("""
                    SELECT COUNT(*) as total,
                           SUM(CASE WHEN status = 'ok' THEN 1 ELSE 0 END) as checked
                    FROM shift_checklist_responses
                    WHERE shift_id = ?
                """, (shift['id'],))
                progress = cursor.fetchone()

                total = progress['total'] or 0
                checked = progress['checked'] or 0

                if total > 0:
                    percent = int((checked / total) * 100)
                    progress_bar = "🟢" * (percent // 20) + "⚪" * (5 - percent // 20)
                    status = f"{progress_bar} {checked}/{total} ({percent}%)"
                else:
                    status = "❌ Не начат"

                text += f"{shift_emoji} <b>{admin_name}</b>\n"
                text += f"   Открыта: {opened_time}\n"
                text += f"   Прогресс: {status}\n\n"

        conn.close()

        keyboard = [
            [InlineKeyboardButton("🔄 Обновить", callback_data=f"ctrl_club_checklist_{club}")],
            [InlineKeyboardButton("◀️ Назад", callback_data="ctrl_current_checklists")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='HTML')

    except Exception as e:
        logger.error(f"Error in show_current_checklists: {e}")
        await query.edit_message_text(f"❌ Ошибка: {e}", parse_mode='HTML')




async def show_club_check_select(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать выбор клуба для проверки"""
    query = update.callback_query
    await query.answer()

    text = "🔍 <b>Проверка клубов</b>\n\n"
    text += "Выберите клуб для проверки:"

    keyboard = [
        [InlineKeyboardButton("🏔 Север", callback_data="ctrl_check_Север")],
        [InlineKeyboardButton("🌊 Рио", callback_data="ctrl_check_Рио")],
        [InlineKeyboardButton("◀️ Назад", callback_data="controller_panel")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='HTML')


async def show_club_check(update: Update, context: ContextTypes.DEFAULT_TYPE, club: str):
    """Показать проверку клуба (чек-лист дежурного для выбранного клуба)"""
    query = update.callback_query
    await query.answer()

    db_path = context.bot_data.get('db_path', '/opt/club_assistant/club_assistant.db')

    try:
        # Импортируем DutyShiftManager
        from modules.duty_shift_manager import DutyShiftManager
        duty_manager = DutyShiftManager(db_path)

        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        today = datetime.now(MSK).date()
        duty_person = duty_manager.get_current_duty_person(today)

        # Получаем смену дежурного на сегодня
        cursor.execute("""
            SELECT id, user_id, username, shift_date, started_at, ended_at
            FROM duty_shifts
            WHERE shift_date = ?
            ORDER BY id DESC
            LIMIT 1
        """, (today,))
        duty_shift = cursor.fetchone()

        text = f"🔍 <b>Проверка клуба {club}</b>\n\n"
        text += f"👤 Дежурный: {duty_person}\n"
        text += f"📅 Дата: {today.strftime('%d.%m.%Y')}\n\n"

        if duty_shift:
            # Получаем пункты чек-листа для этого клуба
            cursor.execute("""
                SELECT dci.id, dci.item_name, dci.category, dcp.checked, dcp.notes
                FROM duty_checklist_items dci
                LEFT JOIN duty_checklist_progress dcp ON dci.id = dcp.item_id AND dcp.shift_id = ?
                WHERE dci.is_active = 1
                ORDER BY dci.category, dci.sort_order
            """, (duty_shift['id'],))
            all_items = cursor.fetchall()

            # Группируем по категориям
            categories = {}
            for item in all_items:
                cat = item['category'] or 'Общее'
                if cat not in categories:
                    categories[cat] = []
                categories[cat].append(item)

            # Выводим по категориям
            for category, items in categories.items():
                text += f"<b>{category}:</b>\n"
                for item in items:
                    if item['checked']:
                        status = "✅"
                    else:
                        status = "⚪"
                    text += f"  {status} {item['item_name']}"
                    if item['notes']:
                        text += f" - <i>{item['notes']}</i>"
                    text += "\n"
                text += "\n"

            # Считаем прогресс
            total = len(all_items)
            checked = sum(1 for item in all_items if item['checked'])
            percent = int((checked / total) * 100) if total > 0 else 0
            text += f"<b>Прогресс:</b> {checked}/{total} ({percent}%)\n"
        else:
            text += "<i>Смена дежурного не открыта</i>\n"

        conn.close()

        keyboard = [
            [InlineKeyboardButton("🔄 Обновить", callback_data=f"ctrl_check_{club}")],
            [InlineKeyboardButton("◀️ Назад", callback_data="ctrl_club_check")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='HTML')

    except Exception as e:
        logger.error(f"Error in show_club_check: {e}")
        await query.edit_message_text(f"❌ Ошибка: {e}", parse_mode='HTML')


async def show_archive_years(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать выбор года для архива"""
    query = update.callback_query
    await query.answer()

    db_path = context.bot_data.get('db_path', '/opt/club_assistant/club_assistant.db')

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Получаем все годы, в которых есть закрытые смены
        cursor.execute("""
            SELECT DISTINCT strftime('%Y', closed_at, '+3 hours') as year
            FROM finmon_shifts
            WHERE closed_at IS NOT NULL
            ORDER BY year DESC
        """)
        years = [row[0] for row in cursor.fetchall()]
        conn.close()

        text = "📂 <b>Архив отчётов</b>\n\n"
        text += "Выберите год:"

        keyboard = []
        for year in years:
            keyboard.append([InlineKeyboardButton(f"📅 {year}", callback_data=f"ctrl_year_{year}")])

        keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data="controller_panel")])
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='HTML')

    except Exception as e:
        logger.error(f"Error in show_archive_years: {e}")
        await query.edit_message_text(f"❌ Ошибка: {e}", parse_mode='HTML')


async def show_archive_months(update: Update, context: ContextTypes.DEFAULT_TYPE, year: str):
    """Показать выбор месяца для архива"""
    query = update.callback_query
    await query.answer()

    db_path = context.bot_data.get('db_path', '/opt/club_assistant/club_assistant.db')

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Получаем все месяцы в выбранном году
        cursor.execute("""
            SELECT DISTINCT strftime('%m', closed_at, '+3 hours') as month
            FROM finmon_shifts
            WHERE strftime('%Y', closed_at, '+3 hours') = ?
            AND closed_at IS NOT NULL
            ORDER BY month DESC
        """, (year,))
        months = [row[0] for row in cursor.fetchall()]
        conn.close()

        month_names = {
            '01': 'Январь', '02': 'Февраль', '03': 'Март', '04': 'Апрель',
            '05': 'Май', '06': 'Июнь', '07': 'Июль', '08': 'Август',
            '09': 'Сентябрь', '10': 'Октябрь', '11': 'Ноябрь', '12': 'Декабрь'
        }

        text = f"📂 <b>Архив отчётов - {year}</b>\n\n"
        text += "Выберите месяц:"

        keyboard = []
        for month in months:
            month_name = month_names.get(month, month)
            keyboard.append([InlineKeyboardButton(f"📆 {month_name}", callback_data=f"ctrl_month_{year}_{month}")])

        keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data="ctrl_archive")])
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='HTML')

    except Exception as e:
        logger.error(f"Error in show_archive_months: {e}")
        await query.edit_message_text(f"❌ Ошибка: {e}", parse_mode='HTML')


async def show_archive_days(update: Update, context: ContextTypes.DEFAULT_TYPE, year: str, month: str):
    """Показать выбор дня для архива"""
    query = update.callback_query
    await query.answer()

    db_path = context.bot_data.get('db_path', '/opt/club_assistant/club_assistant.db')

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Получаем все дни в выбранном месяце
        cursor.execute("""
            SELECT DISTINCT strftime('%d', closed_at, '+3 hours') as day
            FROM finmon_shifts
            WHERE strftime('%Y', closed_at, '+3 hours') = ?
            AND strftime('%m', closed_at, '+3 hours') = ?
            AND closed_at IS NOT NULL
            ORDER BY day DESC
        """, (year, month))
        days = [row[0] for row in cursor.fetchall()]
        conn.close()

        month_names = {
            '01': 'Январь', '02': 'Февраль', '03': 'Март', '04': 'Апрель',
            '05': 'Май', '06': 'Июнь', '07': 'Июль', '08': 'Август',
            '09': 'Сентябрь', '10': 'Октябрь', '11': 'Ноябрь', '12': 'Декабрь'
        }

        text = f"📂 <b>Архив отчётов - {month_names.get(month, month)} {year}</b>\n\n"
        text += "Выберите день:"

        keyboard = []
        for day in days:
            keyboard.append([InlineKeyboardButton(f"📅 {day}.{month}.{year}", callback_data=f"ctrl_day_{year}_{month}_{day}")])

        keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data=f"ctrl_year_{year}")])
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='HTML')

    except Exception as e:
        logger.error(f"Error in show_archive_days: {e}")
        await query.edit_message_text(f"❌ Ошибка: {e}", parse_mode='HTML')


async def show_archive_shifts(update: Update, context: ContextTypes.DEFAULT_TYPE, year: str, month: str, day: str):
    """Показать выбор смены для просмотра отчёта"""
    query = update.callback_query
    await query.answer()

    db_path = context.bot_data.get('db_path', '/opt/club_assistant/club_assistant.db')

    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Получаем все смены в выбранный день
        date_str = f"{year}-{month}-{day}"
        cursor.execute("""
            SELECT f.id, f.club, f.shift_type, f.total_revenue,
                   f.closed_at, ad.full_name, f.admin_id
            FROM finmon_shifts f
            LEFT JOIN admins ad ON f.admin_id = ad.user_id
            WHERE DATE(f.closed_at, '+3 hours') = ?
            ORDER BY f.closed_at
        """, (date_str,))
        shifts = cursor.fetchall()
        conn.close()

        text = f"📂 <b>Архив отчётов - {day}.{month}.{year}</b>\n\n"
        text += "Выберите смену для просмотра:"

        keyboard = []
        for shift in shifts:
            shift_emoji = "☀️" if shift['shift_type'] == 'morning' else "🌙"
            admin_name = shift['full_name'] or f"ID:{shift['admin_id']}"
            revenue = shift['total_revenue'] or 0
            closed_time = datetime.fromisoformat(shift['closed_at']).astimezone(MSK).strftime('%H:%M')

            button_text = f"{shift_emoji} {shift['club']} - {admin_name} ({revenue:,.0f}₽, {closed_time})"
            keyboard.append([InlineKeyboardButton(button_text, callback_data=f"ctrl_shift_{shift['id']}")])

        keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data=f"ctrl_month_{year}_{month}")])
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='HTML')

    except Exception as e:
        logger.error(f"Error in show_archive_shifts: {e}")
        await query.edit_message_text(f"❌ Ошибка: {e}", parse_mode='HTML')


async def show_shift_report(update: Update, context: ContextTypes.DEFAULT_TYPE, shift_id: int):
    """Показать полный отчёт по смене с фотографиями и чек-листом"""
    query = update.callback_query
    await query.answer()

    db_path = context.bot_data.get('db_path', '/opt/club_assistant/club_assistant.db')

    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Получаем данные смены
        cursor.execute("""
            SELECT f.*, ad.full_name
            FROM finmon_shifts f
            LEFT JOIN admins ad ON f.admin_id = ad.user_id
            WHERE f.id = ?
        """, (shift_id,))
        shift = cursor.fetchone()

        if not shift:
            await query.edit_message_text("❌ Смена не найдена", parse_mode='HTML')
            return

        # Формируем отчёт
        shift_date = datetime.fromisoformat(shift['closed_at']).astimezone(MSK)
        shift_emoji = "☀️" if shift['shift_type'] == 'morning' else "🌙"
        admin_name = shift['full_name'] or f"ID:{shift['admin_id']}"

        text = f"📊 <b>Отчёт по смене</b>\n\n"
        text += f"📅 Дата: {shift_date.strftime('%d.%m.%Y')}\n"
        text += f"{shift_emoji} Смена: {shift['shift_type']} ({shift['club']})\n"
        text += f"👤 Администратор: {admin_name}\n"
        text += f"🕐 Закрыта: {shift_date.strftime('%H:%M')}\n\n"

        text += f"💰 <b>Выручка:</b>\n"
        text += f"  💵 Наличные: {shift['cash_revenue'] or 0:,.0f}₽\n"
        text += f"  💳 Карта: {shift['card_revenue'] or 0:,.0f}₽\n"
        text += f"  📱 QR: {shift['qr_revenue'] or 0:,.0f}₽\n"
        if shift['card2_revenue']:
            text += f"  💳 Карта 2: {shift['card2_revenue']:,.0f}₽\n"
        text += f"  <b>Всего: {shift['total_revenue'] or 0:,.0f}₽</b>\n\n"

        text += f"💼 <b>Остатки:</b>\n"
        text += f"  🔒 Сейф начало: {shift['safe_cash_start'] or 0:,.0f}₽\n"
        text += f"  🔒 Сейф конец: {shift['safe_cash_end'] or 0:,.0f}₽\n"
        text += f"  📦 Бокс начало: {shift['box_cash_start'] or 0:,.0f}₽\n"
        text += f"  📦 Бокс конец: {shift['box_cash_end'] or 0:,.0f}₽\n\n"

        if shift['total_expenses']:
            text += f"💸 Расходы: {shift['total_expenses']:,.0f}₽\n\n"

        if shift['notes']:
            text += f"📝 Примечания: {shift['notes']}\n\n"

        # Получаем чек-лист смены с именами пунктов
        cursor.execute("""
            SELECT scr.status, scr.notes, sci.item_name
            FROM shift_checklist_responses scr
            JOIN shift_checklist_items sci ON scr.item_id = sci.id
            WHERE scr.shift_id = ?
            ORDER BY scr.id
        """, (shift['active_shift_id'],))
        checklist_items = cursor.fetchall()

        if checklist_items:
            text += f"✅ <b>Чек-лист приёма смены ({len(checklist_items)} пунктов):</b>\n"
            for item in checklist_items:
                status = "✅" if item['status'] == 'ok' else "❌"
                text += f"  {status} {item['item_name']}"
                if item['notes']:
                    text += f" ({item['notes']})"
                text += "\n"
            text += "\n"

        conn.close()

        # Кнопка назад
        shift_date_parts = shift_date.strftime('%Y_%m_%d').split('_')
        keyboard = [[InlineKeyboardButton("◀️ Назад к списку смен",
                                          callback_data=f"ctrl_day_{shift_date_parts[0]}_{shift_date_parts[1]}_{shift_date_parts[2]}")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        # Отправляем текстовый отчёт
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='HTML')

        # Отправляем фотографии Z-отчётов
        photos_to_send = []
        photo_captions = []

        if shift['z_report_cash_photo']:
            photos_to_send.append(shift['z_report_cash_photo'])
            photo_captions.append("💵 Z-отчёт: Наличные")

        if shift['z_report_card_photo']:
            photos_to_send.append(shift['z_report_card_photo'])
            photo_captions.append("💳 Z-отчёт: Карта")

        if shift['z_report_qr_photo']:
            photos_to_send.append(shift['z_report_qr_photo'])
            photo_captions.append("📱 Z-отчёт: QR-код")

        if shift['z_report_card2_photo']:
            photos_to_send.append(shift['z_report_card2_photo'])
            photo_captions.append("💳 Z-отчёт: Карта 2")

        # Отправляем фотографии
        for photo_id, caption in zip(photos_to_send, photo_captions):
            try:
                await query.message.reply_photo(photo=photo_id, caption=caption)
            except Exception as e:
                logger.error(f"Error sending photo: {e}")
                await query.message.reply_text(f"⚠️ Ошибка загрузки фото: {caption}")

    except Exception as e:
        logger.error(f"Error in show_shift_report: {e}")
        await query.edit_message_text(f"❌ Ошибка загрузки отчёта: {e}", parse_mode='HTML')


async def handle_controller_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик callback для панели контролёра"""
    query = update.callback_query
    data = query.data

    if data == "controller_panel":
        await show_controller_panel(update, context)
        return

    # Текущие чек-листы админов
    if data == "ctrl_current_checklists":
        await show_current_checklists_club_select(update, context)
        return

    if data.startswith("ctrl_club_checklist_"):
        club = data.replace("ctrl_club_checklist_", "")
        await show_current_checklists(update, context, club)
        return

    # Чек-лист дежурного - используем оригинальную функцию из duty_shift_manager
    if data == "ctrl_duty_checklist":
        from modules.duty_shift_manager import show_duty_checklist
        await show_duty_checklist(update, context)
        return

    # Проверка клубов
    if data == "ctrl_club_check":
        await show_club_check_select(update, context)
        return

    if data.startswith("ctrl_check_"):
        club = data.replace("ctrl_check_", "")
        await show_club_check(update, context, club)
        return

    # Архив отчётов
    if data == "ctrl_archive":
        await show_archive_years(update, context)
        return

    if data.startswith("ctrl_year_"):
        year = data.split("_")[2]
        await show_archive_months(update, context, year)
        return

    if data.startswith("ctrl_month_"):
        parts = data.split("_")
        year, month = parts[2], parts[3]
        await show_archive_days(update, context, year, month)
        return

    if data.startswith("ctrl_day_"):
        parts = data.split("_")
        year, month, day = parts[2], parts[3], parts[4]
        await show_archive_shifts(update, context, year, month, day)
        return

    if data.startswith("ctrl_shift_"):
        shift_id = int(data.split("_")[2])
        await show_shift_report(update, context, shift_id)
        return

    # Кнопка назад
    if data == "main_menu":
        # Возвращаем в главное меню - обработается в основном обработчике
        return


def create_controller_callback_handler():
    """Создать обработчик для callback кнопок контролёра"""
    return CallbackQueryHandler(
        handle_controller_callback,
        pattern="^(controller_panel|ctrl_archive|ctrl_year_|ctrl_month_|ctrl_day_|ctrl_shift_)"
    )
