"""
Команды для управления задачами обслуживания оборудования
"""

import logging
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CallbackQueryHandler, MessageHandler, ConversationHandler, filters
from modules.maintenance_manager import MaintenanceManager

logger = logging.getLogger(__name__)

# Состояния для ConversationHandler
MAINT_UPLOAD_PHOTO, MAINT_ENTER_NOTES = range(2)


def format_date_ru(date_str):
    """Форматировать дату в русский формат ДД.ММ.ГГГГ"""
    if not date_str:
        return '—'
    try:
        # Парсим дату из формата YYYY-MM-DD
        dt = datetime.strptime(str(date_str), '%Y-%m-%d')
        # Возвращаем в формате ДД.ММ.ГГГГ
        return dt.strftime('%d.%m.%Y')
    except:
        return str(date_str)


async def show_maintenance_tasks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать задачи обслуживания админа"""
    query = update.callback_query
    if query:
        await query.answer()

    user_id = update.effective_user.id
    db_path = context.bot_data.get('db_path')
    owner_id = context.bot_data.get('owner_id')
    schedule_parser = context.bot_data.get('schedule_parser')

    manager = MaintenanceManager(db_path, schedule_parser)

    # Получить задачи админа
    pending_tasks = manager.get_admin_tasks(user_id, status='pending')
    overdue_tasks = manager.get_admin_tasks(user_id, status='overdue')
    completed_tasks = manager.get_admin_tasks(user_id, status='completed')

    text = "🔧 *Задачи обслуживания оборудования*\n\n"

    # Группируем задачи по клубу и типу для компактного вывода
    def group_tasks_by_type(tasks):
        from collections import defaultdict
        grouped = defaultdict(lambda: defaultdict(list))
        for task in tasks:
            club = task['club']
            eq_type = task['equipment_type']
            grouped[club][eq_type].append(task['pc_number'])
        return grouped

    if overdue_tasks:
        text += f"⚠️ *Просрочено ({len(overdue_tasks)}):*\n"
        grouped = group_tasks_by_type(overdue_tasks)
        for club in ['rio', 'sever']:
            if club not in grouped:
                continue
            club_emoji = '🏪' if club == 'rio' else '🏢'
            text += f"{club_emoji} *{club.upper()}:*\n"
            for eq_type, pc_nums in grouped[club].items():
                type_emoji = {'pc': '💻', 'keyboard': '⌨️', 'mouse': '🖱'}.get(eq_type, '📦')
                type_name = {'pc': 'ПК', 'keyboard': 'Клавиатуры', 'mouse': 'Мыши'}.get(eq_type, eq_type)
                pc_nums_str = ', '.join(map(str, sorted(pc_nums)))
                text += f"   {type_emoji} {type_name}: №{pc_nums_str}\n"
        # Показываем срок
        if overdue_tasks:
            text += f"   ⏰ Срок истёк: {format_date_ru(overdue_tasks[0]['due_date'])}\n"
        text += "\n"

    if pending_tasks:
        text += f"📋 *Активные ({len(pending_tasks)}):*\n"
        grouped = group_tasks_by_type(pending_tasks)
        for club in ['rio', 'sever']:
            if club not in grouped:
                continue
            club_emoji = '🏪' if club == 'rio' else '🏢'
            text += f"{club_emoji} *{club.upper()}:*\n"
            for eq_type, pc_nums in grouped[club].items():
                type_emoji = {'pc': '💻', 'keyboard': '⌨️', 'mouse': '🖱'}.get(eq_type, '📦')
                type_name = {'pc': 'ПК', 'keyboard': 'Клавиатуры', 'mouse': 'Мыши'}.get(eq_type, eq_type)
                pc_nums_str = ', '.join(map(str, sorted(pc_nums)))
                text += f"   {type_emoji} {type_name}: №{pc_nums_str}\n"
        # Показываем срок
        if pending_tasks:
            text += f"   ⏰ До: {format_date_ru(pending_tasks[0]['due_date'])}\n"
        text += "\n"

    if completed_tasks:
        text += f"✅ Выполнено: {len(completed_tasks)}\n\n"

    if not pending_tasks and not overdue_tasks:
        text += "У вас нет активных задач обслуживания\n"

    keyboard = []

    if pending_tasks or overdue_tasks:
        keyboard.append([InlineKeyboardButton("✅ Отметить выполнение", callback_data="maint_complete")])

    # Кнопки только для владельца
    if user_id == owner_id:
        keyboard.append([InlineKeyboardButton("📊 Статистика выполнения", callback_data="maint_stats")])
        keyboard.append([InlineKeyboardButton("⚙️ Управление задачами", callback_data="maint_manage")])

    keyboard.append([InlineKeyboardButton("« Главное меню", callback_data="main_menu")])

    reply_markup = InlineKeyboardMarkup(keyboard)

    if query:
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
    else:
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='Markdown')


async def show_maintenance_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать статистику выполнения задач обслуживания"""
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id
    db_path = context.bot_data.get('db_path')

    import sqlite3
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

        text = "📊 <b>Статистика обслуживания (30 дней)</b>\n\n"

        # Общая статистика
        if total_stats and total_stats['total_tasks'] > 0:
            total = total_stats['total_tasks']
            completed = total_stats['completed'] or 0
            pending = total_stats['pending'] or 0
            overdue = total_stats['overdue'] or 0
            percent = int((completed / total) * 100) if total > 0 else 0

            # Визуальный прогресс-бар
            filled = int(percent / 10)
            progress_bar = "🟢" * filled + "⚪" * (10 - filled)

            text += f"<b>📈 Общее:</b> {completed}/{total} ({percent}%)\n"
            text += f"{progress_bar}\n"
            if pending > 0:
                text += f"📋 В работе: {pending}\n"
            if overdue > 0:
                text += f"⚠️ Просрочено: {overdue}\n"
            text += "\n"

        # Краткая статистика по админам
        if admin_stats:
            text += "<b>👥 Администраторы:</b>\n"
            for stat in admin_stats:
                admin_name = stat['full_name'] or f"ID:{stat['admin_id']}"
                total = stat['total_tasks']
                completed = stat['completed'] or 0
                overdue = stat['overdue'] or 0
                percent = int((completed / total) * 100) if total > 0 else 0

                # Индикатор прогресса
                if percent >= 80:
                    emoji = "🟢"
                elif percent >= 50:
                    emoji = "🟡"
                else:
                    emoji = "🔴"

                overdue_text = f" ⚠️{overdue}" if overdue > 0 else ""
                text += f"{emoji} {admin_name}: {completed}/{total} ({percent}%){overdue_text}\n"

            text += "\n<i>Нажмите на админа для деталей</i>"
        else:
            text += "<i>Нет данных за последние 30 дней</i>\n"

        keyboard = []

        # Добавляем кнопки для ВСЕХ админов (без ограничения)
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
                    callback_data=f"maint_admin_{stat['admin_id']}"
                )])

        keyboard.append([InlineKeyboardButton("📸 Фото оборудования", callback_data="maint_equipment_browser")])
        keyboard.append([InlineKeyboardButton("🔄 Обновить", callback_data="maint_stats")])
        keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data="maintenance_tasks")])

        reply_markup = InlineKeyboardMarkup(keyboard)

        try:
            await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='HTML')
        except Exception as edit_error:
            # Если сообщение не изменилось - игнорируем ошибку
            if "message is not modified" not in str(edit_error).lower():
                raise

    except Exception as e:
        logger.error(f"Error in show_maintenance_stats: {e}")
        try:
            await query.edit_message_text(f"❌ Ошибка загрузки статистики: {e}", parse_mode='HTML')
        except:
            await query.answer(f"❌ Ошибка: {e}", show_alert=True)


