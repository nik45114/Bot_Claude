#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Simple Bot Fix - Простое исправление bot.py
"""

import re
import os

def fix_bot_py():
    """Простое исправление bot.py"""
    
    print("Исправляю bot.py...")
    
    try:
        # Читаем файл
        with open("bot.py", "r", encoding="utf-8") as f:
            content = f.read()
        
        print(f"Размер файла: {len(content)} символов")
        
        # Обновляем версию
        content = re.sub(r'VERSION = "[^"]*"', 'VERSION = "4.15"', content)
        
        # Добавляем импорт улучшенных модулей
        import_pattern = r'(from modules\.admins import register_admins)'
        replacement = r'\1\n    # Улучшенные модули управления админами и сменами\n    from modules.enhanced_admin_shift_integration import register_enhanced_admin_shift_management'
        
        content = re.sub(import_pattern, replacement, content)
        
        # Добавляем инициализацию улучшенной системы
        init_pattern = r'(self\.config = config)'
        replacement = r'\1\n        \n        # Инициализация улучшенной системы управления админами и сменами\n        self.enhanced_admin_shift_integration = None'
        
        content = re.sub(init_pattern, replacement, content)
        
        # Добавляем регистрацию улучшенных команд
        registration_pattern = r'(logger\.info\("✅ Bot v.*?готов"\))'
        replacement = r'\1\n        \n        # Регистрация улучшенной системы управления админами и сменами\n        try:\n            self.enhanced_admin_shift_integration = register_enhanced_admin_shift_management(\n                app, self.config, DB_PATH, self.owner_id\n            )\n            logger.info("✅ Enhanced Admin & Shift Management system registered")\n        except Exception as e:\n            logger.error(f"❌ Error registering Enhanced Admin & Shift Management: {e}")'
        
        content = re.sub(registration_pattern, replacement, content)
        
        # Добавляем команду админ-панели
        help_pattern = r'(/listadmins - список админов)'
        replacement = r'\1\n\n👥 АДМИНИСТРАТОРЫ (v4.15):\n/adminpanel - админ-панель с кнопочным интерфейсом\n/shift - сдача смены с фото и OCR\n/systemstatus - статус системы'
        
        content = re.sub(help_pattern, replacement, content)
        
        # Сохраняем файл
        with open("bot.py", "w", encoding="utf-8") as f:
            f.write(content)
        
        print("bot.py исправлен успешно")
        return True
        
    except Exception as e:
        print(f"Ошибка исправления bot.py: {e}")
        return False

def create_migration_script():
    """Создание скрипта миграции"""
    
    print("Создаю скрипт миграции...")
    
    migration_content = '''#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Enhanced Database Migration Script
"""

import sqlite3
import os
import sys

