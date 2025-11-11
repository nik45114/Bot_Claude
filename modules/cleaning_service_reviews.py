"""
Модуль отзывов об уборщице (Чек-лист #2)
Только для ночной смены (evening)
Оценка 1-5 звезд + текстовый отзыв + фото (опционально)
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

# States
REVIEW_RATING, REVIEW_TEXT, REVIEW_PHOTO = range(3)


class CleaningServiceReviewManager:
    """Менеджер отзывов об уборщице"""

    def __init__(self, db_path: str = 'club_assistant.db'):
        self.db_path = db_path

    def add_review(self, shift_id: int, club: str, reviewer_admin_id: int,
                   rating: int, review_text: Optional[str] = None,
                   photo_file_id: Optional[str] = None) -> bool:
        """Добавить отзыв об уборщице"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("""
                INSERT INTO cleaning_service_reviews
                (shift_id, club, reviewer_admin_id, rating, review_text, photo_file_id)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (shift_id, club, reviewer_admin_id, rating, review_text, photo_file_id))

            conn.commit()
            conn.close()
            logger.info(f"Added cleaning service review for shift {shift_id}")
            return True

        except Exception as e:
            logger.error(f"Error adding cleaning service review: {e}")
            return False

    def get_reviews(self, club: Optional[str] = None, limit: int = 50) -> List[Dict]:
        """Получить отзывы с фильтром по клубу"""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            if club:
                cursor.execute("""
                    SELECT csr.*, a.full_name as reviewer_name
                    FROM cleaning_service_reviews csr
                    LEFT JOIN admins a ON csr.reviewer_admin_id = a.user_id
                    WHERE csr.club = ?
                    ORDER BY csr.created_at DESC
                    LIMIT ?
                """, (club, limit))
            else:
                cursor.execute("""
                    SELECT csr.*, a.full_name as reviewer_name
                    FROM cleaning_service_reviews csr
                    LEFT JOIN admins a ON csr.reviewer_admin_id = a.user_id
                    ORDER BY csr.created_at DESC
                    LIMIT ?
                """, (limit,))

            rows = cursor.fetchall()
            conn.close()

            return [dict(row) for row in rows]

        except Exception as e:
            logger.error(f"Error getting reviews: {e}")
            return []

    def get_average_rating(self, club: str, days: int = 30) -> Optional[float]:
        """Получить средний рейтинг за период"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cutoff_date = datetime.now(MSK) - timedelta(days=days)

            cursor.execute("""
                SELECT AVG(rating) FROM cleaning_service_reviews
                WHERE club = ? AND created_at >= ?
            """, (club, cutoff_date))

            result = cursor.fetchone()[0]
            conn.close()
            return round(result, 1) if result else None

        except Exception as e:
            logger.error(f"Error getting average rating: {e}")
            return None


# ===== TELEGRAM HANDLERS =====

async def start_cleaning_review(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начать отзыв об уборщице"""
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id

    # Проверяем активную смену
    shift_manager = context.bot_data.get('shift_manager')
    if not shift_manager:
        await query.edit_message_text("❌ Модуль смен недоступен")
        return ConversationHandler.END

    active_shift = shift_manager.get_active_shift(user_id)
    if not active_shift:
        await query.edit_message_text("❌ У вас нет активной смены")
        return ConversationHandler.END

    # Проверяем что это ночная смена
    if active_shift.get('shift_type') != 'evening':
        await query.edit_message_text("❌ Оценка уборщицы доступна только для ночной смены")
        return ConversationHandler.END

    # Сохраняем данные
    context.user_data['review_shift_id'] = active_shift['id']
    context.user_data['review_club'] = active_shift['club']

    text = "🧹 *Оценка работы уборщицы*\n\n"
    text += f"🏢 Клуб: {active_shift['club'].upper()}\n\n"
    text += "Оцените качество уборки:"

    keyboard = [
        [InlineKeyboardButton("⭐️⭐️⭐️⭐️⭐️ (5)", callback_data="review_rating_5")],
        [InlineKeyboardButton("⭐️⭐️⭐️⭐️ (4)", callback_data="review_rating_4")],
        [InlineKeyboardButton("⭐️⭐️⭐️ (3)", callback_data="review_rating_3")],
        [InlineKeyboardButton("⭐️⭐️ (2)", callback_data="review_rating_2")],
        [InlineKeyboardButton("⭐️ (1)", callback_data="review_rating_1")],
        [InlineKeyboardButton("« Отмена", callback_data="review_cancel")]
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')

    return REVIEW_RATING


async def review_rating_response(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработать оценку"""
    query = update.callback_query
    await query.answer()

    if query.data == "review_cancel":
        await query.edit_message_text("❌ Отзыв отменен")
        context.user_data.clear()
        return ConversationHandler.END

    rating = int(query.data.split('_')[-1])
    context.user_data['review_rating'] = rating

    text = f"⭐️ *Оценка: {rating}/5*\n\n"
    text += "Хотите добавить текстовый отзыв?\n\n"
    text += "Отправьте текст или нажмите /skip чтобы пропустить"

    await query.edit_message_text(text, parse_mode='Markdown')
    return REVIEW_TEXT


async def review_text_response(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получить текстовый отзыв"""
    review_text = None
    if update.message and update.message.text and update.message.text != '/skip':
        review_text = update.message.text

    context.user_data['review_text'] = review_text

    text = "📸 *Фото*\n\n"
    text += "Хотите добавить фото?\n\n"
    text += "Отправьте фото или нажмите /skip чтобы пропустить"

    await update.message.reply_text(text, parse_mode='Markdown')
    return REVIEW_PHOTO


async def review_photo_response(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получить фото или пропустить"""
    photo_file_id = None

    if update.message.photo:
        photo_file_id = update.message.photo[-1].file_id
        context.user_data['review_photo'] = photo_file_id

    # Сохраняем отзыв
    return await save_review(update, context)


async def save_review(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Сохранить отзыв в БД"""
    shift_id = context.user_data.get('review_shift_id')
    club = context.user_data.get('review_club')
    rating = context.user_data.get('review_rating')
    review_text = context.user_data.get('review_text')
    photo_file_id = context.user_data.get('review_photo')

    user_id = update.effective_user.id

    db_path = context.bot_data.get('db_path', 'club_assistant.db')
    manager = CleaningServiceReviewManager(db_path)

    success = manager.add_review(
        shift_id=shift_id,
        club=club,
        reviewer_admin_id=user_id,
        rating=rating,
        review_text=review_text,
        photo_file_id=photo_file_id
    )

    if success:
        stars = "⭐️" * rating
        text = f"✅ *Отзыв сохранен!*\n\n{stars}\n\nСпасибо за обратную связь!"
        await update.message.reply_text(text, parse_mode='Markdown')
    else:
        await update.message.reply_text("❌ Ошибка сохранения отзыва")

    context.user_data.clear()
    return ConversationHandler.END


async def cancel_review(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отменить отзыв"""
    await update.message.reply_text("❌ Отзыв отменен")
    context.user_data.clear()
    return ConversationHandler.END


async def show_reviews_stats(update: Update, context: ContextTypes.DEFAULT_TYPE, club: Optional[str] = None):
    """Показать статистику отзывов"""
    query = update.callback_query
    if query:
        await query.answer()

    db_path = context.bot_data.get('db_path', 'club_assistant.db')
    manager = CleaningServiceReviewManager(db_path)

    reviews = manager.get_reviews(club=club, limit=20)
    avg_rating = manager.get_average_rating(club, days=30) if club else None

    if club:
        text = f"🧹 *Отзывы об уборщице - {club.upper()}*\n\n"
        if avg_rating:
            text += f"📊 Средняя оценка (30 дней): {avg_rating}/5\n\n"
    else:
        text = "🧹 *Отзывы об уборщице - Все клубы*\n\n"

    if not reviews:
        text += "Пока нет отзывов"
    else:
        for review in reviews:
            reviewer = review.get('reviewer_name') or 'Неизвестно'
            date = review.get('created_at', '')[:10] if review.get('created_at') else ''
            stars = "⭐️" * review.get('rating', 0)

            text += f"{stars} - {reviewer} ({date})\n"
            if review.get('review_text'):
                text += f"💬 {review['review_text'][:100]}\n"
            if review.get('photo_file_id'):
                text += "📸 Есть фото\n"
            text += "\n"

    keyboard = []
    if not club:
        keyboard.append([
            InlineKeyboardButton("🏪 Рио", callback_data="reviews_rio"),
            InlineKeyboardButton("🏢 Север", callback_data="reviews_sever")
        ])

    keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data="owner_panel")])

    reply_markup = InlineKeyboardMarkup(keyboard)

    if query:
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
    else:
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='Markdown')


def create_cleaning_review_handlers():
    """Создать обработчики для отзывов об уборщице"""
    from telegram.ext import CallbackQueryHandler, MessageHandler, CommandHandler, filters

    conv_handler = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(start_cleaning_review, pattern="^review_start$")
        ],
        states={
            REVIEW_RATING: [
                CallbackQueryHandler(review_rating_response, pattern="^review_rating_|review_cancel$")
            ],
            REVIEW_TEXT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, review_text_response),
                CommandHandler('skip', review_text_response)
            ],
            REVIEW_PHOTO: [
                MessageHandler(filters.PHOTO, review_photo_response),
                CommandHandler('skip', lambda u, c: save_review(u, c))
            ]
        },
        fallbacks=[
            CommandHandler('cancel', cancel_review),
            CallbackQueryHandler(cancel_review, pattern="^review_cancel$")
        ]
    )

    stats_handler = CallbackQueryHandler(
        lambda u, c: show_reviews_stats(u, c, club=None),
        pattern="^reviews_all$"
    )

    stats_rio_handler = CallbackQueryHandler(
        lambda u, c: show_reviews_stats(u, c, club='rio'),
        pattern="^reviews_rio$"
    )

    stats_sever_handler = CallbackQueryHandler(
        lambda u, c: show_reviews_stats(u, c, club='sever'),
        pattern="^reviews_sever$"
    )

    # Обработчик для кнопки "Назад" - делегируем в owner_panel
    async def handle_back_to_owner(update: Update, context: ContextTypes.DEFAULT_TYPE):
        from modules.owner_panel import show_owner_panel
        await show_owner_panel(update, context)

    back_handler = CallbackQueryHandler(
        handle_back_to_owner,
        pattern="^owner_panel$"
    )

    return [conv_handler, stats_handler, stats_rio_handler, stats_sever_handler, back_handler]
