#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Принудительное исправление базы данных
Удаляет все записи где вопрос начинается с "что делать если"
"""

import sqlite3
import sys

DB_PATH = 'knowledge.db'

def main():
    print("🔍 Проверка базы данных...")
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Ищем все записи где вопрос начинается с "что делать если"
    cursor.execute('''
        SELECT id, question, answer 
        FROM knowledge 
        WHERE question LIKE 'что делать если%'
        AND is_current = 1
        ORDER BY id
        LIMIT 20
    ''')
    
    records = cursor.fetchall()
    
    print(f"\nНайдено записей: {len(records)}")
    print("\nПример записей:\n")
    
    for rec_id, question, answer in records[:5]:
        print(f"ID: {rec_id}")
        print(f"Вопрос: {question[:80]}")
        print(f"Ответ: {answer[:80]}")
        print("-" * 80)
    
    if not records:
        print("✅ Нет проблемных записей")
        conn.close()
        return
    
    # Спрашиваем подтверждение
    print(f"\n⚠️  ВНИМАНИЕ!")
    print(f"Найдено {len(records)} записей где вопрос начинается с 'что делать если'")
    print("Это автогенерированные записи с плохими вопросами.")
    print("\nВарианты:")
    print("1. Удалить все эти записи")
    print("2. Пометить как неактивные (is_current = 0)")
    print("3. Отмена")
    
    choice = input("\nВыбери (1/2/3): ").strip()
    
    if choice == "1":
        # Удаляем
        print("\n🗑️  Удаляю записи...")
        cursor.execute('''
            DELETE FROM knowledge 
            WHERE question LIKE 'что делать если%'
            AND is_current = 1
        ''')
        deleted = cursor.rowcount
        conn.commit()
        print(f"✅ Удалено: {deleted}")
        
    elif choice == "2":
        # Деактивируем
        print("\n🔒 Деактивирую записи...")
        cursor.execute('''
            UPDATE knowledge 
            SET is_current = 0
            WHERE question LIKE 'что делать если%'
            AND is_current = 1
        ''')
        updated = cursor.rowcount
        conn.commit()
        print(f"✅ Деактивировано: {updated}")
        
    else:
        print("❌ Отменено")
    
    conn.close()
    
    # Статистика после
    print("\n📊 Статистика после:")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM knowledge WHERE is_current = 1')
    total = cursor.fetchone()[0]
    print(f"Активных записей: {total}")
    conn.close()


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n❌ Прервано")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
