#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Simplified Bot Test - Упрощенная версия бота для тестирования
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

def test_basic_imports():
    """Тестирование базовых импортов"""
    try:
        from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
        from telegram.ext import ContextTypes, ConversationHandler, CommandHandler, CallbackQueryHandler, MessageHandler, filters
        print("OK: Telegram Bot API импортирован успешно")
        return True
    except ImportError as e:
        print(f"Ошибка импорта Telegram Bot API: {e}")
        return False

def test_enhanced_modules():
    """Тестирование улучшенных модулей"""
    try:
        from modules.enhanced_admin_shift_integration import register_enhanced_admin_shift_management
        print("OK: Улучшенные модули импортированы успешно")
        return True
    except ImportError as e:
        print(f"Ошибка импорта улучшенных модулей: {e}")
        return False

def test_database():
    """Тестирование базы данных"""
    try:
        import sqlite3
        db_path = "knowledge.db"
        
        if not os.path.exists(db_path):
            print(f"Ошибка: База данных {db_path} не найдена")
            return False
        
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Проверяем существование таблиц
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()
        
        print(f"OK: База данных подключена. Таблицы: {[t[0] for t in tables]}")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"Ошибка работы с базой данных: {e}")
        return False

def test_config():
    """Тестирование конфигурации"""
    try:
        config_path = "config.json"
        
        if not os.path.exists(config_path):
            print(f"Ошибка: Файл конфигурации {config_path} не найден")
            return False
        
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        required_keys = ['telegram_token', 'openai_api_key']
        missing_keys = [key for key in required_keys if key not in config]
        
        if missing_keys:
            print(f"Ошибка: Отсутствуют ключи в конфигурации: {missing_keys}")
            return False
        
        print("OK: Конфигурация загружена успешно")
        return True
        
    except Exception as e:
        print(f"Ошибка загрузки конфигурации: {e}")
        return False

def main():
    """Основная функция тестирования"""
    print(f"Тестирование Club Assistant Bot v{VERSION}")
    print("=" * 50)
    
    tests = [
        ("Базовые импорты", test_basic_imports),
        ("Улучшенные модули", test_enhanced_modules),
        ("База данных", test_database),
        ("Конфигурация", test_config)
    ]
    
    results = []
    
    for test_name, test_func in tests:
        print(f"\nТестирование: {test_name}")
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"Ошибка в тесте {test_name}: {e}")
            results.append((test_name, False))
    
    print("\n" + "=" * 50)
    print("Результаты тестирования:")
    
    passed = 0
    for test_name, result in results:
        status = "ПРОЙДЕН" if result else "ПРОВАЛЕН"
        print(f"{test_name}: {status}")
        if result:
            passed += 1
    
    print(f"\nПройдено тестов: {passed}/{len(results)}")
    
    if passed == len(results):
        print("\nВсе тесты пройдены! Бот готов к работе.")
        return True
    else:
        print(f"\nПровалено тестов: {len(results) - passed}")
        print("Необходимо исправить ошибки перед запуском бота.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
