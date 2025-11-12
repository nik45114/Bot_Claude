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
        [InlineKeyboardButton("📅 График дежурств", callback_data="ctrl_schedule")],
        [InlineKeyboardButton("📂 Архив отчётов", callback_data="ctrl_archive")],
        [
            InlineKeyboardButton("🧹 Отзывы уборщицы", callback_data="reviews_all"),
            InlineKeyboardButton("⭐️ Рейтинги уборки", callback_data="ctrl_cleaning_ratings")
        ],
        [InlineKeyboardButton("👁 Чек-лист Глаза", callback_data="ctrl_club_check")],
        [InlineKeyboardButton("🔧 Статистика обслуживания", callback_data="ctrl_maint_stats")],
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
    """Показать выбор клуба для чек-листа глаза"""
    query = update.callback_query
    await query.answer()

    text = "👁 <b>Чек-лист Глаза</b>\n\n"
    text += "Выберите клуб для проверки:"

    keyboard = [
        [InlineKeyboardButton("🏔 Север", callback_data="ctrl_check_Север")],
        [InlineKeyboardButton("🌊 Рио", callback_data="ctrl_check_Рио")],
        [InlineKeyboardButton("◀️ Назад", callback_data="controller_panel")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='HTML')


async def show_club_check(update: Update, context: ContextTypes.DEFAULT_TYPE, club: str):
    """Показать проверку клуба (чек-лист дежурного глаза для выбранного клуба)"""
    query = update.callback_query
    await query.answer()

    knowledge_db_path = '/opt/club_assistant/knowledge.db'

    try:
        from modules.duty_shift_manager import DutyShiftManager
        # Используем knowledge.db для duty shifts
        duty_manager = DutyShiftManager(knowledge_db_path)

        conn = sqlite3.connect(knowledge_db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        today = datetime.now(MSK).date()
        duty_person = duty_manager.get_current_duty_person(today)

        # Автоматически создаём смену если её нет (или получаем существующую)
        shift_id = duty_manager.get_or_create_shift(
            shift_date=today,
            user_id=query.from_user.id,
            username=query.from_user.username or query.from_user.full_name
        )

        cursor.execute("""
            SELECT id, user_id, username, shift_date, started_at, ended_at
            FROM duty_shifts
            WHERE id = ?
        """, (shift_id,))
        duty_shift = cursor.fetchone()

        text = f"👁 <b>Чек-лист Глаза - {club}</b>\n\n"
        text += f"👤 Дежурный: {duty_person}\n"
        text += f"📅 Дата: {today.strftime('%d.%m.%Y')}\n\n"

        keyboard = []

        # Получаем все пункты чек-листа для клуба
        cursor.execute("""
            SELECT dci.id, dci.item_text, dci.category, dcp.checked, dcp.notes
            FROM duty_checklist_items dci
            LEFT JOIN duty_checklist_progress dcp
                ON dci.id = dcp.item_id
                AND dcp.shift_id = ?
                AND dcp.club = ?
            WHERE dci.is_active = 1
              AND (dci.club IS NULL OR dci.club = ?)
            ORDER BY dci.category, dci.sort_order
        """, (duty_shift['id'], club, club))
        all_items = cursor.fetchall()

        if all_items:
            categories = {}
            for item in all_items:
                cat = item['category'] or 'Общее'
                if cat not in categories:
                    categories[cat] = []
                categories[cat].append(item)

            for category, items in categories.items():
                text += f"<b>{category}:</b>\n"
                for item in items:
                    status = "✅" if item['checked'] else "⚪"
                    text += f"  {status} {item['item_text']}"
                    if item['notes']:
                        text += f" - <i>{item['notes']}</i>"
                    text += "\n"

                    # Добавляем кнопку для каждого пункта
                    button_text = f"{'✅' if item['checked'] else '⚪'} {item['item_text'][:30]}"
                    keyboard.append([InlineKeyboardButton(
                        button_text,
                        callback_data=f"ctrl_toggle_{duty_shift['id']}_{item['id']}_{club}"
                    )])
                text += "\n"

            total = len(all_items)
            checked = sum(1 for item in all_items if item['checked'])
            percent = int((checked / total) * 100) if total > 0 else 0
            text += f"<b>Прогресс:</b> {checked}/{total} ({percent}%)\n"
        else:
            text += "<i>⚠️ Нет пунктов чек-листа для этого клуба</i>\n"

        conn.close()

        keyboard.append([InlineKeyboardButton("🔄 Обновить", callback_data=f"ctrl_check_{club}")])
        keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data="ctrl_club_check")])
        reply_markup = InlineKeyboardMarkup(keyboard)

        try:
            await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='HTML')
        except Exception as edit_error:
            # Если сообщение не изменилось - просто игнорируем ошибку
            if "message is not modified" not in str(edit_error).lower():
                raise

    except Exception as e:
        logger.error(f"Error in show_club_check: {e}")
        try:
            await query.edit_message_text(f"❌ Ошибка: {e}", parse_mode='HTML')
        except:
            await query.message.reply_text(f"❌ Ошибка: {e}", parse_mode='HTML')


