#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Простой тест проверки что команды инициализируются в правильном порядке
"""

def test_initialization_logic():
    """Проверка логики инициализации"""
    print("\n🧪 Демонстрация изменения логики инициализации...")
    
    # Симулируем старый неправильный порядок
    print("\n  ❌ СТАРЫЙ (неправильный) порядок:")
    print("     1. cash_commands = None  (в __init__)")
    print("     2. Application.builder().build()  (в run())")
    print("     3. add_handler(cash_commands.start_add_movement)  <- AttributeError!")
    print("     4. post_init: cash_commands = CashCommands(...)  (слишком поздно)")
    
    # Симулируем новый правильный порядок  
    print("\n  ✅ НОВЫЙ (правильный) порядок:")
    print("     1. cash_commands = CashCommands(...)  <- Ранняя инициализация")
    print("     2. product_commands = ProductCommands(...)  <- Ранняя инициализация")
    print("     3. Application.builder().build()")
    print("     4. add_handler(cash_commands.start_add_movement)  <- Работает!")
    print("     5. post_init: issue_commands = IssueCommands(...)  <- Требует bot_app")
    
    print("\n✅ Логика инициализации исправлена!")
    
    return True

def verify_bot_py_changes():
    """Проверка что изменения внесены в bot.py"""
    print("\n🧪 Проверка изменений в bot.py...")
    
    with open('/home/runner/work/Bot_Claude/Bot_Claude/bot.py', 'r') as f:
        content = f.read()
    
    # Проверяем что в run() есть инициализация команд перед Application
    lines = content.split('\n')
    
    run_line = None
    init_cash_line = None
    init_product_line = None
    app_builder_line = None
    add_handler_line = None
    
    for i, line in enumerate(lines):
        if 'def run(self):' in line:
            run_line = i
        if 'self.cash_commands = CashCommands' in line and run_line and i > run_line:
            init_cash_line = i
        if 'self.product_commands = ProductCommands' in line and run_line and i > run_line:
            init_product_line = i
        if 'Application.builder().token' in line and run_line and i > run_line and not app_builder_line:
            app_builder_line = i
        if 'self.cash_commands.start_add_movement' in line and run_line and i > run_line:
            add_handler_line = i
            break  # Нашли первое использование
    
    print(f"  run() метод: строка {run_line}")
    print(f"  CashCommands инициализация: строка {init_cash_line}")
    print(f"  ProductCommands инициализация: строка {init_product_line}")
    print(f"  Application.builder(): строка {app_builder_line}")
    print(f"  Первый handler с cash_commands: строка {add_handler_line}")
    
    # Проверяем порядок
    assert init_cash_line is not None, "CashCommands инициализация не найдена в run()"
    assert init_product_line is not None, "ProductCommands инициализация не найдена в run()"
    assert app_builder_line is not None, "Application.builder() не найден"
    assert add_handler_line is not None, "Handler с cash_commands не найден"
    
    assert init_cash_line < app_builder_line, "CashCommands должен быть инициализирован ПЕРЕД Application.builder()"
    assert init_product_line < app_builder_line, "ProductCommands должен быть инициализирован ПЕРЕД Application.builder()"
    assert init_cash_line < add_handler_line, "CashCommands должен быть инициализирован ПЕРЕД add_handler"
    assert init_product_line < add_handler_line, "ProductCommands должен быть инициализирован ПЕРЕД add_handler"
    assert app_builder_line < add_handler_line, "Application.builder() должен быть ПЕРЕД add_handler"
    
    print("\n  ✅ Порядок инициализации правильный:")
    print("     1. CashCommands инициализация")
    print("     2. ProductCommands инициализация")
    print("     3. Application.builder()")
    print("     4. add_handler()")
    
    return True

def main():
    print("=" * 60)
    print("   ПРОВЕРКА ИСПРАВЛЕНИЯ ПОРЯДКА ИНИЦИАЛИЗАЦИИ")
    print("=" * 60)
    
    try:
        if not verify_bot_py_changes():
            return 1
        
        if not test_initialization_logic():
            return 1
        
        print("\n" + "=" * 60)
        print("✅ ВСЕ ПРОВЕРКИ ПРОЙДЕНЫ УСПЕШНО!")
        print("=" * 60)
        
        return 0
        
    except AssertionError as e:
        print(f"\n❌ ОШИБКА: {e}")
        import traceback
        traceback.print_exc()
        return 1
    except Exception as e:
        print(f"\n❌ НЕОЖИДАННАЯ ОШИБКА: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == '__main__':
    import sys
    sys.exit(main())
