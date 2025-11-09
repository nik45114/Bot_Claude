"""
Модуль управления сменами дежурных (Правый Глаз / Левый Глаз)
Автор: Club Assistant Bot
Дата: 2025-11-08
"""

import sqlite3
import logging
from datetime import datetime, date, timedelta, timezone
from typing import Optional, Dict, List, Tuple
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CallbackQueryHandler, ConversationHandler, MessageHandler, CommandHandler, filters

# Moscow timezone (UTC+3)
MSK = timezone(timedelta(hours=3))

logger = logging.getLogger(__name__)

# Состояния для ConversationHandler
DUTY_ENTER_HANDOVER_NOTES, DUTY_CHECKLIST_CATEGORY, DUTY_CHECKLIST_ITEM = range(3)


class DutyShiftManager:
    """Менеджер смен дежурных"""

    def __init__(self, db_path: str):
        self.db_path = db_path

    def get_current_duty_person(self, target_date: date = None) -> str:
        """
        Определить кто дежурит в указанную дату

        Args:
            target_date: Дата для проверки (по умолчанию сегодня)

        Returns:
            'Правый Глаз' или 'Левый Глаз'
        """
        if target_date is None:
            target_date = datetime.now(MSK).date()

        # График начинается с 15.10.25
        start_date = date(2025, 10, 15)
        days_diff = (target_date - start_date).days
        cycle_day = days_diff % 4  # 4-дневный цикл

        if cycle_day < 2:
            return "Правый Глаз"
        else:
            return "Левый Глаз"

    def get_or_create_shift(self, shift_date: date, user_id: int = None, username: str = None) -> int:
        """
        Получить или создать смену дежурного

        Args:
            shift_date: Дата смены
            user_id: ID пользователя Telegram
            username: Username пользователя

        Returns:
            ID смены
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            duty_person = self.get_current_duty_person(shift_date)

            # Проверяем, есть ли уже смена на эту дату
            cursor.execute("""
                SELECT id FROM duty_shifts
                WHERE shift_date = ?
            """, (shift_date,))

            row = cursor.fetchone()

            if row:
                shift_id = row[0]
                # Обновляем user_id и username если они предоставлены
                if user_id:
                    cursor.execute("""
                        UPDATE duty_shifts
                        SET user_id = ?, username = ?
                        WHERE id = ?
                    """, (user_id, username, shift_id))
                    conn.commit()
            else:
                # Создаем новую смену
                cursor.execute("""
                    INSERT INTO duty_shifts (duty_person, user_id, username, shift_date, started_at)
                    VALUES (?, ?, ?, ?, ?)
                """, (duty_person, user_id, username, shift_date, datetime.now(MSK)))
                shift_id = cursor.lastrowid
                conn.commit()

                # Создаем записи в checklist_progress для всех активных пунктов
                cursor.execute("""
                    INSERT INTO duty_checklist_progress (shift_id, item_id)
                    SELECT ?, id FROM duty_checklist_items WHERE is_active = 1
                """, (shift_id,))
                conn.commit()

            conn.close()
            return shift_id

        except Exception as e:
            logger.error(f"❌ Error getting/creating duty shift: {e}")
            return None

    def get_shift_info(self, shift_id: int) -> Optional[Dict]:
        """Получить информацию о смене"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("""
                SELECT id, duty_person, user_id, username, shift_date,
                       started_at, ended_at, handover_notes, checklist_completed
                FROM duty_shifts
                WHERE id = ?
            """, (shift_id,))

            row = cursor.fetchone()
            conn.close()

            if row:
                return {
                    'id': row[0],
                    'duty_person': row[1],
                    'user_id': row[2],
                    'username': row[3],
                    'shift_date': row[4],
                    'started_at': row[5],
                    'ended_at': row[6],
                    'handover_notes': row[7],
                    'checklist_completed': row[8]
                }
            return None

        except Exception as e:
            logger.error(f"❌ Error getting shift info: {e}")
            return None

    def get_previous_shift_notes(self, current_shift_date: date) -> Optional[str]:
        """
        Получить заметки от предыдущей закрытой смены дежурного

        Args:
            current_shift_date: Дата текущей смены

        Returns:
            Текст заметок или None
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("""
                SELECT handover_notes, duty_person, shift_date
                FROM duty_shifts
                WHERE shift_date < ?
                  AND handover_notes IS NOT NULL
                  AND handover_notes != ''
                ORDER BY shift_date DESC
                LIMIT 1
            """, (current_shift_date,))

            row = cursor.fetchone()
            conn.close()

            if row:
                notes, duty_person, shift_date = row
                return notes
            return None

        except Exception as e:
            logger.error(f"❌ Error getting previous shift notes: {e}")
            return None

    def get_checklist_categories(self, club: str = None, shift_type: str = None) -> List[str]:
        """
        Получить список категорий чек-листа с учетом фильтров

        Args:
            club: Название клуба ('Рио' или 'Север'), None = все
            shift_type: Тип смены ('morning' или 'evening'), None = все
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("""
                SELECT DISTINCT category, MIN(sort_order) as min_order
                FROM duty_checklist_items
                WHERE is_active = 1
                  AND (club IS NULL OR club = ?)
                  AND (shift_type IS NULL OR shift_type = ?)
                GROUP BY category
                ORDER BY min_order
            """, (club, shift_type))

            categories = [row[0] for row in cursor.fetchall()]
            conn.close()
            return categories

        except Exception as e:
            logger.error(f"❌ Error getting checklist categories: {e}")
            return []

    def get_checklist_items(self, category: str, club: str = None, shift_type: str = None) -> List[Dict]:
        """
        Получить пункты чек-листа для категории с учетом фильтров

        Args:
            category: Название категории
            club: Название клуба ('Рио' или 'Север'), None = все
            shift_type: Тип смены ('morning' или 'evening'), None = все
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("""
                SELECT id, item_text, description, requires_photo
                FROM duty_checklist_items
                WHERE category = ? AND is_active = 1
                  AND (club IS NULL OR club = ?)
                  AND (shift_type IS NULL OR shift_type = ?)
                ORDER BY sort_order
            """, (category, club, shift_type))

            items = []
            for row in cursor.fetchall():
                items.append({
                    'id': row[0],
                    'item_text': row[1],
                    'description': row[2],
                    'requires_photo': row[3]
                })

            conn.close()
            return items

        except Exception as e:
            logger.error(f"❌ Error getting checklist items: {e}")
            return []

    def get_checklist_progress(self, shift_id: int, club: str = None, shift_type: str = None) -> Dict:
        """
        Получить прогресс по чек-листу с учетом фильтров

        Args:
            shift_id: ID смены дежурного
            club: Название клуба ('Рио' или 'Север'), None = все
            shift_type: Тип смены ('morning' или 'evening'), None = все

        Returns:
            {'total': int, 'checked': int, 'items': {...}}
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Получаем все пункты с их статусом с учетом фильтров
            cursor.execute("""
                SELECT
                    dci.id,
                    dci.category,
                    dci.item_text,
                    dci.description,
                    dcp.checked,
                    dcp.notes,
                    dcp.checked_at
                FROM duty_checklist_items dci
                LEFT JOIN duty_checklist_progress dcp ON dci.id = dcp.item_id AND dcp.shift_id = ?
                WHERE dci.is_active = 1
                  AND (dci.club IS NULL OR dci.club = ?)
                  AND (dci.shift_type IS NULL OR dci.shift_type = ?)
                ORDER BY dci.sort_order
            """, (shift_id, club, shift_type))

            items = {}
            total = 0
            checked = 0

            for row in cursor.fetchall():
                item_id = row[0]
                category = row[1]

                if category not in items:
                    items[category] = []

                is_checked = row[4] == 1 if row[4] is not None else False

                items[category].append({
                    'id': item_id,
                    'text': row[2],
                    'description': row[3],
                    'checked': is_checked,
                    'notes': row[5],
                    'checked_at': row[6]
                })

                total += 1
                if is_checked:
                    checked += 1

            conn.close()

            return {
                'total': total,
                'checked': checked,
                'items': items
            }

        except Exception as e:
            logger.error(f"❌ Error getting checklist progress: {e}")
            return {'total': 0, 'checked': 0, 'items': {}}

    def toggle_checklist_item(self, shift_id: int, item_id: int, notes: str = None) -> bool:
        """Переключить статус пункта чек-листа"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Проверяем текущий статус
            cursor.execute("""
                SELECT checked FROM duty_checklist_progress
                WHERE shift_id = ? AND item_id = ?
            """, (shift_id, item_id))

            row = cursor.fetchone()

            if row:
                new_status = not row[0]
                cursor.execute("""
                    UPDATE duty_checklist_progress
                    SET checked = ?, checked_at = ?, notes = ?
                    WHERE shift_id = ? AND item_id = ?
                """, (new_status, datetime.now(MSK) if new_status else None, notes, shift_id, item_id))
            else:
                # Создаем запись если её нет
                cursor.execute("""
                    INSERT INTO duty_checklist_progress (shift_id, item_id, checked, checked_at, notes)
                    VALUES (?, ?, 1, ?, ?)
                """, (shift_id, item_id, datetime.now(MSK), notes))

            conn.commit()
            conn.close()
            return True

        except Exception as e:
            logger.error(f"❌ Error toggling checklist item: {e}")
            return False

    def save_handover_notes(self, shift_id: int, notes: str) -> bool:
        """Сохранить заметки при передаче смены"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("""
                UPDATE duty_shifts
                SET handover_notes = ?, ended_at = ?
                WHERE id = ?
            """, (notes, datetime.now(MSK), shift_id))

            conn.commit()
            conn.close()
            return True

        except Exception as e:
            logger.error(f"❌ Error saving handover notes: {e}")
            return False

    def complete_checklist(self, shift_id: int) -> bool:
        """Отметить чек-лист как завершенный"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("""
                UPDATE duty_shifts
                SET checklist_completed = 1, ended_at = ?
                WHERE id = ?
            """, (datetime.now(MSK), shift_id))

            conn.commit()
            conn.close()
            return True

        except Exception as e:
            logger.error(f"❌ Error completing checklist: {e}")
            return False


# Обработчики команд

async def show_duty_shift_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать меню смены дежурного"""
    query = update.callback_query
    if query:
        await query.answer()

    user_id = update.effective_user.id
    username = update.effective_user.username

    db_path = context.bot_data.get('db_path')
    manager = DutyShiftManager(db_path)

    # Получаем или создаем смену на сегодня
    today = datetime.now(MSK).date()
    shift_id = manager.get_or_create_shift(today, user_id, username)

    if not shift_id:
        text = "❌ Ошибка при создании смены"
        keyboard = [[InlineKeyboardButton("« Назад", callback_data="main_menu")]]
    else:
        context.user_data['current_duty_shift_id'] = shift_id

        shift_info = manager.get_shift_info(shift_id)
        progress = manager.get_checklist_progress(shift_id)

        duty_person = shift_info['duty_person']

        text = f"👁 *Смена дежурного*\n\n"
        text += f"📅 Дата: {today.strftime('%d.%m.%Y')}\n"
        text += f"👤 Дежурный: *{duty_person}*\n"

        if shift_info.get('username'):
            text += f"📱 Контакт: @{shift_info['username']}\n"

        text += f"\n📋 Чек-лист: {progress['checked']}/{progress['total']}\n"

        # Показать заметки от ПРЕДЫДУЩЕЙ смены (не текущей!)
        previous_notes = manager.get_previous_shift_notes(today)
        if previous_notes:
            text += f"\n📝 *Заметки от предыдущего дежурного:*\n{previous_notes}\n"

        keyboard = [
            [InlineKeyboardButton("✅ Чек-лист", callback_data="duty_checklist")],
            [InlineKeyboardButton("📝 Оставить заметки при передаче", callback_data="duty_handover")],
            [InlineKeyboardButton("« Главное меню", callback_data="main_menu")]
        ]

    reply_markup = InlineKeyboardMarkup(keyboard)

    if query:
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
    else:
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='Markdown')


