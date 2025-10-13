#!/usr/bin/env python3
"""
Скрипт миграции базы данных Club Assistant Bot
Добавляет новые колонки в существующую БД
"""

import sqlite3
import sys

DB_PATH = 'knowledge.db'

def migrate():
    print("🔄 Миграция базы данных...")
    print(f"📁 Файл: {DB_PATH}\n")
    
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Добавляем новые колонки в knowledge
        migrations = [
            ("tags", "ALTER TABLE knowledge ADD COLUMN tags TEXT DEFAULT ''"),
            ("source", "ALTER TABLE knowledge ADD COLUMN source TEXT DEFAULT ''"),
            ("added_by", "ALTER TABLE knowledge ADD COLUMN added_by INTEGER"),
            ("version", "ALTER TABLE knowledge ADD COLUMN version INTEGER DEFAULT 1"),
            ("is_current", "ALTER TABLE knowledge ADD COLUMN is_current BOOLEAN DEFAULT 1"),
        ]
        
        for col_name, sql in migrations:
            try:
                cursor.execute(sql)
                print(f"✅ Добавлена колонка: {col_name}")
            except sqlite3.OperationalError as e:
                if "duplicate column" in str(e).lower():
                    print(f"⚠️  Колонка {col_name} уже существует")
                else:
                    print(f"❌ Ошибка при добавлении {col_name}: {e}")
        
        # Создаём индекс
        try:
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_current ON knowledge(is_current)')
            print("✅ Создан индекс: idx_current")
        except Exception as e:
            print(f"⚠️  Индекс idx_current: {e}")
        
        # Создаём таблицу admins
        try:
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS admins (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    full_name TEXT,
                    added_by INTEGER,
                    can_teach BOOLEAN DEFAULT 1,
                    can_import BOOLEAN DEFAULT 0,
                    can_manage_admins BOOLEAN DEFAULT 0,
                    is_active BOOLEAN DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            print("✅ Создана таблица: admins")
        except Exception as e:
            print(f"⚠️  Таблица admins: {e}")
        
        # Создаём таблицу admin_credentials
        try:
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS admin_credentials (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    service TEXT NOT NULL,
                    login TEXT,
                    password TEXT,
                    notes TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES admins(user_id)
                )
            ''')
            print("✅ Создана таблица: admin_credentials")
        except Exception as e:
            print(f"⚠️  Таблица admin_credentials: {e}")
        
        # Создаём таблицу health_checks
        try:
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS health_checks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    check_type TEXT,
                    status TEXT,
                    details TEXT,
                    checked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            print("✅ Создана таблица: health_checks")
        except Exception as e:
            print(f"⚠️  Таблица health_checks: {e}")
        
        conn.commit()
        conn.close()
        
        print("\n🎉 Миграция завершена успешно!")
        print("\nТеперь можно запускать бота:")
        print("  systemctl start club_assistant")
        return 0
        
    except Exception as e:
        print(f"\n❌ Критическая ошибка: {e}")
        return 1

if __name__ == '__main__':
    sys.exit(migrate())
