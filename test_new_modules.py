#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Тест новых модулей управления
"""

import sys
import sqlite3
import os
import tempfile

# Временная БД для тестов - используем tempfile для кроссплатформенности
TEST_DB = os.path.join(tempfile.gettempdir(), 'test_bot.db')

def test_cash_manager():
    """Тест финансового менеджера"""
    print("\n🧪 Тестирование CashManager...")
    
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)
    
    from cash_manager import CashManager
    
    cm = CashManager(TEST_DB)
    
    # Тест инициализации
    balances = cm.get_all_balances()
    assert 'rio' in balances, "Клуб 'rio' должен быть инициализирован"
    assert 'michurinskaya' in balances, "Клуб 'michurinskaya' должен быть инициализирован"
    print("  ✅ Инициализация касс")
    
    # Тест добавления прихода
    success = cm.add_movement('rio', 'official', 5000, 'income', 'Тестовый приход', 'test', 123)
    assert success, "Движение должно быть добавлено"
    balance = cm.get_balance('rio', 'official')
    assert balance == 5000, f"Баланс должен быть 5000, получен {balance}"
    print("  ✅ Добавление прихода")
    
    # Тест добавления расхода
    success = cm.add_movement('rio', 'official', 2000, 'expense', 'Тестовый расход', 'salary', 123)
    assert success, "Движение должно быть добавлено"
    balance = cm.get_balance('rio', 'official')
    assert balance == 3000, f"Баланс должен быть 3000, получен {balance}"
    print("  ✅ Добавление расхода")
    
    # Тест получения истории
    movements = cm.get_movements('rio', 'official', limit=10)
    assert len(movements) == 2, f"Должно быть 2 движения, получено {len(movements)}"
    print("  ✅ Получение истории")
    
    # Тест форматирования
    report = cm.format_balance_report()
    assert 'Рио' in report, "В отчёте должен быть клуб Рио"
    assert '3,000' in report or '3000' in report, "В отчёте должен быть баланс 3000"
    print("  ✅ Форматирование отчётов")
    
    print("✅ CashManager - все тесты пройдены")

def test_product_manager():
    """Тест менеджера товаров"""
    print("\n🧪 Тестирование ProductManager...")
    
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)
    
    from product_manager import ProductManager
    
    pm = ProductManager(TEST_DB)
    
    # Тест добавления товара
    success = pm.add_product('Monster Energy', 50.0)
    assert success, "Товар должен быть добавлен"
    print("  ✅ Добавление товара")
    
    # Тест получения товара
    products = pm.list_products()
    assert len(products) == 1, f"Должен быть 1 товар, получено {len(products)}"
    assert products[0]['name'] == 'Monster Energy', "Неверное название товара"
    print("  ✅ Получение списка товаров")
    
    # Тест записи товара на админа
    product_id = products[0]['id']
    success = pm.record_admin_product(123, 'Test Admin', product_id, 5)
    assert success, "Товар должен быть записан на админа"
    print("  ✅ Запись товара на админа")
    
    # Тест получения долга
    debt = pm.get_admin_debt(123)
    assert debt == 250.0, f"Долг должен быть 250.0, получено {debt}"
    print("  ✅ Расчёт долга")
    
    # Тест обнуления долга
    success = pm.clear_admin_debt(123)
    assert success, "Долг должен быть обнулён"
    debt = pm.get_admin_debt(123)
    assert debt == 0.0, f"Долг должен быть 0.0, получено {debt}"
    print("  ✅ Обнуление долга")
    
    print("✅ ProductManager - все тесты пройдены")

def test_issue_manager():
    """Тест менеджера проблем"""
    print("\n🧪 Тестирование IssueManager...")
    
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)
    
    from issue_manager import IssueManager
    
    im = IssueManager(TEST_DB)
    
    # Тест создания проблемы
    issue_id = im.create_issue('rio', 'Тестовая проблема', 123, 'Test User')
    assert issue_id > 0, "Проблема должна быть создана"
    print("  ✅ Создание проблемы")
    
    # Тест получения проблемы
    issue = im.get_issue(issue_id)
    assert issue is not None, "Проблема должна существовать"
    assert issue['description'] == 'Тестовая проблема', "Неверное описание"
    assert issue['status'] == 'active', "Статус должен быть 'active'"
    print("  ✅ Получение проблемы")
    
    # Тест списка проблем
    issues = im.list_issues(club='rio', status='active')
    assert len(issues) == 1, f"Должна быть 1 проблема, получено {len(issues)}"
    print("  ✅ Получение списка проблем")
    
    # Тест решения проблемы
    success = im.resolve_issue(issue_id)
    assert success, "Проблема должна быть решена"
    issue = im.get_issue(issue_id)
    assert issue['status'] == 'resolved', "Статус должен быть 'resolved'"
    print("  ✅ Решение проблемы")
    
    # Тест количества активных
    count = im.get_active_count()
    assert count == 0, f"Активных проблем должно быть 0, получено {count}"
    print("  ✅ Подсчёт активных проблем")
    
    # Тест форматирования
    text = im.format_issue(issue)
    assert 'Проблема #' in text, "В форматировании должен быть ID проблемы"
    print("  ✅ Форматирование проблем")
    
    print("✅ IssueManager - все тесты пройдены")

def test_database_schema():
    """Тест схемы базы данных"""
    print("\n🧪 Тестирование схемы БД...")
    
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)
    
    # Инициализируем все менеджеры
    from cash_manager import CashManager
    from product_manager import ProductManager
    from issue_manager import IssueManager
    
    CashManager(TEST_DB)
    ProductManager(TEST_DB)
    IssueManager(TEST_DB)
    
    # Проверяем наличие всех таблиц
    conn = sqlite3.connect(TEST_DB)
    cursor = conn.cursor()
    
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [row[0] for row in cursor.fetchall()]
    
    required_tables = [
        'cash_movements',
        'cash_balances',
        'products',
        'admin_products',
        'club_issues'
    ]
    
    for table in required_tables:
        assert table in tables, f"Таблица {table} должна существовать"
        print(f"  ✅ Таблица {table} создана")
    
    conn.close()
    
    print("✅ Схема БД - все тесты пройдены")

def main():
    print("=" * 60)
    print("   ТЕСТИРОВАНИЕ НОВЫХ МОДУЛЕЙ")
    print("=" * 60)
    
    try:
        test_database_schema()
        test_cash_manager()
        test_product_manager()
        test_issue_manager()
        
        print("\n" + "=" * 60)
        print("✅ ВСЕ ТЕСТЫ ПРОЙДЕНЫ УСПЕШНО!")
        print("=" * 60)
        
        # Очистка
        if os.path.exists(TEST_DB):
            os.remove(TEST_DB)
        
        return 0
        
    except AssertionError as e:
        print(f"\n❌ ОШИБКА ТЕСТА: {e}")
        return 1
    except Exception as e:
        print(f"\n❌ НЕОЖИДАННАЯ ОШИБКА: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == '__main__':
    sys.exit(main())
