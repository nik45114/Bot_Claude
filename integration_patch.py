#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Bot Integration Patch - Патч для интеграции системы управления админами и сменами
"""

import os
import sys
import re
from pathlib import Path

def apply_integration_patch(bot_file_path: str):
    """Применение патча интеграции к основному файлу бота"""
    
    try:
        # Читаем файл бота
        with open(bot_file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 1. Обновляем версию
        content = re.sub(r'VERSION = "[^"]*"', 'VERSION = "4.14"', content)
        
        # 2. Добавляем импорты новых модулей
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
    # Новые модули управления админами и сменами
    from modules.admin_shift_integration import register_admin_shift_management
    from modules.manual_update import ManualUpdateSystem, ManualUpdateCommands
except ImportError as e:
    print(f"❌ Не найдены модули v4.14: {e}")
    sys.exit(1)'''
        
        # Заменяем секцию импортов
        content = re.sub(
            r'try:\s*from embeddings import.*?except ImportError as e:.*?sys\.exit\(1\)',
            import_section,
            content,
            flags=re.DOTALL
        )
        
        # 3. Добавляем инициализацию новых систем в __init__
        init_addition = '''
        # Инициализация системы управления админами и сменами
        self.admin_shift_integration = None
        self.manual_update_system = ManualUpdateSystem()
        self.manual_update_commands = ManualUpdateCommands(self.manual_update_system)'''
        
        # Находим место в __init__ для добавления
        init_pattern = r'(def __init__\(self, config: dict\):.*?self\.config = config)'
        content = re.sub(
            init_pattern,
            r'\1' + init_addition,
            content,
            flags=re.DOTALL
        )
        
        # 4. Добавляем регистрацию новых команд в run()
        registration_addition = '''
        # Регистрация системы управления админами и сменами
        try:
            self.admin_shift_integration = register_admin_shift_management(app, self.config, DB_PATH)
            logger.info("✅ Admin & Shift Management system registered")
        except Exception as e:
            logger.error(f"❌ Error registering Admin & Shift Management: {e}")
        
        # Регистрация команд ручного обновления
        app.add_handler(CommandHandler("manualupdate", self.manual_update_commands.cmd_manual_update))
        app.add_handler(CommandHandler("updatelog", self.manual_update_commands.cmd_update_log))
        logger.info("✅ Manual update commands registered")'''
        
        # Находим место в run() для добавления
        run_pattern = r'(# Регистрация команд.*?logger\.info\("✅ Bot v.*?готов"\))'
        content = re.sub(
            run_pattern,
            r'\1' + registration_addition,
            content,
            flags=re.DOTALL
        )
        
        # 5. Добавляем новые команды в cmd_help
        help_addition = '''
👥 АДМИНИСТРАТОРЫ (v4.14):
/adminmgmt - управление администраторами
/shiftmgmt - контроль смен с фото и OCR
/systemstatus - статус системы

🔄 ОБНОВЛЕНИЯ (v4.14):
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
        content = re.sub(r'Club Assistant Bot v[\d.]+', 'Club Assistant Bot v4.14', content)
        content = re.sub(r'Инициализация v[\d.]+', 'Инициализация v4.14', content)
        content = re.sub(r'Бот v[\d.]+ готов', 'Бот v4.14 готов', content)
        
        # 7. Добавляем обработчик фото для смен
        photo_handler_addition = '''
    async def handle_shift_photo(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка фото смены с OCR"""
        if not self._should_respond(update, context):
            return
        
        # Проверяем, что это фото смены
        if context.user_data.get('waiting_for_shift_photo'):
            if self.admin_shift_integration:
                await self.admin_shift_integration.handle_shift_with_photo(update, context)
            else:
                await update.message.reply_text("❌ Система управления сменами недоступна")
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
            r'app.add_handler(MessageHandler(filters.PHOTO, self.handle_shift_photo))',
            content
        )
        
        # Сохраняем обновленный файл
        with open(bot_file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        print("✅ Integration patch applied successfully")
        return True
        
    except Exception as e:
        print(f"❌ Error applying integration patch: {e}")
        return False

def create_migration_script():
    """Создание скрипта миграции базы данных"""
    
    migration_script = '''#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Database Migration Script - Скрипт миграции для системы управления админами и сменами
"""

import sqlite3
import os
import sys
from pathlib import Path

def run_migration(db_path: str):
    """Выполнение миграции базы данных"""
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Читаем файл миграции
        migration_file = Path(__file__).parent / "migrations" / "admin_shift_management_001_init.sql"
        
        if not migration_file.exists():
            print(f"❌ Migration file not found: {migration_file}")
            return False
        
        with open(migration_file, 'r', encoding='utf-8') as f:
            migration_sql = f.read()
        
        # Выполняем миграцию
        cursor.executescript(migration_sql)
        conn.commit()
        conn.close()
        
        print("✅ Database migration completed successfully")
        return True
        
    except Exception as e:
        print(f"❌ Error running migration: {e}")
        return False

if __name__ == "__main__":
    db_path = sys.argv[1] if len(sys.argv) > 1 else "knowledge.db"
    run_migration(db_path)
'''
    
    with open("migrate_admin_shift.py", "w", encoding="utf-8") as f:
        f.write(migration_script)
    
    print("✅ Migration script created: migrate_admin_shift.py")

def create_setup_script():
    """Создание скрипта установки зависимостей"""
    
    setup_script = '''#!/bin/bash
# Скрипт установки зависимостей для системы управления админами и сменами

echo "🔧 Установка зависимостей для Admin & Shift Management..."

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
echo "1. Запустите миграцию: python3 migrate_admin_shift.py"
echo "2. Перезапустите бота: systemctl restart club_assistant"
echo "3. Проверьте статус: /systemstatus"
'''
    
    with open("setup_admin_shift.sh", "w", encoding="utf-8") as f:
        f.write(setup_script)
    
    # Делаем скрипт исполняемым
    os.chmod("setup_admin_shift.sh", 0o755)
    
    print("✅ Setup script created: setup_admin_shift.sh")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 integration_patch.py <bot_file_path>")
        sys.exit(1)
    
    bot_file_path = sys.argv[1]
    
    if not os.path.exists(bot_file_path):
        print(f"❌ Bot file not found: {bot_file_path}")
        sys.exit(1)
    
    # Применяем патч
    if apply_integration_patch(bot_file_path):
        print("✅ Integration patch applied successfully")
        
        # Создаем дополнительные скрипты
        create_migration_script()
        create_setup_script()
        
        print("")
        print("🎉 Интеграция завершена!")
        print("")
        print("📝 Следующие шаги:")
        print("1. Установите зависимости: ./setup_admin_shift.sh")
        print("2. Запустите миграцию: python3 migrate_admin_shift.py")
        print("3. Перезапустите бота: systemctl restart club_assistant")
        print("4. Проверьте новые команды: /adminmgmt, /shiftmgmt, /systemstatus")
        
    else:
        print("❌ Failed to apply integration patch")
        sys.exit(1)
