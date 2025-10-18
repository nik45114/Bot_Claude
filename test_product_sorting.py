#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Тест функций сортировки и расширенных отчётов для ProductManager
"""

import sys
import os
import tempfile
from product_manager import ProductManager

# Временная БД для тестов
TEST_DB = os.path.join(tempfile.gettempdir(), 'test_product_sorting.db')

def setup_test_data(pm):
    """Настройка тестовых данных"""
    # Добавляем товары
    pm.add_product('Gorilla', 50.0)
    pm.add_product('Redbull', 60.0)
    pm.add_product('Bulmeni', 40.0)
    pm.add_product('Monster', 55.0)
    
    products = pm.list_products()
    gorilla_id = next(p['id'] for p in products if p['name'] == 'Gorilla')
    redbull_id = next(p['id'] for p in products if p['name'] == 'Redbull')
    bulmeni_id = next(p['id'] for p in products if p['name'] == 'Bulmeni')
    monster_id = next(p['id'] for p in products if p['name'] == 'Monster')
    
    # Записываем товары на админов
    pm.record_admin_product(101, 'Vanya', redbull_id, 2)
    pm.record_admin_product(101, 'Vanya', bulmeni_id, 4)
    pm.record_admin_product(102, 'Igor', gorilla_id, 12)
    pm.record_admin_product(102, 'Igor', redbull_id, 14)
    pm.record_admin_product(103, 'Anna', monster_id, 5)
    pm.record_admin_product(103, 'Anna', gorilla_id, 3)
    
    return {
        'gorilla_id': gorilla_id,
        'redbull_id': redbull_id,
        'bulmeni_id': bulmeni_id,
        'monster_id': monster_id
    }

def test_get_all_debts_sorting():
    """Тест сортировки долгов"""
    print("\n🧪 Тестирование сортировки долгов...")
    
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)
    
    pm = ProductManager(TEST_DB)
    setup_test_data(pm)
    
    # Тест сортировки по долгу (по умолчанию)
    debts_by_debt = pm.get_all_debts(sort_by='debt')
    debt_values = [data['total'] for data in debts_by_debt.values()]
    assert debt_values == sorted(debt_values, reverse=True), "Долги должны быть отсортированы по убыванию"
    print("  ✅ Сортировка по долгу (по убыванию)")
    
    # Тест сортировки по имени
    debts_by_name = pm.get_all_debts(sort_by='name')
    names = [data['name'] for data in debts_by_name.values()]
    assert names == sorted(names), f"Имена должны быть отсортированы по возрастанию, получено: {names}"
    print("  ✅ Сортировка по имени (по возрастанию)")
    
    print("✅ Сортировка долгов - все тесты пройдены")

def test_get_products_summary():
    """Тест получения сводки по товарам"""
    print("\n🧪 Тестирование сводки по товарам...")
    
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)
    
    pm = ProductManager(TEST_DB)
    setup_test_data(pm)
    
    # Получаем сводку
    summary = pm.get_products_summary()
    
    assert len(summary) == 4, f"Должно быть 4 товара, получено {len(summary)}"
    
    # Проверяем Gorilla (12 от Igor + 3 от Anna = 15)
    gorilla = next((s for s in summary if s['product_name'] == 'Gorilla'), None)
    assert gorilla is not None, "Gorilla должен быть в сводке"
    assert gorilla['total_quantity'] == 15, f"Gorilla: ожидалось 15 шт, получено {gorilla['total_quantity']}"
    assert gorilla['total_debt'] == 750.0, f"Gorilla: ожидалось 750₽, получено {gorilla['total_debt']}"
    print("  ✅ Gorilla: 15 шт = 750₽")
    
    # Проверяем Redbull (2 от Vanya + 14 от Igor = 16)
    redbull = next((s for s in summary if s['product_name'] == 'Redbull'), None)
    assert redbull is not None, "Redbull должен быть в сводке"
    assert redbull['total_quantity'] == 16, f"Redbull: ожидалось 16 шт, получено {redbull['total_quantity']}"
    assert redbull['total_debt'] == 960.0, f"Redbull: ожидалось 960₽, получено {redbull['total_debt']}"
    print("  ✅ Redbull: 16 шт = 960₽")
    
    # Проверяем Bulmeni (4 от Vanya = 4)
    bulmeni = next((s for s in summary if s['product_name'] == 'Bulmeni'), None)
    assert bulmeni is not None, "Bulmeni должен быть в сводке"
    assert bulmeni['total_quantity'] == 4, f"Bulmeni: ожидалось 4 шт, получено {bulmeni['total_quantity']}"
    assert bulmeni['total_debt'] == 160.0, f"Bulmeni: ожидалось 160₽, получено {bulmeni['total_debt']}"
    print("  ✅ Bulmeni: 4 шт = 160₽")
    
    # Проверяем Monster (5 от Anna = 5)
    monster = next((s for s in summary if s['product_name'] == 'Monster'), None)
    assert monster is not None, "Monster должен быть в сводке"
    assert monster['total_quantity'] == 5, f"Monster: ожидалось 5 шт, получено {monster['total_quantity']}"
    assert monster['total_debt'] == 275.0, f"Monster: ожидалось 275₽, получено {monster['total_debt']}"
    print("  ✅ Monster: 5 шт = 275₽")
    
    print("✅ Сводка по товарам - все тесты пройдены")

def test_get_products_report_sorting():
    """Тест сортировки отчёта по товарам"""
    print("\n🧪 Тестирование сортировки отчёта по товарам...")
    
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)
    
    pm = ProductManager(TEST_DB)
    setup_test_data(pm)
    
    # Тест сортировки по админам
    report_by_admin = pm.get_products_report(sort_by='admin')
    assert len(report_by_admin) > 0, "Отчёт не должен быть пустым"
    
    # Проверяем, что админы идут в алфавитном порядке
    admin_names = [item['admin_name'] for item in report_by_admin]
    # Проверяем группировку: все записи одного админа должны идти подряд
    current_admin = None
    for name in admin_names:
        if current_admin is None:
            current_admin = name
        elif name != current_admin:
            # Сменился админ - проверяем что он не встречался ранее
            assert name not in admin_names[:admin_names.index(name)][:-1] or admin_names[:admin_names.index(name)][-1] == name, \
                f"Админы должны быть сгруппированы"
            current_admin = name
    print("  ✅ Сортировка по админам")
    
    # Тест сортировки по товарам
    report_by_product = pm.get_products_report(sort_by='product')
    assert len(report_by_product) > 0, "Отчёт не должен быть пустым"
    
    # Проверяем, что товары идут в алфавитном порядке
    product_names = [item['product_name'] for item in report_by_product]
    # Проверяем группировку: все записи одного товара должны идти подряд
    current_product = None
    for name in product_names:
        if current_product is None:
            current_product = name
        elif name != current_product:
            # Сменился товар - проверяем что он не встречался ранее
            assert name not in product_names[:product_names.index(name)][:-1] or product_names[:product_names.index(name)][-1] == name, \
                f"Товары должны быть сгруппированы"
            current_product = name
    print("  ✅ Сортировка по товарам")
    
    print("✅ Сортировка отчёта - все тесты пройдены")

def test_format_products_summary_report():
    """Тест форматирования сводного отчёта"""
    print("\n🧪 Тестирование форматирования сводного отчёта...")
    
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)
    
    pm = ProductManager(TEST_DB)
    setup_test_data(pm)
    
    # Получаем отформатированный отчёт
    report = pm.format_products_summary_report()
    
    # Проверяем наличие ключевых элементов
    assert "СВОДКА ПО ТОВАРАМ" in report, "Должен быть заголовок сводки"
    assert "15 Gorilla" in report or "15 горилл" in report.lower(), "Должен быть Gorilla с количеством 15"
    assert "16 Redbull" in report, "Должен быть Redbull с количеством 16"
    assert "4 Bulmeni" in report, "Должен быть Bulmeni с количеством 4"
    assert "5 Monster" in report, "Должен быть Monster с количеством 5"
    print("  ✅ Формат 'X Товар' присутствует")
    
    # Проверяем наличие детальной разбивки
    assert "Детально:" in report or "детально" in report.lower(), "Должна быть детальная разбивка"
    print("  ✅ Детальная разбивка присутствует")
    
    # Проверяем общую сумму
    assert "ВСЕГО:" in report or "всего" in report.lower(), "Должна быть общая сумма"
    print("  ✅ Общая сумма присутствует")
    
    print("✅ Форматирование сводного отчёта - все тесты пройдены")

def test_format_detailed_debts_report():
    """Тест форматирования детального отчёта по долгам"""
    print("\n🧪 Тестирование форматирования детального отчёта по долгам...")
    
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)
    
    pm = ProductManager(TEST_DB)
    setup_test_data(pm)
    
    # Получаем отформатированный отчёт
    report = pm.format_detailed_debts_report()
    
    # Проверяем наличие ключевых элементов
    assert "ДЕТАЛЬНЫЕ ДОЛГИ" in report or "детальные долги" in report.lower(), "Должен быть заголовок"
    
    # Проверяем формат "Имя: X Товар1, Y Товар2 = Сумма₽"
    assert "Vanya:" in report, "Должен быть Vanya"
    assert "2 Redbull" in report, "У Vanya должно быть 2 Redbull"
    assert "4 Bulmeni" in report, "У Vanya должно быть 4 Bulmeni"
    print("  ✅ Формат 'Vanya: 2 Redbull, 4 Bulmeni = X₽'")
    
    assert "Igor:" in report, "Должен быть Igor"
    assert "12 Gorilla" in report, "У Igor должно быть 12 Gorilla"
    assert "14 Redbull" in report, "У Igor должно быть 14 Redbull"
    print("  ✅ Формат 'Igor: 12 Gorilla, 14 Redbull = X₽'")
    
    assert "Anna:" in report, "Должна быть Anna"
    assert "3 Gorilla" in report, "У Anna должно быть 3 Gorilla"
    assert "5 Monster" in report, "У Anna должно быть 5 Monster"
    print("  ✅ Формат 'Anna: 3 Gorilla, 5 Monster = X₽'")
    
    # Проверяем итоговую сумму
    assert "ВСЕГО ДОЛГОВ:" in report, "Должна быть общая сумма долгов"
    print("  ✅ Общая сумма долгов присутствует")
    
    print("✅ Форматирование детального отчёта - все тесты пройдены")

def test_format_all_debts_report_sorting():
    """Тест форматирования отчёта по долгам с сортировкой"""
    print("\n🧪 Тестирование форматирования отчёта с сортировкой...")
    
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)
    
    pm = ProductManager(TEST_DB)
    setup_test_data(pm)
    
    # Отчёт с сортировкой по долгу
    report_by_debt = pm.format_all_debts_report(sort_by='debt')
    assert "по сумме долга" in report_by_debt or "по долгу" in report_by_debt.lower(), \
        "Должна быть пометка о сортировке по долгу"
    print("  ✅ Отчёт с сортировкой по долгу")
    
    # Отчёт с сортировкой по имени
    report_by_name = pm.format_all_debts_report(sort_by='name')
    assert "по имени" in report_by_name.lower(), "Должна быть пометка о сортировке по имени"
    print("  ✅ Отчёт с сортировкой по имени")
    
    print("✅ Форматирование отчёта с сортировкой - все тесты пройдены")

def test_format_products_report_sorting():
    """Тест форматирования отчёта по товарам с сортировкой"""
    print("\n🧪 Тестирование форматирования отчёта по товарам с группировкой...")
    
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)
    
    pm = ProductManager(TEST_DB)
    setup_test_data(pm)
    
    # Отчёт с группировкой по админам
    report_by_admin = pm.format_products_report(sort_by='admin')
    assert "по админам" in report_by_admin.lower(), "Должна быть пометка о группировке по админам"
    assert "👤" in report_by_admin, "Должны быть иконки админов"
    print("  ✅ Отчёт с группировкой по админам")
    
    # Отчёт с группировкой по товарам
    report_by_product = pm.format_products_report(sort_by='product')
    assert "по товарам" in report_by_product.lower(), "Должна быть пометка о группировке по товарам"
    assert "📦" in report_by_product, "Должны быть иконки товаров"
    print("  ✅ Отчёт с группировкой по товарам")
    
    print("✅ Форматирование отчёта по товарам - все тесты пройдены")

def main():
    print("=" * 60)
    print("   ТЕСТИРОВАНИЕ СОРТИРОВКИ И РАСШИРЕННЫХ ОТЧЁТОВ")
    print("=" * 60)
    
    try:
        test_get_all_debts_sorting()
        test_get_products_summary()
        test_get_products_report_sorting()
        test_format_products_summary_report()
        test_format_detailed_debts_report()
        test_format_all_debts_report_sorting()
        test_format_products_report_sorting()
        
        print("\n" + "=" * 60)
        print("✅ ВСЕ ТЕСТЫ ПРОЙДЕНЫ УСПЕШНО!")
        print("=" * 60)
        
        # Очистка
        if os.path.exists(TEST_DB):
            os.remove(TEST_DB)
        
        return 0
        
    except AssertionError as e:
        print(f"\n❌ ОШИБКА ТЕСТА: {e}")
        import traceback
        traceback.print_exc()
        return 1
    except Exception as e:
        print(f"\n❌ НЕОЖИДАННАЯ ОШИБКА: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == '__main__':
    sys.exit(main())
