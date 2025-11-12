"""
Модуль рейтинга уборки админа (Чек-лист #1)
Админ оценивает чистоту клуба после предыдущего админа
Срок заполнения: 30 минут после открытия смены
"""

import sqlite3
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, List
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler

logger = logging.getLogger(__name__)

# Moscow timezone (UTC+3)
MSK = timezone(timedelta(hours=3))

# States for ConversationHandler
RATING_BAR, RATING_BAR_PHOTO, RATING_HALL, RATING_HALL_PHOTO, RATING_NOTES = range(5)


class CleaningRatingManager:
    """Менеджер рейтинга уборки админов"""

    def __init__(self, db_path: str = 'club_assistant.db'):
        self.db_path = db_path

    def create_rating(self, shift_id: int, club: str, rated_by_admin_id: int,
                     previous_admin_id: Optional[int] = None) -> bool:
        """Создать запись для рейтинга уборки"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Проверяем, нет ли уже рейтинга для этой смены
            cursor.execute("""
                SELECT id FROM shift_cleaning_rating
                WHERE shift_id = ?
            """, (shift_id,))

            if cursor.fetchone():
                logger.info(f"Rating already exists for shift {shift_id}")
                conn.close()
                return False

            # Создаем пустую запись
            cursor.execute("""
                INSERT INTO shift_cleaning_rating
                (shift_id, club, rated_by_admin_id, previous_admin_id, bar_cleaned, hall_cleaned)
                VALUES (?, ?, ?, ?, 1, 1)
            """, (shift_id, club, rated_by_admin_id, previous_admin_id))

            conn.commit()
            conn.close()
            logger.info(f"Created cleaning rating for shift {shift_id}")
            return True

        except Exception as e:
            logger.error(f"Error creating cleaning rating: {e}")
            return False

    def update_rating(self, shift_id: int, bar_cleaned: bool, hall_cleaned: bool,
                     bar_photo: Optional[str] = None, hall_photo: Optional[str] = None,
                     notes: Optional[str] = None) -> bool:
        """Обновить рейтинг уборки"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("""
                UPDATE shift_cleaning_rating
                SET bar_cleaned = ?,
                    hall_cleaned = ?,
                    bar_photo_file_id = ?,
                    hall_photo_file_id = ?,
                    notes = ?,
                    rated_at = ?
                WHERE shift_id = ?
            """, (bar_cleaned, hall_cleaned, bar_photo, hall_photo, notes,
                  datetime.now(MSK), shift_id))

            conn.commit()
            conn.close()
            logger.info(f"Updated cleaning rating for shift {shift_id}")
            return True

        except Exception as e:
            logger.error(f"Error updating cleaning rating: {e}")
            return False

    def get_rating(self, shift_id: int) -> Optional[Dict]:
        """Получить рейтинг для смены"""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute("""
                SELECT * FROM shift_cleaning_rating
                WHERE shift_id = ?
            """, (shift_id,))

            row = cursor.fetchone()
            conn.close()

            if row:
                return dict(row)
            return None

        except Exception as e:
            logger.error(f"Error getting cleaning rating: {e}")
            return None

    def get_admin_bad_ratings_count(self, admin_id: int, days: int = 30) -> int:
        """Получить количество плохих оценок админа за период"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cutoff_date = datetime.now(MSK) - timedelta(days=days)

            cursor.execute("""
                SELECT COUNT(*) FROM shift_cleaning_rating
                WHERE previous_admin_id = ?
                AND (bar_cleaned = 0 OR hall_cleaned = 0)
                AND rated_at >= ?
            """, (admin_id, cutoff_date))

            count = cursor.fetchone()[0]
            conn.close()
            return count

        except Exception as e:
            logger.error(f"Error getting bad ratings count: {e}")
            return 0

    def get_admin_total_bad_ratings(self, admin_id: int) -> int:
        """Получить общее количество плохих оценок админа"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("""
                SELECT COUNT(*) FROM shift_cleaning_rating
                WHERE previous_admin_id = ?
                AND (bar_cleaned = 0 OR hall_cleaned = 0)
            """, (admin_id,))

            count = cursor.fetchone()[0]
            conn.close()
            return count

        except Exception as e:
            logger.error(f"Error getting total bad ratings: {e}")
            return 0

    def get_all_ratings(self, club: Optional[str] = None, limit: int = 50) -> List[Dict]:
        """Получить все рейтинги с фильтром по клубу"""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            if club:
                cursor.execute("""
                    SELECT scr.*, a1.full_name as rater_name, a2.full_name as previous_admin_name
                    FROM shift_cleaning_rating scr
                    LEFT JOIN admins a1 ON scr.rated_by_admin_id = a1.user_id
                    LEFT JOIN admins a2 ON scr.previous_admin_id = a2.user_id
                    WHERE scr.club = ?
                    ORDER BY scr.rated_at DESC
                    LIMIT ?
                """, (club, limit))
            else:
                cursor.execute("""
                    SELECT scr.*, a1.full_name as rater_name, a2.full_name as previous_admin_name
                    FROM shift_cleaning_rating scr
                    LEFT JOIN admins a1 ON scr.rated_by_admin_id = a1.user_id
                    LEFT JOIN admins a2 ON scr.previous_admin_id = a2.user_id
                    ORDER BY scr.rated_at DESC
                    LIMIT ?
                """, (limit,))

            rows = cursor.fetchall()
            conn.close()

            return [dict(row) for row in rows]

        except Exception as e:
            logger.error(f"Error getting all ratings: {e}")
            return []


# ===== TELEGRAM HANDLERS =====

async def start_cleaning_rating(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начать оценку чистоты клуба"""
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id

    # Получаем активную смену
    shift_manager = context.bot_data.get('shift_manager')
    if not shift_manager:
        await query.edit_message_text("❌ Модуль смен недоступен")
        return ConversationHandler.END

    active_shift = shift_manager.get_active_shift(user_id)
    if not active_shift:
        await query.edit_message_text("❌ У вас нет активной смены")
        return ConversationHandler.END

    # Сохраняем данные в context
    context.user_data['rating_shift_id'] = active_shift['id']
    context.user_data['rating_club'] = active_shift['club']

    text = "⭐ *Оценка чистоты клуба*\n\n"
    text += f"🏢 Клуб: {active_shift['club'].upper()}\n\n"
    text += "Выставлен и убран ли бар?"

    keyboard = [
        [InlineKeyboardButton("✅ Да, всё чисто", callback_data="rating_bar_yes")],
        [InlineKeyboardButton("❌ Нет, не убран", callback_data="rating_bar_no")],
        [InlineKeyboardButton("« Отмена", callback_data="rating_cancel")]
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')

    return RATING_BAR


async def rating_bar_response(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработать ответ про бар"""
    query = update.callback_query
    await query.answer()

    if query.data == "rating_cancel":
        await query.edit_message_text("❌ Оценка отменена")
        context.user_data.clear()
        return ConversationHandler.END

    bar_cleaned = query.data == "rating_bar_yes"
    context.user_data['bar_cleaned'] = bar_cleaned

    if not bar_cleaned:
        # Предлагаем загрузить фото (опционально)
        text = "📸 *Загрузите фото грязного бара* (опционально)\n\n"
        text += "Отправьте фото, подтверждающее что бар не убран,\n"
        text += "или нажмите кнопку ниже чтобы пропустить."

        keyboard = [[InlineKeyboardButton("⏭️ Пропустить фото", callback_data="rating_skip_bar_photo")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
        return RATING_BAR_PHOTO
    else:
        # Переходим к следующему вопросу
        return await ask_hall_cleaned(update, context)


async def rating_bar_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получить фото бара или пропустить"""
    # Если это callback (кнопка "Пропустить")
    if update.callback_query:
        query = update.callback_query
        await query.answer()
        if query.data == "rating_skip_bar_photo":
            context.user_data['bar_photo'] = None
            return await ask_hall_cleaned(update, context)

    # Если это фото
    if update.message and update.message.photo:
        # Сохраняем file_id самого большого фото
        photo_file_id = update.message.photo[-1].file_id
        context.user_data['bar_photo'] = photo_file_id

        # УДАЛЯЕМ сообщение админа с фото
        try:
            await update.message.delete()
        except Exception as e:
            logger.warning(f"Could not delete admin photo message: {e}")

        # Переходим к следующему вопросу
        return await ask_hall_cleaned(update, context)

    # Если ни то ни другое
    await update.message.reply_text("❌ Пожалуйста, отправьте фото или нажмите 'Пропустить'")
    return RATING_BAR_PHOTO


async def ask_hall_cleaned(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Спросить про зал"""
    text = "⭐ *Оценка чистоты клуба*\n\n"
    text += "Убран ли зал?"

    keyboard = [
        [InlineKeyboardButton("✅ Да, всё чисто", callback_data="rating_hall_yes")],
        [InlineKeyboardButton("❌ Нет, не убран", callback_data="rating_hall_no")]
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)

    if update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
    else:
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='Markdown')

    return RATING_HALL


async def rating_hall_response(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработать ответ про зал"""
    query = update.callback_query
    await query.answer()

    hall_cleaned = query.data == "rating_hall_yes"
    context.user_data['hall_cleaned'] = hall_cleaned

    if not hall_cleaned:
        # Предлагаем загрузить фото (опционально)
        text = "📸 *Загрузите фото грязного зала* (опционально)\n\n"
        text += "Отправьте фото, подтверждающее что зал не убран,\n"
        text += "или нажмите кнопку ниже чтобы пропустить."

        keyboard = [[InlineKeyboardButton("⏭️ Пропустить фото", callback_data="rating_skip_hall_photo")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
        return RATING_HALL_PHOTO
    else:
        # Переходим к заметкам
        return await ask_notes(update, context)


async def rating_hall_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получить фото зала или пропустить"""
    # Если это callback (кнопка "Пропустить")
    if update.callback_query:
        query = update.callback_query
        await query.answer()
        if query.data == "rating_skip_hall_photo":
            context.user_data['hall_photo'] = None
            return await ask_notes(update, context)

    # Если это фото
    if update.message and update.message.photo:
        # Сохраняем file_id самого большого фото
        photo_file_id = update.message.photo[-1].file_id
        context.user_data['hall_photo'] = photo_file_id

        # УДАЛЯЕМ сообщение админа с фото
        try:
            await update.message.delete()
        except Exception as e:
            logger.warning(f"Could not delete admin photo message: {e}")

        # Переходим к заметкам
        return await ask_notes(update, context)

    # Если ни то ни другое
    await update.message.reply_text("❌ Пожалуйста, отправьте фото или нажмите 'Пропустить'")
    return RATING_HALL_PHOTO


async def ask_notes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Спросить дополнительные заметки"""
    text = "📝 *Дополнительные заметки*\n\n"
    text += "Хотите добавить комментарий? (опционально)\n\n"
    text += "Отправьте текст или нажмите /skip чтобы пропустить"

    if update.callback_query:
        await update.callback_query.edit_message_text(text, parse_mode='Markdown')
    else:
        await update.message.reply_text(text, parse_mode='Markdown')

    return RATING_NOTES


async def rating_notes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получить заметки"""
    notes = None
    if update.message and update.message.text and update.message.text != '/skip':
        notes = update.message.text

        # УДАЛЯЕМ сообщение админа с заметками
        try:
            await update.message.delete()
        except Exception as e:
            logger.warning(f"Could not delete admin notes message: {e}")

    context.user_data['notes'] = notes

    # Сохраняем рейтинг
    return await save_rating(update, context)


async def save_rating(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Сохранить рейтинг в БД"""
    shift_id = context.user_data.get('rating_shift_id')
    bar_cleaned = context.user_data.get('bar_cleaned', True)
    hall_cleaned = context.user_data.get('hall_cleaned', True)
    bar_photo = context.user_data.get('bar_photo')
    hall_photo = context.user_data.get('hall_photo')
    notes = context.user_data.get('notes')

    db_path = context.bot_data.get('db_path', 'club_assistant.db')
    manager = CleaningRatingManager(db_path)

    success = manager.update_rating(
        shift_id=shift_id,
        bar_cleaned=bar_cleaned,
        hall_cleaned=hall_cleaned,
        bar_photo=bar_photo,
        hall_photo=hall_photo,
        notes=notes
    )

    if success:
        # НЕ показываем админу детали оценки - только подтверждение сохранения
        text = "✅ *Рейтинг уборки сохранен!*\n\n"
        text += "Спасибо за оценку. Информация передана руководству."

        if update.callback_query:
            await update.callback_query.edit_message_text(text, parse_mode='Markdown')
        else:
            await update.message.reply_text(text, parse_mode='Markdown')
    else:
        error_text = "❌ Ошибка сохранения оценки"
        if update.callback_query:
            await update.callback_query.edit_message_text(error_text)
        else:
            await update.message.reply_text(error_text)

    context.user_data.clear()
    return ConversationHandler.END


async def cancel_rating(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отменить оценку"""
    await update.message.reply_text("❌ Оценка отменена")
    context.user_data.clear()
    return ConversationHandler.END


async def show_ratings_stats(update: Update, context: ContextTypes.DEFAULT_TYPE, club: Optional[str] = None):
    """Показать статистику рейтингов"""
    query = update.callback_query
    if query:
        await query.answer()

    db_path = context.bot_data.get('db_path', 'club_assistant.db')
    manager = CleaningRatingManager(db_path)

    ratings = manager.get_all_ratings(club=club, limit=20)

    if club:
        text = f"⭐ *Рейтинг уборки - {club.upper()}*\n\n"
    else:
        text = "⭐ *Рейтинг уборки - Все клубы*\n\n"

    if not ratings:
        text += "Пока нет оценок"
    else:
        for rating in ratings:
            prev_admin = rating.get('previous_admin_name') or 'Неизвестно'
            date = rating.get('rated_at', '')[:10] if rating.get('rated_at') else ''

            bar_status = "✅" if rating.get('bar_cleaned') else "❌"
            hall_status = "✅" if rating.get('hall_cleaned') else "❌"

            text += f"👤 {prev_admin} ({date})\n"
            text += f"   Бар: {bar_status} | Зал: {hall_status}\n"

            if rating.get('notes'):
                text += f"   💬 {rating['notes'][:50]}\n"
            text += "\n"

    keyboard = []
    if not club:
        keyboard.append([
            InlineKeyboardButton("🏪 Рио", callback_data="rating_stats_rio"),
            InlineKeyboardButton("🏢 Север", callback_data="rating_stats_sever")
        ])

    keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data="owner_panel")])

    reply_markup = InlineKeyboardMarkup(keyboard)

    if query:
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
    else:
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='Markdown')


def create_cleaning_rating_handlers():
    """Создать обработчики для рейтинга уборки"""
    from telegram.ext import CallbackQueryHandler, MessageHandler, CommandHandler, filters

    conv_handler = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(start_cleaning_rating, pattern="^rating_start$")
        ],
        states={
            RATING_BAR: [
                CallbackQueryHandler(rating_bar_response, pattern="^rating_bar_")
            ],
            RATING_BAR_PHOTO: [
                CallbackQueryHandler(rating_bar_photo, pattern="^rating_skip_bar_photo$"),
                MessageHandler(filters.PHOTO, rating_bar_photo)
            ],
            RATING_HALL: [
                CallbackQueryHandler(rating_hall_response, pattern="^rating_hall_")
            ],
            RATING_HALL_PHOTO: [
                CallbackQueryHandler(rating_hall_photo, pattern="^rating_skip_hall_photo$"),
                MessageHandler(filters.PHOTO, rating_hall_photo)
            ],
            RATING_NOTES: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, rating_notes),
                CommandHandler('skip', rating_notes)
            ]
        },
        fallbacks=[
            CommandHandler('cancel', cancel_rating),
            CallbackQueryHandler(cancel_rating, pattern="^rating_cancel$")
        ]
    )

    # Обработчик статистики
    stats_handler = CallbackQueryHandler(
        lambda u, c: show_ratings_stats(u, c, club=None),
        pattern="^rating_stats$"
    )

    stats_rio_handler = CallbackQueryHandler(
        lambda u, c: show_ratings_stats(u, c, club='rio'),
        pattern="^rating_stats_rio$"
    )

    stats_sever_handler = CallbackQueryHandler(
        lambda u, c: show_ratings_stats(u, c, club='sever'),
        pattern="^rating_stats_sever$"
    )

    return [conv_handler, stats_handler, stats_rio_handler, stats_sever_handler]
