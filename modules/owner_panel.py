"""
Модуль панели владельца
Автор: Club Assistant Bot
Дата: 2025-11-10
"""

import logging
import sqlite3
import psutil
from datetime import datetime, timezone, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)

# Moscow timezone (UTC+3)
MSK = timezone(timedelta(hours=3))


async def show_owner_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать главную панель владельца"""
    query = update.callback_query
    if query:
        await query.answer()

    user_id = update.effective_user.id
    owner_id = context.bot_data.get('owner_id')

    # Проверка прав доступа
    if user_id != owner_id:
        text = "❌ Доступ запрещен. Эта панель только для владельца."
        if query:
            await query.answer(text, show_alert=True)
        else:
            await update.message.reply_text(text)
        return

    db_path = context.bot_data.get('db_path', '/opt/club_assistant/club_assistant.db')

    try:
        # Собираем системную информацию
        cpu_percent = psutil.cpu_percent(interval=0.5)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')

        # Определяем статусы
        cpu_status = "🟢" if cpu_percent < 70 else "🟡" if cpu_percent < 80 else "🔴"
        ram_status = "🟢" if memory.percent < 75 else "🟡" if memory.percent < 85 else "🔴"
        disk_status = "🟢" if disk.percent < 80 else "🟡" if disk.percent < 90 else "🔴"

        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Получаем статистику бота
        cursor.execute("SELECT COUNT(*) as count FROM admins")
        admins_count = cursor.fetchone()['count']

        cursor.execute("""
            SELECT COUNT(*) as count FROM active_shifts
            WHERE status = 'open'
        """)
        active_shifts_count = cursor.fetchone()['count']

        # Финансовая статистика за сегодня
        today = datetime.now(MSK).date()
        cursor.execute("""
            SELECT
                COUNT(*) as shifts_count,
                SUM(total_revenue) as total_revenue,
                SUM(total_expenses) as total_expenses
            FROM finmon_shifts
            WHERE DATE(closed_at, '+3 hours') = ?
        """, (today.isoformat(),))

        today_stats = cursor.fetchone()

        conn.close()

        # Формируем текст
        text = "👑 <b>Панель владельца</b>\n\n"
        text += f"📅 {datetime.now(MSK).strftime('%d.%m.%Y %H:%M')}\n\n"

        # Системный мониторинг
        text += "🖥 <b>Состояние системы:</b>\n"
        text += f"  {cpu_status} CPU: {cpu_percent:.1f}%\n"
        text += f"  {ram_status} RAM: {memory.percent:.1f}% ({memory.used / (1024**3):.1f}/{memory.total / (1024**3):.1f} GB)\n"
        text += f"  {disk_status} Диск: {disk.percent:.1f}% ({disk.used / (1024**3):.1f}/{disk.total / (1024**3):.1f} GB)\n\n"

        # Статистика бота
        text += "📊 <b>Статистика бота:</b>\n"
        text += f"  • Администраторов: {admins_count}\n"
        text += f"  • Открытых смен: {active_shifts_count}\n\n"

        # Финансы за сегодня
        text += "💰 <b>Финансы за сегодня:</b>\n"
        shifts_today = today_stats['shifts_count'] or 0
        revenue_today = today_stats['total_revenue'] or 0
        expenses_today = today_stats['total_expenses'] or 0

        text += f"  • Закрыто смен: {shifts_today}\n"
        text += f"  • Выручка: {revenue_today:,.0f} ₽\n"
        text += f"  • Расходы: {expenses_today:,.0f} ₽\n"
        text += f"  • Прибыль: {revenue_today - expenses_today:,.0f} ₽\n"

    except Exception as e:
        logger.error(f"Error in show_owner_panel: {e}")
        text = f"👑 <b>Панель владельца</b>\n\n❌ Ошибка загрузки данных: {e}"

    keyboard = [
        [InlineKeyboardButton("🔄 Обновить", callback_data="owner_panel")],
        [
            InlineKeyboardButton("📊 Финансы", callback_data="owner_finance"),
            InlineKeyboardButton("🧹 Отзывы", callback_data="reviews_all")
        ],
        [
            InlineKeyboardButton("⭐️ Рейтинги уборки", callback_data="owner_cleaning_ratings"),
            InlineKeyboardButton("📦 Инвентарь", callback_data="owner_inventory")
        ],
        [
            InlineKeyboardButton("📅 График дежурств", callback_data="ctrl_schedule"),
            InlineKeyboardButton("👁 Чек-лист Глаза", callback_data="ctrl_club_check")
        ],
        [InlineKeyboardButton("🔧 Задачи обслуживания", callback_data="maintenance_tasks")],
        [InlineKeyboardButton("◀️ Главное меню", callback_data="main_menu")]
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


async def show_owner_finance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать финансовую аналитику"""
    query = update.callback_query
    await query.answer()

    db_path = context.bot_data.get('db_path', '/opt/club_assistant/club_assistant.db')

    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Статистика за неделю
        week_ago = (datetime.now(MSK) - timedelta(days=7)).date()
        cursor.execute("""
            SELECT
                club,
                COUNT(*) as shifts_count,
                SUM(total_revenue) as total_revenue,
                SUM(total_expenses) as total_expenses,
                AVG(total_revenue) as avg_revenue
            FROM finmon_shifts
            WHERE DATE(closed_at, '+3 hours') >= ?
            GROUP BY club
        """, (week_ago.isoformat(),))

        week_stats = cursor.fetchall()

        # Статистика за месяц
        month_ago = (datetime.now(MSK) - timedelta(days=30)).date()
        cursor.execute("""
            SELECT
                club,
                COUNT(*) as shifts_count,
                SUM(total_revenue) as total_revenue,
                SUM(total_expenses) as total_expenses
            FROM finmon_shifts
            WHERE DATE(closed_at, '+3 hours') >= ?
            GROUP BY club
        """, (month_ago.isoformat(),))

        month_stats = cursor.fetchall()

        conn.close()

        text = "💰 <b>Финансовая аналитика</b>\n\n"

        text += "📅 <b>За последние 7 дней:</b>\n"
        if week_stats:
            for stat in week_stats:
                club = stat['club']
                shifts = stat['shifts_count']
                revenue = stat['total_revenue'] or 0
                expenses = stat['total_expenses'] or 0
                avg_rev = stat['avg_revenue'] or 0
                profit = revenue - expenses

                text += f"\n🏢 <b>{club.upper()}</b>\n"
                text += f"  • Смен: {shifts}\n"
                text += f"  • Выручка: {revenue:,.0f} ₽\n"
                text += f"  • Расходы: {expenses:,.0f} ₽\n"
                text += f"  • Прибыль: {profit:,.0f} ₽\n"
                text += f"  • Средняя выручка: {avg_rev:,.0f} ₽\n"
        else:
            text += "<i>Нет данных</i>\n"

        text += "\n📆 <b>За последние 30 дней:</b>\n"
        if month_stats:
            for stat in month_stats:
                club = stat['club']
                shifts = stat['shifts_count']
                revenue = stat['total_revenue'] or 0
                expenses = stat['total_expenses'] or 0
                profit = revenue - expenses

                text += f"\n🏢 <b>{club.upper()}</b>\n"
                text += f"  • Смен: {shifts}\n"
                text += f"  • Выручка: {revenue:,.0f} ₽\n"
                text += f"  • Расходы: {expenses:,.0f} ₽\n"
                text += f"  • Прибыль: {profit:,.0f} ₽\n"
        else:
            text += "<i>Нет данных</i>\n"

    except Exception as e:
        logger.error(f"Error in show_owner_finance: {e}")
        text = f"💰 <b>Финансовая аналитика</b>\n\n❌ Ошибка: {e}"

    keyboard = [
        [InlineKeyboardButton("◀️ Назад", callback_data="owner_panel")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='HTML')


async def show_owner_cleaning_ratings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать рейтинги уборки админов"""
    query = update.callback_query
    await query.answer()

    db_path = context.bot_data.get('db_path', '/opt/club_assistant/club_assistant.db')

    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Получаем статистику плохих оценок за месяц
        month_ago = (datetime.now(MSK) - timedelta(days=30)).date()

        cursor.execute("""
            SELECT
                scr.previous_admin_id,
                a.full_name,
                COUNT(*) as total_ratings,
                SUM(CASE WHEN scr.bar_cleaned = 0 THEN 1 ELSE 0 END) as bad_bar,
                SUM(CASE WHEN scr.hall_cleaned = 0 THEN 1 ELSE 0 END) as bad_hall
            FROM shift_cleaning_rating scr
            LEFT JOIN admins a ON scr.previous_admin_id = a.user_id
            WHERE DATE(scr.rated_at, '+3 hours') >= ?
            AND scr.previous_admin_id IS NOT NULL
            GROUP BY scr.previous_admin_id
            HAVING (bad_bar + bad_hall) > 0
            ORDER BY (bad_bar + bad_hall) DESC
            LIMIT 20
        """, (month_ago.isoformat(),))

        bad_ratings = cursor.fetchall()

        # Последние 10 оценок
        cursor.execute("""
            SELECT
                scr.*,
                a1.full_name as rater_name,
                a2.full_name as previous_name
            FROM shift_cleaning_rating scr
            LEFT JOIN admins a1 ON scr.rated_by_admin_id = a1.user_id
            LEFT JOIN admins a2 ON scr.previous_admin_id = a2.user_id
            WHERE scr.bar_cleaned IS NOT NULL AND scr.hall_cleaned IS NOT NULL
            ORDER BY scr.rated_at DESC
            LIMIT 10
        """)

        recent_ratings = cursor.fetchall()

        conn.close()

        text = "⭐️ <b>Рейтинги уборки админов</b>\n\n"

        text += "📊 <b>Плохие оценки за месяц:</b>\n"
        if bad_ratings:
            for rating in bad_ratings:
                admin_name = rating['full_name'] or f"ID:{rating['previous_admin_id']}"
                total = rating['total_ratings']
                bad_bar = rating['bad_bar']
                bad_hall = rating['bad_hall']
                bad_total = bad_bar + bad_hall

                text += f"\n👤 {admin_name}\n"
                text += f"  • Всего оценок: {total}\n"
                text += f"  • Плохих (бар): {bad_bar}\n"
                text += f"  • Плохих (зал): {bad_hall}\n"
                text += f"  • <b>Итого плохих: {bad_total}</b>\n"
        else:
            text += "<i>Нет плохих оценок</i>\n"

        text += "\n📋 <b>Последние 10 оценок:</b>\n"
        if recent_ratings:
            for rating in recent_ratings:
                rater = rating['rater_name'] or f"ID:{rating['rated_by_admin_id']}"
                previous = rating['previous_name'] or f"ID:{rating['previous_admin_id']}" if rating['previous_admin_id'] else "Н/Д"
                bar_emoji = "✅" if rating['bar_cleaned'] else "❌"
                hall_emoji = "✅" if rating['hall_cleaned'] else "❌"
                date = datetime.fromisoformat(rating['rated_at']).astimezone(MSK).strftime('%d.%m %H:%M')

                text += f"\n{date} - {rating['club'].upper()}\n"
                text += f"  Оценщик: {rater}\n"
                text += f"  Предыдущий: {previous}\n"
                text += f"  Бар: {bar_emoji} | Зал: {hall_emoji}\n"
        else:
            text += "<i>Нет оценок</i>\n"

    except Exception as e:
        logger.error(f"Error in show_owner_cleaning_ratings: {e}")
        text = f"⭐️ <b>Рейтинги уборки</b>\n\n❌ Ошибка: {e}"

    keyboard = [
        [InlineKeyboardButton("◀️ Назад", callback_data="owner_panel")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='HTML')


async def show_owner_inventory(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать статистику инвентаря"""
    query = update.callback_query
    await query.answer()

    db_path = context.bot_data.get('db_path', '/opt/club_assistant/club_assistant.db')

    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Последний инвентарь по каждому клубу
        cursor.execute("""
            SELECT
                sic.*,
                a.full_name as admin_name
            FROM shift_inventory_checklist sic
            LEFT JOIN admins a ON sic.admin_id = a.user_id
            WHERE sic.id IN (
                SELECT MAX(id)
                FROM shift_inventory_checklist
                GROUP BY club
            )
            ORDER BY sic.club
        """)

        latest_inventory = cursor.fetchall()

        conn.close()

        text = "📦 <b>Статистика инвентаря</b>\n\n"

        if latest_inventory:
            for inv in latest_inventory:
                club = inv['club'].upper()
                admin = inv['admin_name'] or f"ID:{inv['admin_id']}"
                date = datetime.fromisoformat(inv['completed_at']).astimezone(MSK).strftime('%d.%m.%Y %H:%M')

                text += f"🏢 <b>{club}</b> (обновлено: {date})\n"
                text += f"👤 Админ: {admin}\n\n"

                text += "🖱 <b>Мыши:</b>\n"
                text += f"  • На столах: {inv['mice_on_tables']}\n"
                text += f"  • В запасе: {inv['mice_in_stock']}\n"
                text += f"  • Донглы: {inv['mice_dongles_in_stock']}\n\n"

                text += "⌨️ <b>Клавиатуры:</b>\n"
                text += f"  • На столах: {inv['keyboards_on_tables']}\n"
                text += f"  • В запасе: {inv['keyboards_in_stock']}\n\n"

                text += "🎧 <b>Наушники:</b>\n"
                text += f"  • На столах: {inv['headsets_on_tables']}\n"
                text += f"  • В запасе: {inv['headsets_in_stock']}\n"
                text += f"  • Микрофоны: {inv['headset_mics_in_stock']}\n"
                text += f"  • Кабели: {inv['headset_cables_in_stock']}\n"

                if inv['club'].lower() == 'rio' and inv['chargers_in_stock'] is not None:
                    text += f"\n🔌 <b>Зарядки:</b> {inv['chargers_in_stock']}\n"

                text += "\n" + "="*30 + "\n\n"
        else:
            text += "<i>Нет данных об инвентаре</i>\n"

    except Exception as e:
        logger.error(f"Error in show_owner_inventory: {e}")
        text = f"📦 <b>Статистика инвентаря</b>\n\n❌ Ошибка: {e}"

    keyboard = [
        [InlineKeyboardButton("◀️ Назад", callback_data="owner_panel")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='HTML')


async def handle_owner_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик callback для панели владельца"""
    query = update.callback_query
    data = query.data

    if data == "owner_panel":
        await show_owner_panel(update, context)
    elif data == "owner_finance":
        await show_owner_finance(update, context)
    elif data == "owner_cleaning_ratings":
        await show_owner_cleaning_ratings(update, context)
    elif data == "owner_inventory":
        await show_owner_inventory(update, context)
