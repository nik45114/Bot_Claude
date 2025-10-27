#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Enhanced Integration Patch - Патч для интеграции улучшенной системы с кнопочным интерфейсом
"""

import os
import sys
import re
from pathlib import Path

def apply_enhanced_integration_patch(bot_file_path: str):
    """Применение патча улучшенной интеграции к основному файлу бота"""
    
    try:
        # Читаем файл бота
        with open(bot_file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 1. Обновляем версию
        content = re.sub(r'VERSION = "[^"]*"', 'VERSION = "4.15"', content)
        
        # 2. Добавляем импорты улучшенных модулей
        import_section = '''try:
    from embeddings import EmbeddingService
    from vector_store import VectorStore
    from draft_queue import DraftQueue
    from v2ray_manager import V2RayManager
    from v2ray_commands import V2RayCommands
    from club_manager import ClubManager
    from club_commands import ClubCommands, WAITING_REPORT
    from cash_manager import CashManager
    from cash_commands import CashCommands, CASH_SELECT_CLUB, CASH_SELECT_TYPE, CASH_ENTER_AMOUNT, CASH_ENTER_DESCRIPTION, CASH_ENTER_CATEGORY
    from product_manager import ProductManager
    from product_commands import ProductCommands, PRODUCT_ENTER_NAME, PRODUCT_ENTER_PRICE, PRODUCT_SELECT, PRODUCT_ENTER_QUANTITY, PRODUCT_EDIT_PRICE, PRODUCT_SET_NICKNAME
    from issue_manager import IssueManager
    from issue_commands import IssueCommands, ISSUE_SELECT_CLUB, ISSUE_ENTER_DESCRIPTION, ISSUE_EDIT_DESCRIPTION
    from content_generator import ContentGenerator
    from content_commands import ContentCommands
    # from modules.finmon import register_finmon  # Временно отключено - модуль в разработке
    from modules.admins import register_admins
    from modules.backup_commands import register_backup_commands
    # Улучшенные модули управления админами и сменами
    from modules.enhanced_admin_shift_integration import register_enhanced_admin_shift_management
except ImportError as e:
    print(f"❌ Не найдены модули v4.15: {e}")
    sys.exit(1)'''
        
        # Заменяем секцию импортов
        content = re.sub(
            r'try:\s*from embeddings import.*?except ImportError as e:.*?sys\.exit\(1\)',
            import_section,
            content,
            flags=re.DOTALL
        )
        
        # 3. Добавляем инициализацию улучшенных систем в __init__
        init_addition = '''
        # Инициализация улучшенной системы управления админами и сменами
        self.enhanced_admin_shift_integration = None'''
        
        # Находим место в __init__ для добавления
        init_pattern = r'(def __init__\(self, config: dict\):.*?self\.config = config)'
        content = re.sub(
            init_pattern,
            r'\1' + init_addition,
            content,
            flags=re.DOTALL
        )
        
        # 4. Добавляем регистрацию улучшенных команд в run()
        registration_addition = '''
        # Регистрация улучшенной системы управления админами и сменами
        try:
            self.enhanced_admin_shift_integration = register_enhanced_admin_shift_management(
                app, self.config, DB_PATH, self.owner_id
            )
            logger.info("✅ Enhanced Admin & Shift Management system registered")
        except Exception as e:
            logger.error(f"❌ Error registering Enhanced Admin & Shift Management: {e}")'''
        
        # Находим место в run() для добавления
        run_pattern = r'(# Регистрация команд.*?logger\.info\("✅ Bot v.*?готов"\))'
        content = re.sub(
            run_pattern,
            r'\1' + registration_addition,
            content,
            flags=re.DOTALL
        )
        
        # 5. Обновляем cmd_help с новыми командами
        help_addition = '''
👥 АДМИНИСТРАТОРЫ (v4.15):
/adminpanel - админ-панель с кнопочным интерфейсом
/shift - сдача смены с фото и OCR
/systemstatus - статус системы

🔄 ОБНОВЛЕНИЯ (v4.15):
/manualupdate - ручное обновление через бота
/updatelog - лог обновлений'''
        
        # Находим секцию админов в help
        help_pattern = r'(👥 АДМИНИСТРАТОРЫ:.*?/listadmins - список админов)'
        content = re.sub(
            help_pattern,
            r'\1' + help_addition,
            content,
            flags=re.DOTALL
        )
        
        # 6. Обновляем сообщения о версии
        content = re.sub(r'Club Assistant Bot v[\d.]+', 'Club Assistant Bot v4.15', content)
        content = re.sub(r'Инициализация v[\d.]+', 'Инициализация v4.15', content)
        content = re.sub(r'Бот v[\d.]+ готов', 'Бот v4.15 готов', content)
        
        # 7. Добавляем обработчик фото для улучшенной системы смен
        photo_handler_addition = '''
    async def handle_enhanced_shift_photo(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка фото смены в улучшенной системе"""
        if not self._should_respond(update, context):
            return
        
        # Проверяем, что это фото смены в улучшенной системе
        if context.user_data.get('waiting_for_photo') and self.enhanced_admin_shift_integration:
            await self.enhanced_admin_shift_integration.handle_shift_with_photo(update, context)
        else:
            # Обычная обработка фото
            await self.handle_photo(update, context)'''
        
        # Находим место после handle_photo
        photo_pattern = r'(async def handle_photo\(self, update: Update, context: ContextTypes\.DEFAULT_TYPE\):.*?await update\.message\.reply_text\(f"❌ \{e\}"\))'
        content = re.sub(
            photo_pattern,
            r'\1' + photo_handler_addition,
            content,
            flags=re.DOTALL
        )
        
        # 8. Обновляем регистрацию обработчиков фото
        photo_registration_pattern = r'(app\.add_handler\(MessageHandler\(filters\.PHOTO, self\.handle_photo\)\))'
        content = re.sub(
            photo_registration_pattern,
            r'app.add_handler(MessageHandler(filters.PHOTO, self.handle_enhanced_shift_photo))',
            content
        )
        
        # Сохраняем обновленный файл
        with open(bot_file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        print("✅ Enhanced integration patch applied successfully")
        return True
        
    except Exception as e:
        print(f"❌ Error applying enhanced integration patch: {e}")
        return False

def create_enhanced_migration_script():
    """Создание скрипта миграции для улучшенной системы"""
    
    migration_script = '''#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Enhanced Database Migration Script - Скрипт миграции для улучшенной системы