async def show_owner_admin_maint_details(update: Update, context: ContextTypes.DEFAULT_TYPE, admin_id: int):
    """Показать детальную статистику по задачам конкретного админа для владельца"""
    query = update.callback_query
    await query.answer()

    import sqlite3
    knowledge_db = '/opt/club_assistant/knowledge.db'

    try:
        conn = sqlite3.connect(knowledge_db)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Получаем информацию об админе
        cursor.execute("SELECT full_name FROM admins WHERE user_id = ?", (admin_id,))
        admin = cursor.fetchone()
        admin_name = admin['full_name'] if admin else f"ID:{admin_id}"

        # Получаем задачи админа (только активные типы) с количеством фото
        cursor.execute("""
            SELECT
                mt.id,
                mtt.task_name,
                mt.club,
                ei.inventory_number,
                ei.pc_number,
                mt.status,
                mt.assigned_date,
                mt.due_date,
                mt.completed_date,
                (SELECT COUNT(*) FROM maintenance_photos mp WHERE mp.task_id = mt.id) as photo_count
            FROM maintenance_tasks mt
            LEFT JOIN maintenance_task_types mtt ON mt.task_type_id = mtt.id
            LEFT JOIN equipment_inventory ei ON mt.equipment_id = ei.id
            WHERE mt.admin_id = ?
            AND mt.assigned_date >= date('now', '-30 days')
            AND (mtt.is_active = 1 OR mtt.is_active IS NULL)
            ORDER BY
                CASE mt.status
                    WHEN 'overdue' THEN 1
                    WHEN 'pending' THEN 2
                    WHEN 'completed' THEN 3
                END,
                mt.due_date ASC,
                mt.completed_date DESC
        """, (admin_id,))
        tasks = cursor.fetchall()

        conn.close()

        # Статистика
        total = len(tasks)
        completed = sum(1 for t in tasks if t['status'] == 'completed')
        pending = sum(1 for t in tasks if t['status'] == 'pending')
        overdue = sum(1 for t in tasks if t['status'] == 'overdue')
        percent = int((completed / total) * 100) if total > 0 else 0

        # Визуальный прогресс-бар
        filled = int(percent / 10)
        progress_bar = "🟢" * filled + "⚪" * (10 - filled)

        text = f"👤 <b>{admin_name}</b>\n\n"
        text += f"<b>Статистика:</b>\n"
        text += f"{progress_bar}\n"
        text += f"✅ Выполнено: {completed}/{total} ({percent}%)\n"
        if pending > 0:
            text += f"📋 В работе: {pending}\n"
        if overdue > 0:
            text += f"⚠️ Просрочено: {overdue}\n"
        text += "\n"

        # Группируем задачи
        overdue_tasks = [t for t in tasks if t['status'] == 'overdue']
        pending_tasks = [t for t in tasks if t['status'] == 'pending']
        completed_tasks = [t for t in tasks if t['status'] == 'completed']

        # Просроченные задачи
        if overdue_tasks:
            text += "<b>⚠️ Просроченные:</b>\n"
            for task in overdue_tasks[:3]:
                club_emoji = '🏪' if task['club'] == 'rio' else '🏢'
                inv = task['inventory_number'] or task['pc_number'] or '—'
                text += f"{club_emoji} {task['task_name']}\n"
                text += f"   📦 {inv} | ⏰ до {format_date_ru(task['due_date'])}\n"
            if len(overdue_tasks) > 3:
                text += f"   <i>...и ещё {len(overdue_tasks) - 3}</i>\n"
            text += "\n"

        # Текущие задачи
        if pending_tasks:
            text += "<b>📋 В работе:</b>\n"
            for task in pending_tasks[:3]:
                club_emoji = '🏪' if task['club'] == 'rio' else '🏢'
                inv = task['inventory_number'] or task['pc_number'] or '—'
                text += f"{club_emoji} {task['task_name']}\n"
                text += f"   📦 {inv} | ⏰ до {format_date_ru(task['due_date'])}\n"
            if len(pending_tasks) > 3:
                text += f"   <i>...и ещё {len(pending_tasks) - 3}</i>\n"
            text += "\n"

        # Выполненные задачи (только последние 3)
        if completed_tasks:
            text += "<b>✅ Последние выполненные:</b>\n"
            for task in completed_tasks[:3]:
                club_emoji = '🏪' if task['club'] == 'rio' else '🏢'
                inv = task['inventory_number'] or task['pc_number'] or '—'
                photo_emoji = f" 📸{task['photo_count']}" if task['photo_count'] > 0 else ""
                text += f"{club_emoji} {task['task_name']}{photo_emoji}\n"
                text += f"   📦 {inv} | ✓ {format_date_ru(task['completed_date'])}\n"
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
            keyboard.append([InlineKeyboardButton(f"📸 Все фото ({total_photos})", callback_data=f"maint_photos_{admin_id}")])
        keyboard.append([InlineKeyboardButton("◀️ Назад к статистике", callback_data="maint_stats")])
        reply_markup = InlineKeyboardMarkup(keyboard)

        try:
            await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='HTML')
        except Exception as edit_error:
            if "message is not modified" not in str(edit_error).lower():
                raise

    except Exception as e:
        logger.error(f"Error in show_owner_admin_maint_details: {e}")
        try:
            await query.edit_message_text(f"❌ Ошибка загрузки деталей: {e}", parse_mode='HTML')
        except:
            await query.answer(f"❌ Ошибка: {e}", show_alert=True)


