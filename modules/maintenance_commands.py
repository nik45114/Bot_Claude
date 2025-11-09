"""
Команды для управления задачами обслуживания оборудования
"""

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CallbackQueryHandler, MessageHandler, ConversationHandler, filters
from modules.maintenance_manager import MaintenanceManager

logger = logging.getLogger(__name__)

# Состояния для ConversationHandler
MAINT_UPLOAD_PHOTO, MAINT_ENTER_NOTES = range(2)


async def show_maintenance_tasks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать задачи обслуживания админа"""
    query = update.callback_query
    if query:
        await query.answer()

    user_id = update.effective_user.id
    db_path = context.bot_data.get('db_path')
    owner_id = context.bot_data.get('owner_id')

    manager = MaintenanceManager(db_path)

    # Получить задачи админа
    pending_tasks = manager.get_admin_tasks(user_id, status='pending')
    overdue_tasks = manager.get_admin_tasks(user_id, status='overdue')
    completed_tasks = manager.get_admin_tasks(user_id, status='completed')

    text = "🔧 *Задачи обслуживания оборудования*\n\n"

    if overdue_tasks:
        text += f"⚠️ *Просрочено ({len(overdue_tasks)}):*\n"
        for task in overdue_tasks[:5]:
            club_emoji = '🏪' if task['club'] == 'rio' else '🏢'
            text += f"{club_emoji} {task['task_name']}\n"
            text += f"   {task['inventory_number']} (ПК №{task['pc_number']})\n"
            text += f"   До: {task['due_date']}\n\n"

    if pending_tasks:
        text += f"📋 *Активные ({len(pending_tasks)}):*\n"
        for task in pending_tasks[:5]:
            club_emoji = '🏪' if task['club'] == 'rio' else '🏢'
            text += f"{club_emoji} {task['task_name']}\n"
            text += f"   {task['inventory_number']} (ПК №{task['pc_number']})\n"
            text += f"   До: {task['due_date']}\n\n"

    if completed_tasks:
        text += f"✅ Выполнено: {len(completed_tasks)}\n\n"

    if not pending_tasks and not overdue_tasks:
        text += "У вас нет активных задач обслуживания\n"

    keyboard = []

    if pending_tasks or overdue_tasks:
        keyboard.append([InlineKeyboardButton("✅ Отметить выполнение", callback_data="maint_complete")])

    # Кнопка управления для владельца
    if user_id == owner_id:
        keyboard.append([InlineKeyboardButton("⚙️ Управление задачами", callback_data="maint_manage")])

    keyboard.append([InlineKeyboardButton("« Главное меню", callback_data="main_menu")])

    reply_markup = InlineKeyboardMarkup(keyboard)

    if query:
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
    else:
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='Markdown')


async def select_task_to_complete(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Выбрать задачу для отметки выполнения"""
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id
    db_path = context.bot_data.get('db_path')

    manager = MaintenanceManager(db_path)

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
    manager = MaintenanceManager(db_path)

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
    manager = MaintenanceManager(db_path)

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
    manager = MaintenanceManager(db_path)

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

    text += "Нажмите кнопку для автоматического распределения задач обслуживания пропорционально сменам."

    keyboard = [
        [InlineKeyboardButton("✅ Распределить задачи", callback_data="maint_assign_all")],
        [InlineKeyboardButton("« Назад", callback_data="maintenance_tasks")]
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')


async def assign_maintenance_tasks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Распределить задачи обслуживания"""
    query = update.callback_query
    await query.answer()

    db_path = context.bot_data.get('db_path')
    manager = MaintenanceManager(db_path)

    await query.edit_message_text("⏳ Распределяю задачи обслуживания...", parse_mode='Markdown')

    # Распределить ВСЕ задачи (компы, клавиатуры, мыши)
    manager.assign_tasks_proportionally('all')

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


async def handle_maintenance_callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик всех callback от задач обслуживания"""
    query = update.callback_query
    data = query.data

    if data == "maintenance_tasks":
        await show_maintenance_tasks(update, context)

    elif data == "maint_complete":
        await select_task_to_complete(update, context)

    elif data == "maint_manage":
        await show_maintenance_management(update, context)

    elif data == "maint_assign_all":
        await assign_maintenance_tasks(update, context)

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
        pattern="^(maintenance_tasks|maint_complete|maint_manage|maint_assign_).*$"
    )

    return [completion_conv, callback_handler]
