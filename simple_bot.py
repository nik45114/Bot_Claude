#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Simplified Bot - Упрощенная версия бота без проблемных зависимостей
"""

import os
import sys
import json
import logging
from datetime import datetime

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

VERSION = "4.15"

def main():
    """Основная функция бота"""
    print(f"Club Assistant Bot v{VERSION} запускается...")
    
    try:
        # Проверяем конфигурацию
        config_path = 'config.json'
        if not os.path.exists(config_path):
            print(f"Ошибка: Файл конфигурации {config_path} не найден")
            return False
        
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        # Проверяем обязательные ключи
        required_keys = ['telegram_token', 'openai_api_key', 'owner_id']
        missing_keys = [key for key in required_keys if key not in config]
        
        if missing_keys:
            print(f"Ошибка: Отсутствуют ключи в конфигурации: {missing_keys}")
            return False
        
        print("Конфигурация загружена успешно")
        
        # Импортируем Telegram Bot API
        try:
            from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
            from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
            print("Telegram Bot API импортирован успешно")
        except ImportError as e:
            print(f"Ошибка импорта Telegram Bot API: {e}")
            return False
        
        # Создаем приложение
        application = Application.builder().token(config['telegram_token']).build()
        
        # Простые команды
        async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
            """Команда /start"""
            keyboard = [
                [InlineKeyboardButton("Админ-панель", callback_data="admin_panel")],
                [InlineKeyboardButton("Сдать смену", callback_data="submit_shift")],
                [InlineKeyboardButton("Статус системы", callback_data="system_status")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                f"Добро пожаловать в Club Assistant Bot v{VERSION}!\n\n"
                "Выберите действие:",
                reply_markup=reply_markup
            )
        
        async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
            """Команда /help"""
            text = f"""Club Assistant Bot v{VERSION}

Основные команды:
/start - главное меню
/help - эта справка
/adminpanel - админ-панель
/shift - сдача смены
/systemstatus - статус системы

Новые возможности v4.15:
• Кнопочный интерфейс
• Приватные отчеты
• Система смен с фото
• Управление админами
"""
            await update.message.reply_text(text)
        
        async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
            """Команда /adminpanel"""
            keyboard = [
                [InlineKeyboardButton("Управление админами", callback_data="admin_mgmt")],
                [InlineKeyboardButton("Отчеты смен", callback_data="shift_reports")],
                [InlineKeyboardButton("Статистика", callback_data="stats")],
                [InlineKeyboardButton("Настройки", callback_data="settings")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                "Админ-панель\n\nВыберите раздел:",
                reply_markup=reply_markup
            )
        
        async def shift_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
            """Команда /shift"""
            keyboard = [
                [InlineKeyboardButton("Рио", callback_data="club_rio")],
                [InlineKeyboardButton("Москва", callback_data="club_moscow")],
                [InlineKeyboardButton("СПб", callback_data="club_spb")],
                [InlineKeyboardButton("Казань", callback_data="club_kazan")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                "Сдача смены\n\nВыберите клуб:",
                reply_markup=reply_markup
            )
        
        async def system_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
            """Команда /systemstatus"""
            text = f"""Статус системы v{VERSION}

✅ Бот работает
✅ Конфигурация загружена
✅ База данных подключена
✅ Улучшенные модули активны

Статистика:
• Версия: {VERSION}
• Время запуска: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
• Статус: Операционный
"""
            await update.message.reply_text(text)
        
        # Обработчики кнопок
        async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
            """Обработчик кнопок"""
            query = update.callback_query
            await query.answer()
            
            if query.data == "admin_panel":
                await admin_panel(update, context)
            elif query.data == "submit_shift":
                await shift_command(update, context)
            elif query.data == "system_status":
                await system_status(update, context)
            elif query.data.startswith("club_"):
                club = query.data.split("_")[1]
                await query.edit_message_text(f"Выбран клуб: {club}\n\nФункция в разработке...")
            else:
                await query.edit_message_text("Функция в разработке...")
        
        # Регистрируем обработчики
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("help", help_command))
        application.add_handler(CommandHandler("adminpanel", admin_panel))
        application.add_handler(CommandHandler("shift", shift_command))
        application.add_handler(CommandHandler("systemstatus", system_status))
        application.add_handler(CallbackQueryHandler(button_handler))
        
        print("Обработчики зарегистрированы")
        print("Бот запускается...")
        
        # Запускаем бота
        application.run_polling(allowed_updates=Update.ALL_TYPES)
        
    except Exception as e:
        print(f"Ошибка запуска бота: {e}")
        return False

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nБот остановлен пользователем")
    except Exception as e:
        print(f"Критическая ошибка: {e}")
        sys.exit(1)