def run_enhanced_migration(db_path: str):
    """Выполнение миграции базы данных для улучшенной системы"""
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Создаем таблицы для улучшенной системы
        cursor.execute("CREATE TABLE IF NOT EXISTS admin_management (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER UNIQUE NOT NULL, username TEXT, full_name TEXT, role TEXT DEFAULT 'staff', permissions TEXT, added_by INTEGER, added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, last_seen TIMESTAMP, is_active BOOLEAN DEFAULT 1, notes TEXT, shift_count INTEGER DEFAULT 0, last_shift_date DATE, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)")
        
        cursor.execute("CREATE TABLE IF NOT EXISTS shift_control (id INTEGER PRIMARY KEY AUTOINCREMENT, admin_id INTEGER NOT NULL, club_name TEXT NOT NULL, shift_date DATE NOT NULL, shift_time TEXT NOT NULL, fact_cash REAL DEFAULT 0, fact_card REAL DEFAULT 0, qr_amount REAL DEFAULT 0, card2_amount REAL DEFAULT 0, safe_cash_end REAL DEFAULT 0, box_cash_end REAL DEFAULT 0, photo_file_id TEXT, photo_path TEXT, ocr_text TEXT, ocr_numbers TEXT, ocr_verified BOOLEAN DEFAULT 0, ocr_confidence REAL DEFAULT 0, status TEXT DEFAULT 'pending', verified_by INTEGER, verified_at TIMESTAMP, verification_notes TEXT, visible_to_owner_only BOOLEAN DEFAULT 1, shared_with_admins TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, FOREIGN KEY (admin_id) REFERENCES admin_management(user_id), FOREIGN KEY (verified_by) REFERENCES admin_management(user_id))")
        
        # Создаем индексы
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_admin_management_user_id ON admin_management(user_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_shift_control_admin ON shift_control(admin_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_shift_control_date ON shift_control(shift_date)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_shift_control_status ON shift_control(status)")
        
        # Синхронизируем существующих админов
        cursor.execute("INSERT OR IGNORE INTO admin_management (user_id, username, full_name, added_by, is_active, created_at) SELECT user_id, username, full_name, added_by, is_active, created_at FROM admins WHERE is_active = 1")
        
        conn.commit()
        conn.close()
        
        print("Enhanced database migration completed successfully")
        return True
        
    except Exception as e:
        print(f"Error running enhanced migration: {e}")
        return False

if __name__ == "__main__":
    db_path = sys.argv[1] if len(sys.argv) > 1 else "knowledge.db"
    run_enhanced_migration(db_path)
'''
    
    with open("migrate_enhanced_admin_shift.py", "w", encoding="utf-8") as f:
        f.write(migration_content)
    
    print("Скрипт миграции создан: migrate_enhanced_admin_shift.py")

def create_setup_script():
    """Создание скрипта установки"""
    
    print("Создаю скрипт установки...")
    
    setup_content = '''#!/bin/bash
# Скрипт установки улучшенной системы управления админами и сменами

echo "Установка улучшенной системы Admin & Shift Management..."

# Установка системных зависимостей
echo "Установка системных пакетов..."
sudo apt update
sudo apt install -y tesseract-ocr tesseract-ocr-rus libtesseract-dev

# Установка Python зависимостей
echo "Установка Python пакетов..."
pip3 install opencv-python>=4.8.0 pytesseract>=0.3.10 Pillow>=10.0.0

# Создание директории для фото
echo "Создание директорий..."
mkdir -p /opt/club_assistant/photos
mkdir -p /opt/club_assistant/backups

# Установка прав
echo "Настройка прав доступа..."
chown -R club_assistant:club_assistant /opt/club_assistant/photos
chown -R club_assistant:club_assistant /opt/club_assistant/backups

echo "Установка завершена!"
echo ""
echo "Следующие шаги:"
echo "1. Запустите миграцию: python3 migrate_enhanced_admin_shift.py"
echo "2. Перезапустите бота: systemctl restart club_assistant"
echo "3. Проверьте админ-панель: /adminpanel"
echo "4. Попробуйте сдать смену: /shift"
'''
    
    with open("setup_enhanced_admin_shift.sh", "w", encoding="utf-8") as f:
        f.write(setup_content)
    
    # Делаем скрипт исполняемым
    os.chmod("setup_enhanced_admin_shift.sh", 0o755)
    
    print("Скрипт установки создан: setup_enhanced_admin_shift.sh")

if __name__ == "__main__":
    print("Простое исправление bot.py")
    print("=" * 40)
    
    # Исправляем bot.py
    if fix_bot_py():
        print("✅ bot.py исправлен")
        
        # Создаем дополнительные скрипты
        create_migration_script()
        create_setup_script()
        
        print("\n" + "=" * 40)
        print("Исправление завершено!")
        print("\nСледующие шаги:")
        print("1. Запустите миграцию: python3 migrate_enhanced_admin_shift.py")
        print("2. Перезапустите бота: systemctl restart club_assistant")
        print("3. Проверьте админ-панель: /adminpanel")
        print("4. Попробуйте сдать смену: /shift")
        
    else:
        print("❌ Ошибка исправления bot.py")
