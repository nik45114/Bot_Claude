"""
Модуль для управления чек-листами приема смены
Автор: Club Assistant Bot
Дата: 2025-11-08
"""

import sqlite3
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Tuple
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters
)

# Состояния ConversationHandler
CHECKLIST_CHECK_ITEM, CHECKLIST_ADD_PHOTO, CHECKLIST_ADD_NOTE = range(3)

# Категории и эмодзи
CATEGORY_EMOJI = {
    'equipment': '🖥',
    'cleanliness': '🧹',
    'inventory': '📦',
    'documents': '📄',
    'safety': '🚨'
}

CATEGORY_NAMES = {
    'equipment': 'Оборудование',
    'cleanliness': 'Чистота',
    'inventory': 'Товары и запасы',
    'documents': 'Документы и касса',
    'safety': 'Безопасность'
}


class ShiftChecklistManager:
    """Менеджер чек-листов для приема смены"""

    def __init__(self, db_path: str):
        """
        Инициализация менеджера

        Args:
            db_path: путь к базе данных SQLite
        """
        self.db_path = db_path

    def _get_connection(self):
        """Получить соединение с БД"""
        return sqlite3.connect(self.db_path)

    def get_checklist_items(self, category: Optional[str] = None, club: Optional[str] = None, shift_type: Optional[str] = None) -> List[Dict]:
        """
        Получить пункты чек-листа

        Args:
            category: категория (опционально, если None - все категории)
            club: клуб ('rio' или 'sever', опционально)
            shift_type: тип смены ('morning' или 'evening', опционально)

        Returns:
            Список пунктов чек-листа
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        # Базовый WHERE
        where_conditions = ["is_active = 1"]
        params = []

        # Добавляем фильтр по категории
        if category:
            where_conditions.append("category = ?")
            params.append(category)

        # Добавляем фильтр по клубу (показывать если club NULL или совпадает)
        if club:
            where_conditions.append("(club IS NULL OR club = ?)")
            params.append(club)

        # Добавляем фильтр по типу смены (показывать если shift_type NULL или совпадает)
        if shift_type:
            where_conditions.append("(shift_type IS NULL OR shift_type = ?)")
            params.append(shift_type)

        where_clause = " AND ".join(where_conditions)

        cursor.execute(f"""
            SELECT id, category, item_name, description, is_required, requires_photo, sort_order
            FROM shift_checklist_items
            WHERE {where_clause}
            ORDER BY category, sort_order
        """, params)

        items = []
        for row in cursor.fetchall():
            items.append({
                'id': row[0],
                'category': row[1],
                'item_name': row[2],
                'description': row[3],
                'is_required': bool(row[4]),
                'requires_photo': bool(row[5]),
                'sort_order': row[6]
            })

        conn.close()
        return items

    def get_categories(self, club: Optional[str] = None, shift_type: Optional[str] = None) -> List[str]:
        """
        Получить список уникальных категорий

        Args:
            club: клуб ('rio' или 'sever', опционально)
            shift_type: тип смены ('morning' или 'evening', опционально)

        Returns:
            Список категорий
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        # Базовый WHERE
        where_conditions = ["is_active = 1"]
        params = []

        # Добавляем фильтр по клубу
        if club:
            where_conditions.append("(club IS NULL OR club = ?)")
            params.append(club)

        # Добавляем фильтр по типу смены
        if shift_type:
            where_conditions.append("(shift_type IS NULL OR shift_type = ?)")
            params.append(shift_type)

        where_clause = " AND ".join(where_conditions)

        cursor.execute(f"""
            SELECT category, MIN(sort_order) as min_order
            FROM shift_checklist_items
            WHERE {where_clause}
            GROUP BY category
            ORDER BY min_order
        """, params)

        categories = [row[0] for row in cursor.fetchall()]
        conn.close()
        return categories

    def start_checklist(self, shift_id: int, club: Optional[str] = None, shift_type: Optional[str] = None) -> bool:
        """
        Начать прохождение чек-листа для смены

        Args:
            shift_id: ID смены
            club: клуб ('rio' или 'sever', опционально)
            shift_type: тип смены ('morning' или 'evening', опционально)

        Returns:
            True если успешно, False если чек-лист уже начат
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        # Проверяем, не начат ли уже чек-лист
        cursor.execute("""
            SELECT id FROM shift_checklist_progress WHERE shift_id = ?
        """, (shift_id,))

        if cursor.fetchone():
            conn.close()
            return False

        # Подсчитываем общее количество активных пунктов с учетом фильтров
        where_conditions = ["is_active = 1"]
        params = []

        if club:
            where_conditions.append("(club IS NULL OR club = ?)")
            params.append(club)

        if shift_type:
            where_conditions.append("(shift_type IS NULL OR shift_type = ?)")
            params.append(shift_type)

        where_clause = " AND ".join(where_conditions)

        cursor.execute(f"""
            SELECT COUNT(*) FROM shift_checklist_items WHERE {where_clause}
        """, params)
        total_items = cursor.fetchone()[0]

        # Создаем запись о прогрессе
        cursor.execute("""
            INSERT INTO shift_checklist_progress
            (shift_id, started_at, total_items, checked_items, issues_count)
            VALUES (?, ?, ?, 0, 0)
        """, (shift_id, datetime.now().isoformat(), total_items))

        conn.commit()
        conn.close()
        return True

    def add_response(self, shift_id: int, item_id: int, status: str,
                    photo_file_id: Optional[str] = None, notes: Optional[str] = None) -> bool:
        """
        Добавить ответ на пункт чек-листа

        Args:
            shift_id: ID смены
            item_id: ID пункта чек-листа
            status: статус ('ok', 'issue', 'skipped')
            photo_file_id: ID фото из Telegram (опционально)
            notes: заметки (опционально)

        Returns:
            True если успешно
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        # Добавляем или обновляем ответ
        cursor.execute("""
            INSERT OR REPLACE INTO shift_checklist_responses
            (shift_id, item_id, status, photo_file_id, notes, checked_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (shift_id, item_id, status, photo_file_id, notes, datetime.now().isoformat()))

        # Обновляем прогресс
        cursor.execute("""
            UPDATE shift_checklist_progress
            SET checked_items = (
                SELECT COUNT(DISTINCT item_id)
                FROM shift_checklist_responses
                WHERE shift_id = ?
            ),
            issues_count = (
                SELECT COUNT(*)
                FROM shift_checklist_responses
                WHERE shift_id = ? AND status = 'issue'
            )
            WHERE shift_id = ?
        """, (shift_id, shift_id, shift_id))

        conn.commit()
        conn.close()
        return True

    def get_progress(self, shift_id: int) -> Optional[Dict]:
        """
        Получить прогресс чек-листа

        Args:
            shift_id: ID смены

        Returns:
            Словарь с прогрессом или None если не найдено
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT started_at, completed_at, is_completed,
                   total_items, checked_items, issues_count, last_reminder_at
            FROM shift_checklist_progress
            WHERE shift_id = ?
        """, (shift_id,))

        row = cursor.fetchone()
        conn.close()

        if not row:
            return None

        return {
            'started_at': row[0],
            'completed_at': row[1],
            'is_completed': bool(row[2]),
            'total_items': row[3],
            'checked_items': row[4],
            'issues_count': row[5],
            'last_reminder_at': row[6]
        }

    def complete_checklist(self, shift_id: int) -> bool:
        """
        Завершить чек-лист

        Args:
            shift_id: ID смены

        Returns:
            True если успешно
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE shift_checklist_progress
            SET completed_at = ?, is_completed = 1
            WHERE shift_id = ?
        """, (datetime.now().isoformat(), shift_id))

        conn.commit()
        conn.close()
        return True

    def get_responses(self, shift_id: int) -> List[Dict]:
        """
        Получить все ответы для смены

        Args:
            shift_id: ID смены

        Returns:
            Список ответов с деталями пунктов
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT
                r.id, r.item_id, r.status, r.photo_file_id, r.notes, r.checked_at,
                i.category, i.item_name, i.description
            FROM shift_checklist_responses r
            JOIN shift_checklist_items i ON r.item_id = i.id
            WHERE r.shift_id = ?
            ORDER BY i.category, i.sort_order
        """, (shift_id,))

        responses = []
        for row in cursor.fetchall():
            responses.append({
                'id': row[0],
                'item_id': row[1],
                'status': row[2],
                'photo_file_id': row[3],
                'notes': row[4],
                'checked_at': row[5],
                'category': row[6],
                'item_name': row[7],
                'description': row[8]
            })

        conn.close()
        return responses

    def update_reminder(self, shift_id: int):
        """
        Обновить время последнего напоминания

        Args:
            shift_id: ID смены
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE shift_checklist_progress
            SET last_reminder_at = ?
            WHERE shift_id = ?
        """, (datetime.now().isoformat(), shift_id))

        conn.commit()
        conn.close()

    def get_incomplete_checklists(self, hours_threshold: int = 4) -> List[Dict]:
        """
        Получить незавершенные чек-листы старше определенного времени

        Args:
            hours_threshold: порог в часах

        Returns:
            Список незавершенных чек-листов с информацией о смене
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        threshold_time = (datetime.now() - timedelta(hours=hours_threshold)).isoformat()

        cursor.execute("""
            SELECT
                p.shift_id, p.started_at, p.total_items, p.checked_items, p.issues_count,
                s.admin_id, s.club, s.shift_type
            FROM shift_checklist_progress p
            JOIN active_shifts s ON p.shift_id = s.id
            WHERE p.is_completed = 0 AND p.started_at < ? AND s.status = 'open'
        """, (threshold_time,))

        checklists = []
        for row in cursor.fetchall():
            checklists.append({
                'shift_id': row[0],
                'started_at': row[1],
                'total_items': row[2],
                'checked_items': row[3],
                'issues_count': row[4],
                'admin_id': row[5],
                'club': row[6],
                'shift_type': row[7]
            })

        conn.close()
        return checklists


# Функции для ConversationHandler

async def start_checklist_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Начать чек-лист при открытии смены"""
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id

    # Получаем shift_id из context
    if 'current_shift_id' not in context.user_data:
        await query.edit_message_text("❌ Ошибка: смена не найдена")
        return ConversationHandler.END

    shift_id = context.user_data['current_shift_id']
    db_path = context.bot_data.get('db_path', '/opt/club_assistant/club_assistant.db')

    # Получаем информацию о смене (клуб и тип смены)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("""
        SELECT club, shift_type FROM active_shifts WHERE id = ?
    """, (shift_id,))
    shift_info = cursor.fetchone()
    conn.close()

    if not shift_info:
        await query.edit_message_text("❌ Ошибка: смена не найдена в базе")
        return ConversationHandler.END

    club = shift_info['club']
    shift_type = shift_info['shift_type']

    checklist_manager = ShiftChecklistManager(db_path)

    # Начинаем чек-лист
    if not checklist_manager.start_checklist(shift_id, club=club, shift_type=shift_type):
        await query.edit_message_text("⚠️ Чек-лист для этой смены уже начат")
        return ConversationHandler.END

    # Сохраняем manager и текущую категорию в context
    context.user_data['checklist_manager'] = checklist_manager
    context.user_data['checklist_shift_id'] = shift_id
    context.user_data['checklist_club'] = club
    context.user_data['checklist_shift_type'] = shift_type
    context.user_data['checklist_categories'] = checklist_manager.get_categories(club=club, shift_type=shift_type)
    context.user_data['checklist_current_category_idx'] = 0
    context.user_data['checklist_current_item_idx'] = 0

    # Показываем первую категорию
    return await show_next_item(update, context)


async def show_next_item(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Показать следующий пункт чек-листа"""
    checklist_manager: ShiftChecklistManager = context.user_data['checklist_manager']
    categories = context.user_data['checklist_categories']
    club = context.user_data.get('checklist_club')
    shift_type = context.user_data.get('checklist_shift_type')
    cat_idx = context.user_data['checklist_current_category_idx']

    # Проверяем, не закончились ли категории
    if cat_idx >= len(categories):
        return await complete_checklist(update, context)

    current_category = categories[cat_idx]
    items = checklist_manager.get_checklist_items(current_category, club=club, shift_type=shift_type)

    # Сохраняем items для текущей категории
    if 'checklist_current_items' not in context.user_data or \
       context.user_data.get('checklist_last_category') != current_category:
        context.user_data['checklist_current_items'] = items
        context.user_data['checklist_current_item_idx'] = 0
        context.user_data['checklist_last_category'] = current_category

    item_idx = context.user_data['checklist_current_item_idx']

    # Проверяем, не закончились ли items в категории
    if item_idx >= len(items):
        # Переходим к следующей категории
        context.user_data['checklist_current_category_idx'] += 1
        return await show_next_item(update, context)

    current_item = items[item_idx]
    context.user_data['checklist_current_item_id'] = current_item['id']

    # Формируем сообщение
    emoji = CATEGORY_EMOJI.get(current_category, '📋')
    category_name = CATEGORY_NAMES.get(current_category, current_category)

    # Считаем прогресс локально без запроса к БД
    total_items = sum(len(checklist_manager.get_checklist_items(cat, club=club, shift_type=shift_type)) for cat in categories)
    checked_items = 0
    for cat_i in range(cat_idx):
        checked_items += len(checklist_manager.get_checklist_items(categories[cat_i], club=club, shift_type=shift_type))
    checked_items += item_idx

    text = f"✅ *Чек-лист приема смены*\n\n"
    text += f"{emoji} *Категория:* {category_name}\n"
    text += f"📊 *Прогресс:* {checked_items}/{total_items}\n\n"
    text += f"*Пункт:* {current_item['item_name']}\n"

    if current_item['description']:
        text += f"_{current_item['description']}_\n"

    # Кнопки - упрощенные для быстрого прохождения
    keyboard = [
        [
            InlineKeyboardButton("✅ ОК", callback_data="checklist_ok"),
            InlineKeyboardButton("⚠️ Проблема", callback_data="checklist_issue")
        ]
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)

    # Отправляем или редактируем сообщение
    if update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
    else:
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='Markdown')

    return CHECKLIST_CHECK_ITEM