async def show_controller_schedule(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать график дежурств контролёра"""
    query = update.callback_query
    if query:
        await query.answer()

    db_path = context.bot_data.get('db_path', '/opt/club_assistant/club_assistant.db')

    try:
        import sqlite3
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Получаем график на неделю вперед
        today = datetime.now(MSK).date()
        week_dates = [today + timedelta(days=i) for i in range(7)]

        text = "📅 **График дежурств на неделю**\n\n"

        for day_date in week_dates:
            # Форматируем дату
            day_name = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"][day_date.weekday()]
            date_str = day_date.strftime('%d.%m')

            # Эмодзи для текущего дня
            day_emoji = "📍" if day_date == today else "📆"

            text += f"{day_emoji} **{day_name} {date_str}**\n"

            # Получаем дежурных на этот день
            cursor.execute("""
                SELECT d.club, d.shift_type, ad.full_name, ad.user_id
                FROM duty_schedule d
                LEFT JOIN admins ad ON d.admin_id = ad.user_id
                WHERE d.duty_date = ?
                ORDER BY d.club, d.shift_type
            """, (day_date.isoformat(),))

            duties = cursor.fetchall()

            if duties:
                for duty in duties:
                    admin_name = duty['full_name'] or f"ID:{duty['user_id']}"
                    shift_emoji = "☀️" if duty['shift_type'] == 'morning' else "🌙"
                    text += f"  {shift_emoji} {duty['club']} - {admin_name}\n"
            else:
                text += "  _Не назначено_\n"

            text += "\n"

        conn.close()

    except Exception as e:
        logger.error(f"Error in show_controller_schedule: {e}")
        text = f"📅 **График дежурств**\n\n❌ Ошибка загрузки данных: {e}"

    keyboard = [
        [InlineKeyboardButton("🔄 Обновить", callback_data="ctrl_schedule")],
        [InlineKeyboardButton("◀️ Назад в главное меню", callback_data="main_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    if query:
        try:
            await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
        except Exception as e:
            logger.error(f"Error editing message: {e}")
            await query.message.reply_text(text, reply_markup=reply_markup, parse_mode='Markdown')
    else:
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='Markdown')


async def show_duty_checklist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать выбор клуба для чек-листа дежурного"""
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id
    username = update.effective_user.username

    db_path = context.bot_data.get('db_path')
    manager = DutyShiftManager(db_path)

    # Получить или создать смену дежурного на сегодня
    today = datetime.now(MSK).date()
    shift_id = manager.get_or_create_shift(today, user_id, username)

    if not shift_id:
        await query.edit_message_text("❌ Не удалось создать смену дежурного")
        return

    # Сохранить shift_id в context
    context.user_data['current_duty_shift_id'] = shift_id

    # Определить тип смены по времени (утро до 18:00, вечер после)
    now = datetime.now(MSK)
    shift_type = 'morning' if now.hour < 18 else 'evening'
    context.user_data['duty_shift_type'] = shift_type

    text = "📋 *Чек-лист дежурного*\n\n"
    text += "Выберите клуб для проверки:\n"

    keyboard = [
        [InlineKeyboardButton("🏪 РИО", callback_data="duty_club_rio")],
        [InlineKeyboardButton("🏢 СЕВЕР", callback_data="duty_club_sever")],
        [InlineKeyboardButton("« Назад", callback_data="duty_shift_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')


async def show_duty_checklist_categories(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать категории чек-листа после выбора клуба"""
    query = update.callback_query
    await query.answer()

    # Извлекаем клуб из callback_data
    club = query.data.replace("duty_club_", "")
    if club == 'rio':
        club_name = 'Рио'
    else:
        club_name = 'Север'

    context.user_data['duty_club'] = club_name

    db_path = context.bot_data.get('db_path')
    manager = DutyShiftManager(db_path)

    shift_type = context.user_data.get('duty_shift_type', 'morning')
    categories = manager.get_checklist_categories(club_name, shift_type)

    # Сохраняем категории в context
    context.user_data['duty_categories'] = categories

    text = f"📋 *Чек-лист дежурного - {club_name}*\n\n"
    text += "Выберите категорию для проверки:\n"

    keyboard = []
    for idx, category in enumerate(categories):
        keyboard.append([InlineKeyboardButton(category, callback_data=f"duty_cat_{idx}")])

    keyboard.append([InlineKeyboardButton("« Назад", callback_data="duty_checklist")])
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')


async def show_duty_category(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать пункты категории чек-листа"""
    query = update.callback_query
    await query.answer()

    # Извлекаем индекс категории из callback_data
    cat_idx = int(query.data.replace("duty_cat_", ""))

    categories = context.user_data.get('duty_categories', [])
    if cat_idx >= len(categories):
        await query.edit_message_text("❌ Категория не найдена")
        return

    category = categories[cat_idx]

    shift_id = context.user_data.get('current_duty_shift_id')
    if not shift_id:
        await query.edit_message_text("❌ Смена не найдена")
        return

    db_path = context.bot_data.get('db_path')
    manager = DutyShiftManager(db_path)

    # Получить клуб и тип смены из context
    club = context.user_data.get('duty_club')
    shift_type = context.user_data.get('duty_shift_type')

    progress = manager.get_checklist_progress(shift_id, club, shift_type)
    items = progress['items'].get(category, [])

    text = f"📋 *{category}*\n\n"

    if not items:
        text += "Нет пунктов в этой категории\n"
    else:
        for item in items:
            status = "✅" if item['checked'] else "⬜"
            text += f"{status} {item['text']}\n"
            if item.get('description'):
                text += f"   _{item['description']}_\n"
            if item.get('notes'):
                text += f"   💬 {item['notes']}\n"
            text += "\n"

    # Кнопки для каждого пункта
    keyboard = []
    for item in items:
        btn_text = f"{'✅' if item['checked'] else '⬜'} {item['text']}"
        keyboard.append([InlineKeyboardButton(btn_text, callback_data=f"duty_item_{item['id']}")])

    keyboard.append([InlineKeyboardButton("« Назад к категориям", callback_data="duty_checklist")])
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')


async def toggle_duty_item(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Переключить пункт чек-листа"""
    query = update.callback_query
    await query.answer()

    # Извлекаем item_id из callback_data
    item_id = int(query.data.replace("duty_item_", ""))

    shift_id = context.user_data.get('current_duty_shift_id')
    if not shift_id:
        await query.edit_message_text("❌ Смена не найдена")
        return

    db_path = context.bot_data.get('db_path')
    manager = DutyShiftManager(db_path)

    # Переключаем статус
    manager.toggle_checklist_item(shift_id, item_id)

    # Находим категорию и её индекс
    progress = manager.get_checklist_progress(shift_id)
    categories = context.user_data.get('duty_categories', [])

    category = None
    cat_idx = None

    for cat, items in progress['items'].items():
        for item in items:
            if item['id'] == item_id:
                category = cat
                # Находим индекс категории
                if category in categories:
                    cat_idx = categories.index(category)
                break
        if category:
            break

    if cat_idx is not None:
        # Имитируем callback для show_duty_category
        query.data = f"duty_cat_{cat_idx}"
        await show_duty_category(update, context)


async def start_handover_notes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начать ввод заметок при передаче смены"""
    query = update.callback_query
    await query.answer()

    text = "📝 *Передача смены*\n\n"
    text += "Напишите заметки для следующего дежурного:\n"
    text += "• Что требует особого внимания\n"
    text += "• Какие задачи остались невыполненными\n"
    text += "• Что админ обещал сделать\n"
    text += "• Любая другая важная информация\n\n"
    text += "Или отправьте /cancel для отмены"

    await query.edit_message_text(text, parse_mode='Markdown')

    return DUTY_ENTER_HANDOVER_NOTES


async def receive_handover_notes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получить и сохранить заметки при передаче смены"""
    notes = update.message.text

    shift_id = context.user_data.get('current_duty_shift_id')
    if not shift_id:
        await update.message.reply_text("❌ Смена не найдена")
        return ConversationHandler.END

    db_path = context.bot_data.get('db_path')
    manager = DutyShiftManager(db_path)

    if manager.save_handover_notes(shift_id, notes):
        await update.message.reply_text("✅ Заметки сохранены!")
        # Показываем меню смены снова
        await show_duty_shift_menu(update, context)
    else:
        await update.message.reply_text("❌ Ошибка при сохранении заметок")

    return ConversationHandler.END


async def cancel_handover(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отменить ввод заметок"""
    await update.message.reply_text("❌ Отменено")
    await show_duty_shift_menu(update, context)
    return ConversationHandler.END


def create_duty_shift_handlers():
    """Создать обработчики для смен дежурных"""

    # ConversationHandler для заметок при передаче
    handover_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(start_handover_notes, pattern="^duty_handover$")],
        states={
            DUTY_ENTER_HANDOVER_NOTES: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_handover_notes)
            ]
        },
        fallbacks=[
            CommandHandler('cancel', cancel_handover)
        ]
    )

    # CallbackQueryHandler для остальных действий
    callback_handler = CallbackQueryHandler(
        handle_duty_callbacks,
        pattern="^(duty_|ctrl_schedule)"
    )

    return [handover_conv, callback_handler]


async def handle_duty_callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик всех callback от смен дежурных"""
    query = update.callback_query
    data = query.data

    if data == "duty_shift_menu":
        await show_duty_shift_menu(update, context)

    elif data == "duty_checklist":
        await show_duty_checklist(update, context)

    elif data == "ctrl_schedule":
        await show_controller_schedule(update, context)

    elif data.startswith("duty_club_"):
        await show_duty_checklist_categories(update, context)

    elif data.startswith("duty_cat_"):
        await show_duty_category(update, context)

    elif data.startswith("duty_item_"):
        await toggle_duty_item(update, context)