async def select_task_to_complete(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Выбрать задачу для отметки выполнения"""
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id
    db_path = context.bot_data.get('db_path')
    schedule_parser = context.bot_data.get('schedule_parser')

    manager = MaintenanceManager(db_path, schedule_parser)

    # Получить невыполненные задачи
    tasks = manager.get_admin_tasks(user_id, status='pending')
    tasks += manager.get_admin_tasks(user_id, status='overdue')

    if not tasks:
        await query.edit_message_text("У вас нет активных задач")
        return ConversationHandler.END

    text = "Выберите задачу для отметки выполнения:\n\n"

    keyboard = []
    for task in tasks[:10]:  # Показываем до 10 задач
        club_emoji = '🏪' if task['club'] == 'rio' else '🏢'
        btn_text = f"{club_emoji} {task['task_name']} - {task['inventory_number']}"
        keyboard.append([InlineKeyboardButton(btn_text, callback_data=f"maint_task_{task['id']}")])

    keyboard.append([InlineKeyboardButton("« Назад", callback_data="maintenance_tasks")])

    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')


async def start_task_completion(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начать процесс выполнения задачи"""
    query = update.callback_query
    await query.answer()

    # Извлекаем task_id из callback_data
    task_id = int(query.data.replace("maint_task_", ""))

    # Сохраняем в context
    context.user_data['completing_task_id'] = task_id

    db_path = context.bot_data.get('db_path')
    schedule_parser = context.bot_data.get('schedule_parser')
    manager = MaintenanceManager(db_path, schedule_parser)

    # Получить информацию о задаче
    user_id = update.effective_user.id
    all_tasks = manager.get_admin_tasks(user_id)
    task = next((t for t in all_tasks if t['id'] == task_id), None)

    if not task:
        await query.edit_message_text("❌ Задача не найдена")
        return ConversationHandler.END

    club_emoji = '🏪' if task['club'] == 'rio' else '🏢'

    text = f"📸 *Загрузите фото выполненной работы*\n\n"
    text += f"{club_emoji} {task['task_name']}\n"
    text += f"{task['inventory_number']} (ПК №{task['pc_number']})\n\n"
    text += "Отправьте фото или /cancel для отмены"

    await query.edit_message_text(text, parse_mode='Markdown')

    return MAINT_UPLOAD_PHOTO


async def receive_task_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получить фото выполненной задачи"""
    if not update.message.photo:
        await update.message.reply_text("Пожалуйста, отправьте фото")
        return MAINT_UPLOAD_PHOTO

    # Сохраняем file_id фото
    photo_file_id = update.message.photo[-1].file_id
    context.user_data['task_photo_id'] = photo_file_id

    text = "✅ Фото получено!\n\n"
    text += "Хотите добавить комментарий? (необязательно)\n"
    text += "Отправьте текст или /skip чтобы пропустить"

    await update.message.reply_text(text)

    return MAINT_ENTER_NOTES


async def receive_task_notes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получить комментарий к задаче"""
    notes = update.message.text if update.message.text != '/skip' else None

    task_id = context.user_data.get('completing_task_id')
    photo_id = context.user_data.get('task_photo_id')

    if not task_id:
        await update.message.reply_text("❌ Ошибка: задача не найдена")
        return ConversationHandler.END

    db_path = context.bot_data.get('db_path')
    schedule_parser = context.bot_data.get('schedule_parser')
    manager = MaintenanceManager(db_path, schedule_parser)

    # Отметить задачу как выполненную
    if manager.complete_task(task_id, photo_id, notes):
        await update.message.reply_text("✅ Задача отмечена как выполненная!")
    else:
        await update.message.reply_text("❌ Ошибка при сохранении")

    # Очистка context
    context.user_data.pop('completing_task_id', None)
    context.user_data.pop('task_photo_id', None)

    # Показать обновленный список задач
    await show_maintenance_tasks(update, context)

    return ConversationHandler.END


async def cancel_task_completion(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отменить выполнение задачи"""
    context.user_data.pop('completing_task_id', None)
    context.user_data.pop('task_photo_id', None)

    await update.message.reply_text("❌ Отменено")
    await show_maintenance_tasks(update, context)

    return ConversationHandler.END


async def show_maintenance_management(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать меню управления задачами обслуживания"""
    query = update.callback_query
    await query.answer()

    db_path = context.bot_data.get('db_path')
    schedule_parser = context.bot_data.get('schedule_parser')
    manager = MaintenanceManager(db_path, schedule_parser)

    # Получить статистику распределения смен
    shift_dist = manager._get_admin_shift_distribution()

    text = "⚙️ *Управление задачами обслуживания*\n\n"
    text += "📊 *Распределение смен за последние 60 дней:*\n\n"

    if shift_dist:
        # Получить имена админов
        import sqlite3
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        for admin_id, data in sorted(shift_dist.items()):
            # Получить ФИО админа
            cursor.execute("SELECT full_name FROM admins WHERE user_id = ?", (admin_id,))
            row = cursor.fetchone()
            admin_name = row[0] if row and row[0] else f"Админ {admin_id}"

            text += f"👤 *{admin_name}*:\n"
            text += f"   🏪 РИО: {data['rio']} смен\n"
            text += f"   🏢 СЕВЕР: {data['sever']} смен\n"
            text += f"   📊 Всего: {data['total']} смен\n\n"

        conn.close()
    else:
        text += "Нет данных о сменах\n\n"

    text += "Выберите тип оборудования для распределения задач:"

    keyboard = [
        [InlineKeyboardButton("💻 Продувка ПК", callback_data="maint_assign_pc")],
        [InlineKeyboardButton("⌨️ Чистка клавиатур", callback_data="maint_assign_keyboard")],
        [InlineKeyboardButton("🖱 Чистка мышей", callback_data="maint_assign_mouse")],
        [InlineKeyboardButton("✅ Распределить всё", callback_data="maint_assign_all")],
        [InlineKeyboardButton("🗑 Обнулить все задачи (DEBUG)", callback_data="maint_clear_all")],
        [InlineKeyboardButton("« Назад", callback_data="maintenance_tasks")]
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')


async def assign_maintenance_tasks(update: Update, context: ContextTypes.DEFAULT_TYPE, equipment_type: str = 'all'):
    """Распределить задачи обслуживания"""
    query = update.callback_query
    await query.answer()

    db_path = context.bot_data.get('db_path')
    schedule_parser = context.bot_data.get('schedule_parser')
    manager = MaintenanceManager(db_path, schedule_parser)

    # Названия типов для вывода
    type_names = {
        'all': 'все задачи',
        'pc': 'продувку ПК',
        'keyboard': 'чистку клавиатур',
        'mouse': 'чистку мышей'
    }
    type_name = type_names.get(equipment_type, 'задачи')

    await query.edit_message_text(f"⏳ Распределяю {type_name}...", parse_mode='Markdown')

    # Распределить задачи по выбранному типу
    manager.assign_tasks_proportionally(equipment_type)

    # Показать детальный результат
    text = "✅ *Задачи успешно распределены!*\n\n"

    # Получить детальную статистику по задачам
    try:
        import sqlite3
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Получить задачи с деталями
        cursor.execute("""
            SELECT
                mt.admin_id,
                mt.club,
                ei.equipment_type,
                ei.pc_number,
                ei.inventory_number,
                mtt.task_name
            FROM maintenance_tasks mt
            JOIN equipment_inventory ei ON mt.equipment_id = ei.id
            JOIN maintenance_task_types mtt ON mt.task_type_id = mtt.id
            WHERE mt.status IN ('pending', 'overdue')
            ORDER BY mt.admin_id, mt.club, ei.equipment_type, ei.pc_number
        """)

        # Группируем по админам
        from collections import defaultdict
        admin_tasks = defaultdict(lambda: defaultdict(list))

        for admin_id, club, eq_type, pc_num, inv_num, task_name in cursor.fetchall():
            admin_tasks[admin_id][club].append({
                'type': eq_type,
                'pc_num': pc_num,
                'inv_num': inv_num,
                'task': task_name
            })

        text += "📋 *Распределение по админам:*\n\n"

        # Получить имена админов
        admin_names = {}
        for admin_id in admin_tasks.keys():
            cursor.execute("SELECT full_name FROM admins WHERE user_id = ?", (admin_id,))
            row = cursor.fetchone()
            admin_names[admin_id] = row[0] if row and row[0] else f"Админ {admin_id}"

        for admin_id in sorted(admin_tasks.keys()):
            text += f"👤 *{admin_names[admin_id]}:*\n"

            for club in ['rio', 'sever']:
                if club not in admin_tasks[admin_id]:
                    continue

                tasks = admin_tasks[admin_id][club]
                club_emoji = '🏪' if club == 'rio' else '🏢'
                text += f"\n{club_emoji} *{club.upper()}:*\n"

                # Группируем по типу оборудования
                pc_tasks = [t for t in tasks if t['type'] == 'pc']
                kb_tasks = [t for t in tasks if t['type'] == 'keyboard']
                ms_tasks = [t for t in tasks if t['type'] == 'mouse']

                if pc_tasks:
                    pc_nums = sorted([t['pc_num'] for t in pc_tasks])
                    text += f"   💻 ПК ({len(pc_tasks)}): №{', '.join(map(str, pc_nums))}\n"

                if kb_tasks:
                    kb_nums = sorted([t['pc_num'] for t in kb_tasks])
                    text += f"   ⌨️ Клавиатуры ({len(kb_tasks)}): №{', '.join(map(str, kb_nums))}\n"

                if ms_tasks:
                    ms_nums = sorted([t['pc_num'] for t in ms_tasks])
                    text += f"   🖱 Мыши ({len(ms_tasks)}): №{', '.join(map(str, ms_nums))}\n"

            text += "\n"

        conn.close()

        if not admin_tasks:
            text += "Нет активных задач для распределения.\n"

    except Exception as e:
        logger.error(f"Error getting task stats: {e}")
        text += f"\n❌ Ошибка при получении статистики: {e}\n"

    keyboard = [[InlineKeyboardButton("« Назад", callback_data="maint_manage")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')


async def clear_all_maintenance_tasks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обнулить все задачи обслуживания (DEBUG функция)"""
    query = update.callback_query
    await query.answer()

    db_path = context.bot_data.get('db_path')

    try:
        import sqlite3
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Считаем сколько задач будет удалено
        cursor.execute("SELECT COUNT(*) FROM maintenance_tasks")
        count = cursor.fetchone()[0]

        # Удаляем все задачи
        cursor.execute("DELETE FROM maintenance_tasks")
        conn.commit()
        conn.close()

        text = f"✅ Успешно удалено {count} задач обслуживания\n\n"
        text += "Теперь можно заново распределить задачи."

        keyboard = [[InlineKeyboardButton("« Назад", callback_data="maint_manage")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(text, reply_markup=reply_markup)

    except Exception as e:
        logger.error(f"Error clearing tasks: {e}")
        await query.edit_message_text(f"❌ Ошибка при удалении задач: {e}")


async def show_equipment_browser(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать браузер оборудования для просмотра фото"""
    query = update.callback_query
    await query.answer()

    import sqlite3
    knowledge_db = '/opt/club_assistant/knowledge.db'

    try:
        conn = sqlite3.connect(knowledge_db)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Получить оборудование с фото (за последние 60 дней)
        cursor.execute("""
            SELECT
                ei.id,
                ei.equipment_type,
                ei.inventory_number,
                ei.pc_number,
                ei.club,
                COUNT(DISTINCT mp.id) as photo_count,
                MAX(mp.uploaded_at) as last_photo
            FROM equipment_inventory ei
            LEFT JOIN maintenance_photos mp ON ei.id = mp.equipment_id
                AND mp.uploaded_at >= date('now', '-60 days')
            GROUP BY ei.id
            HAVING photo_count > 0
            ORDER BY ei.club, ei.equipment_type, ei.inventory_number
        """)
        equipment = cursor.fetchall()

        conn.close()

        if not equipment:
            await query.edit_message_text(
                "📸 Фото оборудования\n\nНет фото за последние 60 дней",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("◀️ Назад", callback_data="maint_stats")
                ]])
            )
            return

        text = "📸 <b>Фото оборудования</b>\n\n"
        text += f"Всего оборудования с фото: {len(equipment)}\n\n"
        text += "Выберите оборудование для просмотра:"

        keyboard = []
        for eq in equipment[:20]:  # Показываем первые 20
            club_emoji = '🏪' if eq['club'] == 'rio' else '🏢'
            inv = eq['inventory_number'] or eq['pc_number'] or '—'
            type_emoji = {'pc': '💻', 'keyboard': '⌨️', 'mouse': '🖱', 'headset': '🎧'}.get(eq['equipment_type'], '📦')

            btn_text = f"{club_emoji} {type_emoji} {inv} ({eq['photo_count']} фото)"
            keyboard.append([InlineKeyboardButton(
                btn_text,
                callback_data=f"maint_eq_{eq['id']}_0"
            )])

        keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data="maint_stats")])

        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='HTML')

    except Exception as e:
        logger.error(f"Error showing equipment browser: {e}")
        await query.answer(f"❌ Ошибка: {e}", show_alert=True)