async def handle_item_response(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработать ответ на пункт чек-листа"""
    query = update.callback_query
    await query.answer()

    action = query.data.split('_')[1]  # ok, issue

    checklist_manager: ShiftChecklistManager = context.user_data['checklist_manager']
    shift_id = context.user_data['checklist_shift_id']
    item_id = context.user_data['checklist_current_item_id']

    if action == 'ok':
        # Все в порядке - сохраняем и переходим дальше
        checklist_manager.add_response(shift_id, item_id, 'ok')
        context.user_data['checklist_current_item_idx'] += 1
        return await show_next_item(update, context)

    elif action == 'issue':
        # Есть проблема - сразу сохраняем и переходим дальше
        checklist_manager.add_response(shift_id, item_id, 'issue')
        context.user_data['checklist_current_item_idx'] += 1
        return await show_next_item(update, context)


async def handle_photo_upload(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработать загрузку фото"""
    if update.message and update.message.photo:
        # Получаем file_id самого большого фото
        photo_file_id = update.message.photo[-1].file_id

        checklist_manager: ShiftChecklistManager = context.user_data['checklist_manager']
        shift_id = context.user_data['checklist_shift_id']
        item_id = context.user_data['checklist_issue_item_id']

        # Сохраняем ответ с фото
        checklist_manager.add_response(shift_id, item_id, 'issue', photo_file_id=photo_file_id)

        await update.message.reply_text("✅ Фото сохранено")

        # Переходим к следующему пункту
        context.user_data['checklist_current_item_idx'] += 1
        return await show_next_item(update, context)

    elif update.callback_query:
        query = update.callback_query
        await query.answer()

        if query.data == "checklist_upload_photo":
            await query.edit_message_text("📸 Отправьте фото проблемы")
            return CHECKLIST_ADD_PHOTO

        elif query.data == "checklist_add_note":
            await query.edit_message_text("📝 Напишите комментарий о проблеме")
            return CHECKLIST_ADD_NOTE

        elif query.data == "checklist_continue_issue":
            checklist_manager: ShiftChecklistManager = context.user_data['checklist_manager']
            shift_id = context.user_data['checklist_shift_id']
            item_id = context.user_data['checklist_issue_item_id']

            checklist_manager.add_response(shift_id, item_id, 'issue')
            context.user_data['checklist_current_item_idx'] += 1
            return await show_next_item(update, context)


async def handle_note_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработать ввод комментария"""
    if update.message and update.message.text:
        note = update.message.text

        checklist_manager: ShiftChecklistManager = context.user_data['checklist_manager']
        shift_id = context.user_data['checklist_shift_id']
        item_id = context.user_data['checklist_issue_item_id']

        # Сохраняем ответ с комментарием
        checklist_manager.add_response(shift_id, item_id, 'issue', notes=note)

        await update.message.reply_text("✅ Комментарий сохранен")

        # Переходим к следующему пункту
        context.user_data['checklist_current_item_idx'] += 1
        return await show_next_item(update, context)


async def complete_checklist(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Завершить чек-лист"""
    checklist_manager: ShiftChecklistManager = context.user_data['checklist_manager']
    shift_id = context.user_data['checklist_shift_id']

    # Завершаем чек-лист
    checklist_manager.complete_checklist(shift_id)

    # Получаем итоги
    progress = checklist_manager.get_progress(shift_id)
    responses = checklist_manager.get_responses(shift_id)

    issues = [r for r in responses if r['status'] == 'issue']
    ok_count = progress['checked_items'] - progress['issues_count']

    text = "🎉 *Чек-лист приема смены завершен!*\n\n"
    text += f"📊 *Итоги проверки:*\n"
    text += f"✅ ОК: {ok_count}\n"
    text += f"⚠️ Проблемы: {progress['issues_count']}\n"
    text += f"📝 Всего проверено: {progress['checked_items']}/{progress['total_items']}\n\n"

    if issues:
        text += "*Обнаруженные проблемы:*\n"
        for issue in issues:
            emoji = CATEGORY_EMOJI.get(issue['category'], '📋')
            text += f"{emoji} {issue['item_name']}\n"
            if issue['notes']:
                text += f"  _{issue['notes']}_\n"
        text += "\n"

    # Кнопки
    keyboard = []
    if issues:
        # Сохраняем данные для отправки проблем
        context.user_data['checklist_completed_shift_id'] = shift_id
        context.user_data['checklist_completed_issues'] = issues

        keyboard.append([InlineKeyboardButton("📢 Сообщить проверяющему", callback_data="checklist_notify_controller")])
        text += "Вы можете сообщить о проблемах дежурному контролеру."
    else:
        text += "Смена успешно принята! Можно приступать к работе."

    reply_markup = InlineKeyboardMarkup(keyboard) if keyboard else None

    if update.callback_query:
        await update.callback_query.edit_message_text(text, parse_mode='Markdown', reply_markup=reply_markup)
    else:
        await update.message.reply_text(text, parse_mode='Markdown', reply_markup=reply_markup)

    # Не очищаем user_data сразу, если есть кнопка уведомления
    if not issues:
        keys_to_remove = [k for k in context.user_data.keys() if k.startswith('checklist_')]
        for key in keys_to_remove:
            del context.user_data[key]
        return ConversationHandler.END

    return ConversationHandler.END


async def cancel_checklist(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Отменить чек-лист"""
    query = update.callback_query
    await query.answer()

    # Очищаем user_data
    keys_to_remove = [k for k in context.user_data.keys() if k.startswith('checklist_')]
    for key in keys_to_remove:
        del context.user_data[key]

    await query.edit_message_text("❌ Чек-лист отменен. Вы можете вернуться к нему позже.")

    return ConversationHandler.END


async def notify_controller(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отправить уведомление дежурному контролеру о проблемах"""
    query = update.callback_query
    await query.answer()

    try:
        shift_id = context.user_data.get('checklist_completed_shift_id')
        issues = context.user_data.get('checklist_completed_issues', [])

        if not shift_id or not issues:
            await query.edit_message_text("❌ Не удалось найти данные о проблемах.")
            return

        # Получаем информацию о смене админа
        import sqlite3
        conn = sqlite3.connect('knowledge.db')
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("""
            SELECT club, shift_date
            FROM active_shifts
            WHERE id = ?
        """, (shift_id,))

        shift_info = cursor.fetchone()
        if not shift_info:
            conn.close()
            await query.edit_message_text("❌ Не удалось найти информацию о смене.")
            return

        club = shift_info['club']
        shift_date = shift_info['shift_date']

        # Находим дежурную смену на сегодня
        cursor.execute("""
            SELECT user_id, duty_person
            FROM duty_shifts
            WHERE shift_date = date('now', '+3 hours')
            AND user_id IS NOT NULL
            LIMIT 1
        """, ())

        duty_shift = cursor.fetchone()
        conn.close()

        if not duty_shift or not duty_shift['user_id']:
            await query.edit_message_text(
                "⚠️ На сегодня не назначен дежурный контролер.\n"
                "Проблемы зафиксированы в системе, но уведомление не отправлено."
            )
            return

        controller_id = duty_shift['user_id']
        duty_person = duty_shift['duty_person']

        # Формируем уведомление для контролера
        admin_name = update.effective_user.full_name
        admin_username = f"@{update.effective_user.username}" if update.effective_user.username else ""

        ctrl_text = f"⚠️ *Обнаружены проблемы при приеме смены*\n\n"
        ctrl_text += f"👤 Админ: {admin_name} {admin_username}\n"
        ctrl_text += f"🏢 Клуб: {club}\n"
        ctrl_text += f"📅 Дата: {shift_date}\n"
        ctrl_text += f"🆔 ID смены: {shift_id}\n\n"
        ctrl_text += f"*Обнаружено проблем: {len(issues)}*\n\n"

        for issue in issues:
            emoji = CATEGORY_EMOJI.get(issue['category'], '📋')
            ctrl_text += f"{emoji} *{issue['item_name']}*\n"
            if issue['notes']:
                ctrl_text += f"  _{issue['notes']}_\n"
            ctrl_text += "\n"

        # Отправляем уведомление контролеру
        await context.bot.send_message(
            chat_id=controller_id,
            text=ctrl_text,
            parse_mode='Markdown'
        )

        # Отправляем фото, если есть
        for issue in issues:
            if issue.get('photo_file_id'):
                await context.bot.send_photo(
                    chat_id=controller_id,
                    photo=issue['photo_file_id'],
                    caption=f"Проблема: {issue['item_name']}"
                )

        # Уведомляем админа об успешной отправке
        await query.edit_message_text(
            f"✅ Уведомление отправлено дежурному контролеру ({duty_person}).\n\n"
            "Проблемы будут рассмотрены в ближайшее время."
        )

        # Очищаем данные
        keys_to_remove = [k for k in context.user_data.keys() if k.startswith('checklist_')]
        for key in keys_to_remove:
            del context.user_data[key]

    except Exception as e:
        logger.error(f"Ошибка при отправке уведомления контролеру: {e}")
        await query.edit_message_text("❌ Произошла ошибка при отправке уведомления.")


# ConversationHandler для чек-листа
def create_checklist_conversation_handler():
    """Создать и вернуть ConversationHandler для чек-листа"""
    return ConversationHandler(
        entry_points=[
            CallbackQueryHandler(start_checklist_conversation, pattern="^checklist_start$")
        ],
        states={
            CHECKLIST_CHECK_ITEM: [
                CallbackQueryHandler(handle_item_response, pattern="^checklist_(ok|issue|skip)$"),
                CallbackQueryHandler(cancel_checklist, pattern="^checklist_cancel$")
            ],
            CHECKLIST_ADD_PHOTO: [
                CallbackQueryHandler(handle_photo_upload, pattern="^checklist_(upload_photo|add_note|continue_issue)$"),
                MessageHandler(filters.PHOTO, handle_photo_upload)
            ],
            CHECKLIST_ADD_NOTE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_note_input)
            ]
        },
        fallbacks=[
            CallbackQueryHandler(cancel_checklist, pattern="^checklist_cancel$")
        ],
        name="shift_checklist",
        persistent=False
    )
