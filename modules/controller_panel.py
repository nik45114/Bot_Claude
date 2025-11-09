"""
Модуль панели контролёра (заглушка)
Автор: Club Assistant Bot
Дата: 2025-11-09
"""

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CallbackQueryHandler

logger = logging.getLogger(__name__)


async def show_controller_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать панель контролёра"""
    query = update.callback_query
    if query:
        await query.answer()

    text = """👁 **Панель большого брата**

Функционал временно недоступен.
Модуль находится в разработке."""

    keyboard = [
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


async def handle_controller_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик callback для панели контролёра"""
    query = update.callback_query
    await query.answer()

    if query.data == "controller_panel":
        await show_controller_panel(update, context)
        return

    # Кнопка назад
    if query.data == "main_menu":
        # Возвращаем в главное меню - обработается в основном обработчике
        return


def create_controller_callback_handler():
    """Создать обработчик для callback кнопок контролёра"""
    return CallbackQueryHandler(
        handle_controller_callback,
        pattern="^(controller_panel)$"
    )