async def toggle_club_check_item(update: Update, context: ContextTypes.DEFAULT_TYPE, shift_id: int, item_id: int, club: str):
    """Переключить статус пункта чек-листа глаза"""
    query = update.callback_query
    await query.answer()

    knowledge_db_path = '/opt/club_assistant/knowledge.db'

    try:
        conn = sqlite3.connect(knowledge_db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Проверяем текущий статус для конкретного клуба
        cursor.execute("""
            SELECT checked FROM duty_checklist_progress
            WHERE shift_id = ? AND item_id = ? AND club = ?
        """, (shift_id, item_id, club))
        result = cursor.fetchone()

        if result:
            # Переключаем статус
            new_status = 0 if result['checked'] else 1
            cursor.execute("""
                UPDATE duty_checklist_progress
                SET checked = ?
                WHERE shift_id = ? AND item_id = ? AND club = ?
            """, (new_status, shift_id, item_id, club))
        else:
            # Создаём новую запись с checked=1
            cursor.execute("""
                INSERT INTO duty_checklist_progress (shift_id, item_id, club, checked)
                VALUES (?, ?, ?, 1)
            """, (shift_id, item_id, club))

        conn.commit()
        conn.close()

        # Обновляем отображение чек-листа
        await show_club_check(update, context, club)

    except Exception as e:
        logger.error(f"Error in toggle_club_check_item: {e}")
        await query.answer(f"❌ Ошибка: {e}", show_alert=True)


async def show_controller_maint_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать статистику обслуживания для контролёра"""
    query = update.callback_query
    await query.answer()

    knowledge_db = '/opt/club_assistant/knowledge.db'

    try:
        conn = sqlite3.connect(knowledge_db)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Получаем статистику по каждому админу (только активные типы задач)
        cursor.execute("""
            SELECT
                mt.admin_id,
                a.full_name,
                COUNT(*) as total_tasks,
                SUM(CASE WHEN mt.status = 'completed' THEN 1 ELSE 0 END) as completed,
                SUM(CASE WHEN mt.status = 'pending' THEN 1 ELSE 0 END) as pending,
                SUM(CASE WHEN mt.status = 'overdue' THEN 1 ELSE 0 END) as overdue
            FROM maintenance_tasks mt
            LEFT JOIN admins a ON mt.admin_id = a.user_id
            LEFT JOIN maintenance_task_types mtt ON mt.task_type_id = mtt.id
            WHERE mt.assigned_date >= date('now', '-30 days')
              AND (mtt.is_active = 1 OR mtt.is_active IS NULL)
            GROUP BY mt.admin_id, a.full_name
            ORDER BY completed DESC, total_tasks DESC
        """)
        admin_stats = cursor.fetchall()

        # Общая статистика (только активные типы задач)
        cursor.execute("""
            SELECT
                COUNT(*) as total_tasks,
                SUM(CASE WHEN mt.status = 'completed' THEN 1 ELSE 0 END) as completed,
                SUM(CASE WHEN mt.status = 'pending' THEN 1 ELSE 0 END) as pending,
                SUM(CASE WHEN mt.status = 'overdue' THEN 1 ELSE 0 END) as overdue
            FROM maintenance_tasks mt
            LEFT JOIN maintenance_task_types mtt ON mt.task_type_id = mtt.id
            WHERE mt.assigned_date >= date('now', '-30 days')
              AND (mtt.is_active = 1 OR mtt.is_active IS NULL)
        """)
        total_stats = cursor.fetchone()

        conn.close()

        text = "🔧 <b>Статистика обслуживания оборудования</b>\n"
        text += "<i>За последние 30 дней</i>\n\n"

        # Общая статистика
        if total_stats and total_stats['total_tasks'] > 0:
            total = total_stats['total_tasks']
            completed = total_stats['completed'] or 0
            pending = total_stats['pending'] or 0
            overdue = total_stats['overdue'] or 0
            percent = int((completed / total) * 100) if total > 0 else 0

            # Визуальный прогресс-бар
            progress_bar = "🟢" * (percent // 10) + "⚪" * (10 - percent // 10)

            text += f"<b>📈 Общее выполнение:</b>\n"
            text += f"{progress_bar}\n"
            text += f"✅ Выполнено: {completed}/{total} ({percent}%)\n"
            text += f"📋 В работе: {pending}\n"
            if overdue > 0:
                text += f"⚠️ Просрочено: {overdue}\n"
            text += "\n"

        # Статистика по админам
        if admin_stats:
            text += "<b>👥 По администраторам:</b>\n\n"
            for stat in admin_stats:
                admin_name = stat['full_name'] or f"ID:{stat['admin_id']}"
                total = stat['total_tasks']
                completed = stat['completed'] or 0
                pending = stat['pending'] or 0
                overdue = stat['overdue'] or 0
                percent = int((completed / total) * 100) if total > 0 else 0

                # Индикатор прогресса
                if percent >= 80:
                    emoji = "🟢"
                elif percent >= 50:
                    emoji = "🟡"
                elif percent >= 20:
                    emoji = "🟠"
                else:
                    emoji = "🔴"

                text += f"{emoji} <b>{admin_name}</b>: {completed}/{total} ({percent}%)\n"
                if overdue > 0:
                    text += f"   ⚠️ Просрочено: {overdue}\n"
        else:
            text += "<i>Нет данных за последние 30 дней</i>\n"

        keyboard = []

        # Кнопки для выбора конкретного админа (без ограничения)
        if admin_stats:
            for stat in admin_stats:
                admin_name = stat['full_name'] or f"ID:{stat['admin_id']}"
                total = stat['total_tasks']
                completed = stat['completed'] or 0
                percent = int((completed / total) * 100) if total > 0 else 0

                # Короткое имя для кнопки
                if len(admin_name) > 20:
                    short_name = admin_name[:18] + "..."
                else:
                    short_name = admin_name

                keyboard.append([InlineKeyboardButton(
                    f"👤 {short_name} ({percent}%)",
                    callback_data=f"ctrl_maint_admin_{stat['admin_id']}"
                )])

        keyboard.append([InlineKeyboardButton("📸 Фото оборудования", callback_data="ctrl_equipment_browser")])
        keyboard.append([InlineKeyboardButton("🔄 Обновить", callback_data="ctrl_maint_stats")])
        keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data="controller_panel")])
        reply_markup = InlineKeyboardMarkup(keyboard)

        try:
            await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='HTML')
        except Exception as edit_error:
            # Если сообщение не изменилось - игнорируем ошибку
            if "message is not modified" not in str(edit_error).lower():
                raise

    except Exception as e:
        logger.error(f"Error in show_controller_maint_stats: {e}")
        try:
            await query.edit_message_text(f"❌ Ошибка загрузки статистики: {e}", parse_mode='HTML')
        except:
            await query.answer(f"❌ Ошибка: {e}", show_alert=True)


async def show_admin_maint_details(update: Update, context: ContextTypes.DEFAULT_TYPE, admin_id: int):
    """Показать детальную статистику по задачам конкретного админа"""
    query = update.callback_query
    await query.answer()

    knowledge_db = '/opt/club_assistant/knowledge.db'

    try:
        conn = sqlite3.connect(knowledge_db)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Получаем информацию об админе
        cursor.execute("SELECT full_name FROM admins WHERE user_id = ?", (admin_id,))
        admin_info = cursor.fetchone()
        admin_name = admin_info['full_name'] if admin_info else f"ID:{admin_id}"

        # Получаем задачи админа с количеством фото
        cursor.execute("""
            SELECT
                mt.id,
                mt.status,
                mt.assigned_date,
                mt.due_date,
                mt.completed_date,
                mt.club,
                mtt.task_name,
                ei.inventory_number,
                ei.pc_number,
                (SELECT COUNT(*) FROM maintenance_photos mp WHERE mp.task_id = mt.id) as photo_count
            FROM maintenance_tasks mt
            LEFT JOIN maintenance_task_types mtt ON mt.task_type_id = mtt.id
            LEFT JOIN equipment_inventory ei ON mt.equipment_id = ei.id
            WHERE mt.admin_id = ?
              AND mt.assigned_date >= date('now', '-30 days')
            ORDER BY
                CASE mt.status
                    WHEN 'overdue' THEN 1
                    WHEN 'pending' THEN 2
                    WHEN 'completed' THEN 3
                END,
                mt.due_date ASC
        """, (admin_id,))
        tasks = cursor.fetchall()

        # Статистика
        total = len(tasks)
        completed = sum(1 for t in tasks if t['status'] == 'completed')
        pending = sum(1 for t in tasks if t['status'] == 'pending')
        overdue = sum(1 for t in tasks if t['status'] == 'overdue')
        percent = int((completed / total) * 100) if total > 0 else 0

        conn.close()

        text = f"🔧 <b>Задачи обслуживания</b>\n"
        text += f"👤 <b>{admin_name}</b>\n\n"

        # Общая статистика
        progress_bar = "🟢" * (percent // 10) + "⚪" * (10 - percent // 10)
        text += f"<b>Прогресс:</b>\n{progress_bar}\n"
        text += f"✅ Выполнено: {completed}/{total} ({percent}%)\n"
        text += f"📋 В работе: {pending}\n"
        if overdue > 0:
            text += f"⚠️ Просрочено: {overdue}\n"
        text += "\n"

        # Просроченные задачи
        if overdue > 0:
            text += "<b>⚠️ Просроченные задачи:</b>\n"
            overdue_tasks = [t for t in tasks if t['status'] == 'overdue']
            for task in overdue_tasks[:5]:
                club_emoji = "🏔" if task['club'] == 'Север' else "🌊"
                text += f"{club_emoji} {task['task_name']}\n"
                text += f"   {task['inventory_number']} (ПК №{task['pc_number']})\n"
                text += f"   Срок: {task['due_date']}\n"
            text += "\n"

        # Активные задачи
        if pending > 0:
            text += "<b>📋 Активные задачи:</b>\n"
            pending_tasks = [t for t in tasks if t['status'] == 'pending']
            for task in pending_tasks[:5]:
                club_emoji = "🏔" if task['club'] == 'Север' else "🌊"
                text += f"{club_emoji} {task['task_name']}\n"
                text += f"   {task['inventory_number']} (ПК №{task['pc_number']})\n"
                text += f"   До: {task['due_date']}\n"
            if len(pending_tasks) > 5:
                text += f"   <i>...и ещё {len(pending_tasks) - 5}</i>\n"
            text += "\n"

        # Последние выполненные
        if completed > 0:
            text += "<b>✅ Последние выполненные:</b>\n"
            completed_tasks = [t for t in tasks if t['status'] == 'completed']
            for task in completed_tasks[:3]:
                club_emoji = "🏔" if task['club'] == 'Север' else "🌊"
                photo_emoji = f" 📸{task['photo_count']}" if task['photo_count'] > 0 else ""
                text += f"{club_emoji} {task['task_name']}{photo_emoji}\n"
                text += f"   {task['inventory_number']} (ПК №{task['pc_number']})\n"
                if task['completed_date']:
                    from datetime import datetime
                    completed_date = datetime.fromisoformat(task['completed_date'].replace('+03:00', '')).strftime('%d.%m')
                    text += f"   Выполнено: {completed_date}\n"
            if len(completed_tasks) > 3:
                text += f"   <i>...и ещё {len(completed_tasks) - 3}</i>\n"

        # Подсчитать общее количество фото админа
        conn2 = sqlite3.connect(knowledge_db)
        cursor2 = conn2.cursor()
        cursor2.execute("""
            SELECT COUNT(*) FROM maintenance_photos
            WHERE admin_id = ?
            AND uploaded_at >= date('now', '-30 days')
        """, (admin_id,))
        total_photos = cursor2.fetchone()[0]
        conn2.close()

        keyboard = []
        if total_photos > 0:
            keyboard.append([InlineKeyboardButton(f"📸 Все фото ({total_photos})", callback_data=f"ctrl_photos_{admin_id}")])
        keyboard.append([InlineKeyboardButton("🔄 Обновить", callback_data=f"ctrl_maint_admin_{admin_id}")])
        keyboard.append([InlineKeyboardButton("◀️ К общей статистике", callback_data="ctrl_maint_stats")])
        reply_markup = InlineKeyboardMarkup(keyboard)

        try:
            await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='HTML')
        except Exception as edit_error:
            if "message is not modified" not in str(edit_error).lower():
                raise

    except Exception as e:
        logger.error(f"Error in show_admin_maint_details: {e}")
        await query.answer(f"❌ Ошибка: {e}", show_alert=True)


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
            photo_captions.append("💵 Сверка итогов (касса 1)")

        if shift['z_report_card_photo']:
            photos_to_send.append(shift['z_report_card_photo'])
            photo_captions.append("💳 Итоговый отчет (касса 1)")

        if shift['z_report_qr_photo']:
            photos_to_send.append(shift['z_report_qr_photo'])
            photo_captions.append("📱 Итоговый отчет QR (касса 1)")

        if shift['z_report_card2_photo']:
            photos_to_send.append(shift['z_report_card2_photo'])
            photo_captions.append("💳 X-отчет (касса 2)")

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


async def show_cleaning_ratings_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать статистику рейтингов уборки для контролёра"""
    query = update.callback_query
    await query.answer()

    db_path = context.bot_data.get('db_path', '/opt/club_assistant/club_assistant.db')

    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Последние 15 оценок
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
            LIMIT 15
        """)

        recent_ratings = cursor.fetchall()

        conn.close()

        text = "⭐️ <b>Рейтинги уборки админов</b>\n\n"
        text += "📋 <b>Последние 15 оценок:</b>\n"

        if recent_ratings:
            for rating in recent_ratings:
                rater = rating['rater_name'] or f"ID:{rating['rated_by_admin_id']}"
                previous = rating['previous_name'] or f"ID:{rating['previous_admin_id']}" if rating['previous_admin_id'] else "Н/Д"
                bar_emoji = "✅" if rating['bar_cleaned'] else "❌"
                hall_emoji = "✅" if rating['hall_cleaned'] else "❌"
                date = datetime.fromisoformat(rating['rated_at']).astimezone(MSK).strftime('%d.%m %H:%M')

                text += f"\n{date} - {rating['club'].upper()}\n"
                text += f"  Оценил: {rater}\n"
                text += f"  Предыдущий: {previous}\n"
                text += f"  Бар: {bar_emoji} | Зал: {hall_emoji}\n"

                if rating['notes']:
                    text += f"  📝 {rating['notes'][:50]}...\n" if len(rating['notes']) > 50 else f"  📝 {rating['notes']}\n"
        else:
            text += "<i>Нет оценок</i>\n"

    except Exception as e:
        logger.error(f"Error in show_cleaning_ratings_stats: {e}")
        text = f"⭐️ <b>Рейтинги уборки</b>\n\n❌ Ошибка: {e}"

    keyboard = [
        [InlineKeyboardButton("◀️ Назад", callback_data="controller_panel")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='HTML')


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

    # Чек-лист Глаза
    if data == "ctrl_club_check":
        await show_club_check_select(update, context)
        return

    if data.startswith("ctrl_toggle_"):
        # Формат: ctrl_toggle_{shift_id}_{item_id}_{club}
        parts = data.replace("ctrl_toggle_", "").split("_")
        shift_id = int(parts[0])
        item_id = int(parts[1])
        club = "_".join(parts[2:])  # На случай если в названии клуба есть _
        await toggle_club_check_item(update, context, shift_id, item_id, club)
        return

    if data.startswith("ctrl_check_"):
        club = data.replace("ctrl_check_", "")
        await show_club_check(update, context, club)
        return

    # Рейтинги уборки
    if data == "ctrl_cleaning_ratings":
        await show_cleaning_ratings_stats(update, context)
        return

    # Статистика обслуживания
    if data == "ctrl_maint_stats":
        await show_controller_maint_stats(update, context)
        return

    if data.startswith("ctrl_maint_admin_"):
        admin_id = int(data.replace("ctrl_maint_admin_", ""))
        await show_admin_maint_details(update, context, admin_id)
        return

    # Фото оборудования и админов
    if data == "ctrl_equipment_browser":
        from modules.maintenance_commands import show_equipment_browser
        await show_equipment_browser(update, context)
        return

    if data.startswith("ctrl_photos_"):
        admin_id = int(data.replace("ctrl_photos_", ""))
        from modules.maintenance_commands import show_admin_photos
        await show_admin_photos(update, context, admin_id, page=0)
        return

    if data.startswith("ctrl_photo_"):
        # Формат: ctrl_photo_{admin_id}_{page}
        parts = data.replace("ctrl_photo_", "").split("_")
        admin_id = int(parts[0])
        page = int(parts[1])
        from modules.maintenance_commands import show_admin_photos
        await show_admin_photos(update, context, admin_id, page)
        return

    if data.startswith("ctrl_eq_"):
        # Формат: ctrl_eq_{equipment_id}_{page}
        parts = data.replace("ctrl_eq_", "").split("_")
        equipment_id = int(parts[0])
        page = int(parts[1])
        from modules.maintenance_commands import show_equipment_photos
        await show_equipment_photos(update, context, equipment_id, page)
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
        pattern="^(controller_panel|ctrl_current_checklists|ctrl_club_checklist_|ctrl_club_check|ctrl_check_|ctrl_toggle_|ctrl_cleaning_ratings|ctrl_maint_stats|ctrl_maint_admin_|ctrl_equipment_browser|ctrl_photos_|ctrl_photo_|ctrl_eq_|ctrl_archive|ctrl_year_|ctrl_month_|ctrl_day_|ctrl_shift_)"
    )
