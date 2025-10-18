#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Демонстрация новых функций сортировки и детальных отчётов
"""

import os
import tempfile
from product_manager import ProductManager

# Временная БД для демо
DEMO_DB = os.path.join(tempfile.gettempdir(), 'demo_products.db')

def main():
    print("=" * 70)
    print("   ДЕМОНСТРАЦИЯ НОВЫХ ФУНКЦИЙ УПРАВЛЕНИЯ ТОВАРАМИ")
    print("=" * 70)
    
    # Очищаем старую БД если есть
    if os.path.exists(DEMO_DB):
        os.remove(DEMO_DB)
    
    pm = ProductManager(DEMO_DB)
    
    # Настройка тестовых данных
    print("\n📦 Добавляем товары в систему...")
    pm.add_product('Gorilla', 50.0)
    pm.add_product('Redbull', 60.0)
    pm.add_product('Bulmeni', 40.0)
    pm.add_product('Monster', 55.0)
    print("   ✅ Добавлено 4 товара")
    
    products = pm.list_products()
    gorilla_id = next(p['id'] for p in products if p['name'] == 'Gorilla')
    redbull_id = next(p['id'] for p in products if p['name'] == 'Redbull')
    bulmeni_id = next(p['id'] for p in products if p['name'] == 'Bulmeni')
    monster_id = next(p['id'] for p in products if p['name'] == 'Monster')
    
    print("\n👥 Записываем товары на админов...")
    pm.record_admin_product(101, 'Vanya', redbull_id, 2)
    pm.record_admin_product(101, 'Vanya', bulmeni_id, 4)
    pm.record_admin_product(102, 'Igor', gorilla_id, 12)
    pm.record_admin_product(102, 'Igor', redbull_id, 14)
    pm.record_admin_product(103, 'Anna', monster_id, 5)
    pm.record_admin_product(103, 'Anna', gorilla_id, 3)
    print("   ✅ Товары записаны")
    
    # Демонстрация 1: Сортировка долгов по имени
    print("\n" + "=" * 70)
    print("ДЕМО 1: Сортировка долгов по имени админа")
    print("=" * 70)
    print(pm.format_all_debts_report(sort_by='name'))
    
    # Демонстрация 2: Сортировка долгов по сумме
    print("\n" + "=" * 70)
    print("ДЕМО 2: Сортировка долгов по сумме долга")
    print("=" * 70)
    print(pm.format_all_debts_report(sort_by='debt'))
    
    # Демонстрация 3: Сводка по товарам (12 Gorilla, 14 Redbull)
    print("\n" + "=" * 70)
    print("ДЕМО 3: Сводка по товарам за период")
    print("=" * 70)
    print(pm.format_products_summary_report())
    
    # Демонстрация 4: Детальный отчёт (Vanya: 2 Redbull, 4 Bulmeni)
    print("\n" + "=" * 70)
    print("ДЕМО 4: Детальный отчёт с разбивкой по админам")
    print("=" * 70)
    print(pm.format_detailed_debts_report())
    
    # Демонстрация 5: Отчёт с группировкой по товарам
    print("\n" + "=" * 70)
    print("ДЕМО 5: Отчёт с группировкой по товарам")
    print("=" * 70)
    print(pm.format_products_report(sort_by='product'))
    
    # Демонстрация 6: Отчёт с группировкой по админам
    print("\n" + "=" * 70)
    print("ДЕМО 6: Отчёт с группировкой по админам")
    print("=" * 70)
    print(pm.format_products_report(sort_by='admin'))
    
    # Очистка
    if os.path.exists(DEMO_DB):
        os.remove(DEMO_DB)
    
    print("\n" + "=" * 70)
    print("   ✅ ДЕМОНСТРАЦИЯ ЗАВЕРШЕНА")
    print("=" * 70)

if __name__ == '__main__':
    main()