async def show_equipment_photos(update: Update, context: ContextTypes.DEFAULT_TYPE, equipment_id: int, page: int = 0):
    """Показать фото конкретного оборудования (по 1 фото на страницу)"""
    query = update.callback_query
    await query.answer()

    import sqlite3
    knowledge_db = '/opt/club_assistant/knowledge.db'

    try:
        conn = sqlite3.connect(knowledge_db)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Получить информацию об оборудовании
        cursor.execute("""
            SELECT
                equipment_type,
                inventory_number,
                pc_number,
                club
            FROM equipment_inventory
            WHERE id = ?
        """, (equipment_id,))
        equipment = cursor.fetchone()

        if not equipment:
            await query.edit_message_text("❌ Оборудование не найдено")
            return

        # Получить все фото этого оборудования
        cursor.execute("""
            SELECT
                mp.photo_file_id,
                mp.caption,
                mp.uploaded_at,
                mtt.task_name,
                a.full_name as admin_name
            FROM maintenance_photos mp
            LEFT JOIN maintenance_tasks mt ON mp.task_id = mt.id
            LEFT JOIN maintenance_task_types mtt ON mt.task_type_id = mtt.id
            LEFT JOIN admins a ON mp.admin_id = a.user_id
            WHERE mp.equipment_id = ?
            AND mp.uploaded_at >= date('now', '-60 days')
            ORDER BY mp.uploaded_at DESC
        """, (equipment_id,))
        photos = cursor.fetchall()

        conn.close()

        if not photos:
            await query.edit_message_text(
                "📸 Нет фото для этого оборудования",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("◀️ Назад", callback_data="maint_equipment_browser")
                ]])
            )
            return

        # Показываем по 1 фото на страницу
        total_pages = len(photos)
        page = max(0, min(page, total_pages - 1))
        photo = photos[page]

        club_emoji = '🏪' if equipment['club'] == 'rio' else '🏢'
        inv = equipment['inventory_number'] or equipment['pc_number'] or '—'
        type_emoji = {'pc': '💻', 'keyboard': '⌨️', 'mouse': '🖱', 'headset': '🎧'}.get(equipment['equipment_type'], '📦')

        caption = f"📸 <b>Фото {page + 1}/{total_pages}</b>\n\n"
        caption += f"{club_emoji} {type_emoji} {inv}\n"
        caption += f"🔧 {photo['task_name']}\n"
        caption += f"👤 {photo['admin_name']}\n"
        caption += f"📅 {format_date_ru(photo['uploaded_at'])}\n"

        if photo['caption']:
            caption += f"\n💬 <i>{photo['caption']}</i>"

        # Кнопки навигации
        keyboard = []
        nav_buttons = []
        if page > 0:
            nav_buttons.append(InlineKeyboardButton("⬅️", callback_data=f"maint_eq_{equipment_id}_{page-1}"))
        nav_buttons.append(InlineKeyboardButton(f"{page + 1}/{total_pages}", callback_data="noop"))
        if page < total_pages - 1:
            nav_buttons.append(InlineKeyboardButton("➡️", callback_data=f"maint_eq_{equipment_id}_{page+1}"))
        keyboard.append(nav_buttons)
        keyboard.append([InlineKeyboardButton("◀️ К списку оборудования", callback_data="maint_equipment_browser")])

        reply_markup = InlineKeyboardMarkup(keyboard)

        # Отправляем фото
        try:
            await query.message.delete()
        except:
            pass

        await context.bot.send_photo(
            chat_id=update.effective_chat.id,
            photo=photo['photo_file_id'],
            caption=caption,
            reply_markup=reply_markup,
            parse_mode='HTML'
        )

    except Exception as e:
        logger.error(f"Error showing equipment photos: {e}")
        await query.answer(f"❌ Ошибка: {e}", show_alert=True)