"""

import sqlite3
import os
import sys
from pathlib import Path

def run_enhanced_migration(db_path: str):
    """Выполнение миграции базы данных для улучшенной системы"""
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Создаем таблицы для улучшенной системы
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS admin_management (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER UNIQUE NOT NULL,
                username TEXT,
                full_name TEXT,
                role TEXT DEFAULT 'staff',
                permissions TEXT,
                added_by INTEGER,
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_seen TIMESTAMP,
                is_active BOOLEAN DEFAULT 1,
                notes TEXT,
                shift_count INTEGER DEFAULT 0,
                last_shift_date DATE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS admin_activity (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                admin_id INTEGER NOT NULL,
                action TEXT NOT NULL,
                details TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (admin_id) REFERENCES admin_management(user_id)
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS shift_control (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                admin_id INTEGER NOT NULL,
                club_name TEXT NOT NULL,
                shift_date DATE NOT NULL,
                shift_time TEXT NOT NULL,
                
                -- Данные смены
                fact_cash REAL DEFAULT 0,
                fact_card REAL DEFAULT 0,
                qr_amount REAL DEFAULT 0,
                card2_amount REAL DEFAULT 0,
                safe_cash_end REAL DEFAULT 0,
                box_cash_end REAL DEFAULT 0,
                
                -- Фото и OCR
                photo_file_id TEXT,
                photo_path TEXT,
                ocr_text TEXT,
                ocr_numbers TEXT,
                ocr_verified BOOLEAN DEFAULT 0,
                ocr_confidence REAL DEFAULT 0,
                
                -- Статус и проверка
                status TEXT DEFAULT 'pending',
                verified_by INTEGER,
                verified_at TIMESTAMP,
                verification_notes TEXT,
                
                -- Права доступа
                visible_to_owner_only BOOLEAN DEFAULT 1,
                shared_with_admins TEXT,
                
                -- Метаданные
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                
                FOREIGN KEY (admin_id) REFERENCES admin_management(user_id),
                FOREIGN KEY (verified_by) REFERENCES admin_management(user_id)
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS shift_status_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                shift_id INTEGER NOT NULL,
                old_status TEXT,
                new_status TEXT,
                changed_by INTEGER NOT NULL,
                reason TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (shift_id) REFERENCES shift_control(id),
                FOREIGN KEY (changed_by) REFERENCES admin_management(user_id)
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS shift_submissions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                admin_id INTEGER NOT NULL,
                club_name TEXT NOT NULL,
                shift_date DATE NOT NULL,
                shift_time TEXT NOT NULL,
                
                -- Данные смены
                fact_cash REAL DEFAULT 0,
                fact_card REAL DEFAULT 0,
                qr_amount REAL DEFAULT 0,
                card2_amount REAL DEFAULT 0,
                safe_cash_end REAL DEFAULT 0,
                box_cash_end REAL DEFAULT 0,
                
                -- Фото и OCR
                photo_file_id TEXT,
                photo_path TEXT,
                ocr_text TEXT,
                ocr_numbers TEXT,
                ocr_verified BOOLEAN DEFAULT 0,
                ocr_confidence REAL DEFAULT 0,
                
                -- Статус
                status TEXT DEFAULT 'submitted',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                
                FOREIGN KEY (admin_id) REFERENCES admin_management(user_id)
            )
        ''')
        
        # Создаем индексы
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_admin_management_user_id ON admin_management(user_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_admin_management_role ON admin_management(role)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_admin_management_active ON admin_management(is_active)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_admin_management_updated_at ON admin_management(updated_at DESC)')
        
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_admin_activity_admin_id ON admin_activity(admin_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_admin_activity_timestamp ON admin_activity(timestamp DESC)')
        
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_shift_control_admin ON shift_control(admin_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_shift_control_date ON shift_control(shift_date)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_shift_control_status ON shift_control(status)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_shift_control_club ON shift_control(club_name)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_shift_control_created_at ON shift_control(created_at DESC)')
        
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_shift_status_history_shift_id ON shift_status_history(shift_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_shift_status_history_timestamp ON shift_status_history(timestamp DESC)')
        
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_shift_submissions_admin ON shift_submissions(admin_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_shift_submissions_date ON shift_submissions(shift_date)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_shift_submissions_status ON shift_submissions(status)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_shift_submissions_created_at ON shift_submissions(created_at DESC)')
        
        # Синхронизируем существующих админов
        cursor.execute('''
            INSERT OR IGNORE INTO admin_management (user_id, username, full_name, added_by, is_active, created_at)
            SELECT user_id, username, full_name, added_by, is_active, created_at
            FROM admins 
            WHERE is_active = 1
        ''')
        
        conn.commit()
        conn.close()
        
        print("✅ Enhanced database migration completed successfully")
        return True
        
    except Exception as e:
        print(f"❌ Error running enhanced migration: {e}")
        return False

if __name__ == "__main__":
    db_path = sys.argv[1] if len(sys.argv) > 1 else "knowledge.db"
    run_enhanced_migration(db_path)
'''
    
    with open("migrate_enhanced_admin_shift.py", "w", encoding="utf-8") as f:
        f.write(migration_script)
    
    print("✅ Enhanced migration script created: migrate_enhanced_admin_shift.py")

def create_enhanced_setup_script():
    """Создание скрипта установки для улучшенной системы"""
    
    setup_script = '''#!/bin/bash
# Скрипт установки улучшенной системы управления админами и сменами

echo "🔧 Установка улучшенной системы Admin & Shift Management..."

# Установка системных зависимостей
echo "📦 Установка системных пакетов..."
sudo apt update
sudo apt install -y tesseract-ocr tesseract-ocr-rus libtesseract-dev

# Установка Python зависимостей
echo "🐍 Установка Python пакетов..."
pip3 install opencv-python>=4.8.0 pytesseract>=0.3.10 Pillow>=10.0.0

# Создание директории для фото
echo "📁 Создание директорий..."
mkdir -p /opt/club_assistant/photos
mkdir -p /opt/club_assistant/backups

# Установка прав
echo "🔐 Настройка прав доступа..."
chown -R club_assistant:club_assistant /opt/club_assistant/photos
chown -R club_assistant:club_assistant /opt/club_assistant/backups

echo "✅ Установка завершена!"
echo ""
echo "📝 Следующие шаги:"
echo "1. Запустите миграцию: python3 migrate_enhanced_admin_shift.py"
echo "2. Перезапустите бота: systemctl restart club_assistant"
echo "3. Проверьте админ-панель: /adminpanel"
echo "4. Попробуйте сдать смену: /shift"
'''
    
    with open("setup_enhanced_admin_shift.sh", "w", encoding="utf-8") as f:
        f.write(setup_script)
    
    # Делаем скрипт исполняемым
    os.chmod("setup_enhanced_admin_shift.sh", 0o755)
    
    print("✅ Enhanced setup script created: setup_enhanced_admin_shift.sh")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 enhanced_integration_patch.py <bot_file_path>")
        sys.exit(1)
    
    bot_file_path = sys.argv[1]
    
    if not os.path.exists(bot_file_path):
        print(f"❌ Bot file not found: {bot_file_path}")
        sys.exit(1)
    
    # Применяем патч
    if apply_enhanced_integration_patch(bot_file_path):
        print("✅ Enhanced integration patch applied successfully")
        
        # Создаем дополнительные скрипты
        create_enhanced_migration_script()
        create_enhanced_setup_script()
        
        print("")
        print("🎉 Улучшенная интеграция завершена!")
        print("")
        print("📝 Следующие шаги:")
        print("1. Установите зависимости: ./setup_enhanced_admin_shift.sh")
        print("2. Запустите миграцию: python3 migrate_enhanced_admin_shift.py")
        print("3. Перезапустите бота: systemctl restart club_assistant")
        print("4. Проверьте новые команды: /adminpanel, /shift, /systemstatus")
        print("")
        print("✨ Новые возможности:")
        print("• Кнопочный интерфейс вместо команд")
        print("• Отчеты видны только владельцу")
        print("• Возможность расшарить отчеты админам")
        print("• Удобная работа с отчетами")
        print("• Улучшенная система смен с фото и OCR")
        
    else:
        print("❌ Failed to apply enhanced integration patch")
        sys.exit(1)
