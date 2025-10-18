#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Миграция базы данных: добавление никнеймов админов и индексов
Добавляет admin_nickname колонку и индексы для оптимизации запросов
"""

import sqlite3
import sys
import logging

DB_PATH = 'knowledge.db'

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

def migrate():
    """Выполняет миграцию базы данных"""
    logger.info("🔄 Миграция базы данных...")
    logger.info(f"📁 Файл: {DB_PATH}\n")
    
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # 1. Добавляем колонку admin_nickname в таблицу admins
        logger.info("📝 Добавление колонки admin_nickname...")
        try:
            cursor.execute('ALTER TABLE admins ADD COLUMN admin_nickname TEXT')
            logger.info("✅ Колонка admin_nickname добавлена")
        except sqlite3.OperationalError as e:
            if "duplicate column" in str(e).lower():
                logger.info("⚠️  Колонка admin_nickname уже существует")
            else:
                logger.error(f"❌ Ошибка при добавлении admin_nickname: {e}")
        
        # 2. Создаём индексы для оптимизации запросов
        logger.info("\n📊 Создание индексов для оптимизации...")
        
        indexes = [
            # Индекс для быстрого поиска админов по активности
            ("idx_admins_active", "CREATE INDEX IF NOT EXISTS idx_admins_active ON admins(is_active)"),
            
            # Индекс для быстрого поиска товаров админа
            ("idx_admin_products_admin", "CREATE INDEX IF NOT EXISTS idx_admin_products_admin ON admin_products(admin_id, settled)"),
            
            # Индекс для быстрого поиска по товарам
            ("idx_admin_products_product", "CREATE INDEX IF NOT EXISTS idx_admin_products_product ON admin_products(product_id, settled)"),
            
            # Индекс для быстрого поиска по дате взятия
            ("idx_admin_products_date", "CREATE INDEX IF NOT EXISTS idx_admin_products_date ON admin_products(taken_at)"),
            
            # Индекс для агрегации по админу и товару
            ("idx_admin_products_group", "CREATE INDEX IF NOT EXISTS idx_admin_products_group ON admin_products(admin_id, product_name, settled)"),
        ]
        
        for idx_name, sql in indexes:
            try:
                cursor.execute(sql)
                logger.info(f"✅ Создан индекс: {idx_name}")
            except Exception as e:
                logger.error(f"❌ Ошибка при создании индекса {idx_name}: {e}")
        
        # 3. Проверяем созданные индексы
        logger.info("\n🔍 Проверка созданных индексов...")
        cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND name LIKE 'idx_%'")
        indexes_created = cursor.fetchall()
        
        if indexes_created:
            logger.info("✅ Найдено индексов:")
            for idx in indexes_created:
                logger.info(f"   • {idx[0]}")
        
        conn.commit()
        conn.close()
        
        logger.info("\n🎉 Миграция завершена успешно!")
        logger.info("\n📋 Что добавлено:")
        logger.info("   • Колонка admin_nickname в таблице admins")
        logger.info("   • Индексы для оптимизации запросов по товарам и админам")
        
        return 0
        
    except Exception as e:
        logger.error(f"\n❌ Критическая ошибка: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return 1

if __name__ == '__main__':
    sys.exit(migrate())