async def show_admin_photos(update: Update, context: ContextTypes.DEFAULT_TYPE, admin_id: int, page: int = 0):
    """Показать фото-отчёты админа (по 1 фото на страницу)"""
    query = update.callback_query
    await query.answer()

    import sqlite3
    knowledge_db = '/opt/club_assistant/knowledge.db'

    try:
        conn = sqlite3.connect(knowledge_db)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Получить фото админа за последние 30 дней
        cursor.execute("""
            SELECT
                mp.photo_file_id,
                mp.caption,
                mp.uploaded_at,
                mtt.task_name,
                ei.inventory_number,
                ei.pc_number,
                mt.club
            FROM maintenance_photos mp
            LEFT JOIN maintenance_tasks mt ON mp.task_id = mt.id
            LEFT JOIN maintenance_task_types mtt ON mt.task_type_id = mtt.id
            LEFT JOIN equipment_inventory ei ON mp.equipment_id = ei.id
            WHERE mp.admin_id = ?
            AND mp.uploaded_at >= date('now', '-60 days')
            ORDER BY mp.uploaded_at DESC
        """, (admin_id,))
        photos = cursor.fetchall()

        # Получить имя админа
        cursor.execute("SELECT full_name FROM admins WHERE user_id = ?", (admin_id,))
        admin = cursor.fetchone()
        admin_name = admin['full_name'] if admin else f"ID:{admin_id}"

        conn.close()

        if not photos:
            await query.edit_message_text(
                f"📸 Фото-отчёты: {admin_name}\n\nНет фото за последние 60 дней",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("◀️ Назад", callback_data=f"maint_admin_{admin_id}")
                ]])
            )
            return

        # Показываем по 1 фото на страницу
        total_pages = len(photos)
        page = max(0, min(page, total_pages - 1))
        photo = photos[page]

        club_emoji = '🏪' if photo['club'] == 'rio' else '🏢'
        inv = photo['inventory_number'] or photo['pc_number'] or '—'

        caption = f"📸 <b>Фото-отчёт {page + 1}/{total_pages}</b>\n\n"
        caption += f"👤 {admin_name}\n"
        caption += f"{club_emoji} {photo['task_name']}\n"
        caption += f"📦 {inv}\n"
        caption += f"📅 {format_date_ru(photo['uploaded_at'])}\n"

        if photo['caption']:
            caption += f"\n💬 <i>{photo['caption']}</i>"

        # Кнопки навигации
        keyboard = []
        nav_buttons = []
        if page > 0:
            nav_buttons.append(InlineKeyboardButton("⬅️", callback_data=f"maint_photo_{admin_id}_{page-1}"))
        nav_buttons.append(InlineKeyboardButton(f"{page + 1}/{total_pages}", callback_data="noop"))
        if page < total_pages - 1:
            nav_buttons.append(InlineKeyboardButton("➡️", callback_data=f"maint_photo_{admin_id}_{page+1}"))
        keyboard.append(nav_buttons)
        keyboard.append([InlineKeyboardButton("◀️ К деталям админа", callback_data=f"maint_admin_{admin_id}")])

        reply_markup = InlineKeyboardMarkup(keyboard)

        # Отправляем фото
        try:
            await query.message.delete()
        except:
            pass

        await context.bot.send_photo(
            chat_id=update.effective_chat.id,
            photo=photo['photo_file_id'],
            caption=caption,
            reply_markup=reply_markup,
            parse_mode='HTML'
        )

    except Exception as e:
        logger.error(f"Error showing admin photos: {e}")
        await query.answer(f"❌ Ошибка: {e}", show_alert=True)


async def handle_maintenance_callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик всех callback от задач обслуживания"""
    query = update.callback_query
    data = query.data

    if data == "noop":
        await query.answer()
        return

    if data == "maintenance_tasks":
        await show_maintenance_tasks(update, context)

    elif data == "maint_stats":
        await show_maintenance_stats(update, context)

    elif data.startswith("maint_admin_"):
        admin_id = int(data.replace("maint_admin_", ""))
        await show_owner_admin_maint_details(update, context, admin_id)

    elif data.startswith("maint_photos_"):
        admin_id = int(data.replace("maint_photos_", ""))
        await show_admin_photos(update, context, admin_id, page=0)

    elif data.startswith("maint_photo_"):
        # Формат: maint_photo_<admin_id>_<page>
        parts = data.replace("maint_photo_", "").split("_")
        admin_id = int(parts[0])
        page = int(parts[1])
        await show_admin_photos(update, context, admin_id, page)

    elif data == "maint_equipment_browser":
        await show_equipment_browser(update, context)

    elif data.startswith("maint_eq_"):
        # Формат: maint_eq_<equipment_id>_<page>
        parts = data.replace("maint_eq_", "").split("_")
        equipment_id = int(parts[0])
        page = int(parts[1])
        await show_equipment_photos(update, context, equipment_id, page)

    elif data == "maint_complete":
        await select_task_to_complete(update, context)

    elif data == "maint_manage":
        await show_maintenance_management(update, context)

    elif data == "maint_assign_all":
        await assign_maintenance_tasks(update, context, 'all')

    elif data == "maint_assign_pc":
        await assign_maintenance_tasks(update, context, 'pc')

    elif data == "maint_assign_keyboard":
        await assign_maintenance_tasks(update, context, 'keyboard')

    elif data == "maint_assign_mouse":
        await assign_maintenance_tasks(update, context, 'mouse')

    elif data == "maint_clear_all":
        await clear_all_maintenance_tasks(update, context)

    elif data.startswith("maint_task_"):
        await start_task_completion(update, context)


def create_maintenance_handlers():
    """Создать обработчики для задач обслуживания"""

    # ConversationHandler для выполнения задачи
    completion_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(start_task_completion, pattern="^maint_task_")],
        states={
            MAINT_UPLOAD_PHOTO: [
                MessageHandler(filters.PHOTO, receive_task_photo)
            ],
            MAINT_ENTER_NOTES: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_task_notes)
            ]
        },
        fallbacks=[
            MessageHandler(filters.Regex('^/cancel$'), cancel_task_completion),
            MessageHandler(filters.Regex('^/skip$'), receive_task_notes)
        ]
    )

    # CallbackQueryHandler для остальных действий
    callback_handler = CallbackQueryHandler(
        handle_maintenance_callbacks,
        pattern="^(maintenance_tasks|maint_stats|maint_admin_|maint_photos_|maint_photo_|maint_equipment_browser|maint_eq_|maint_complete|maint_manage|maint_assign_|maint_clear_all|noop).*$"
    )

    return [completion_conv, callback_handler]
