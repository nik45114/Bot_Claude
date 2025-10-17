#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Тест проверки что IssueCommands инициализируется в правильном порядке
"""

def verify_issue_commands_initialization():
    """Проверка что IssueCommands инициализируется после Application.builder()"""
    print("\n🧪 Проверка инициализации IssueCommands в bot.py...")
    
    import os
    bot_path = os.path.join(os.path.dirname(__file__), 'bot.py')
    
    with open(bot_path, 'r') as f:
        content = f.read()
    
    lines = content.split('\n')
    
    run_line = None
    app_builder_line = None
    init_issue_line = None
    first_issue_handler_line = None
    post_init_issue_line = None
    
    for i, line in enumerate(lines):
        if 'def run(self):' in line:
            run_line = i
        if run_line is not None and i > run_line:
            # Найти строку с Application.builder()
            if 'Application.builder().token' in line and not app_builder_line:
                app_builder_line = i
            # Найти строку инициализации IssueCommands в run()
            if 'self.issue_commands = IssueCommands' in line and not line.strip().startswith('#'):
                init_issue_line = i
            # Найти первый handler с issue_commands
            if 'self.issue_commands.start_report_issue' in line:
                first_issue_handler_line = i
        # Найти закомментированную строку в post_init
        if 'def post_init' in line:
            post_init_line = i
        if 'post_init_line' in locals() and i > post_init_line and i < post_init_line + 10:
            if 'self.issue_commands = IssueCommands' in line and line.strip().startswith('#'):
                post_init_issue_line = i
    
    print(f"  run() метод: строка {run_line}")
    print(f"  Application.builder(): строка {app_builder_line}")
    print(f"  IssueCommands инициализация в run(): строка {init_issue_line}")
    print(f"  Первый handler с issue_commands: строка {first_issue_handler_line}")
    print(f"  Закомментированная IssueCommands в post_init: строка {post_init_issue_line}")
    
    # Проверяем что все найдено
    assert app_builder_line is not None, "Application.builder() не найден"
    assert init_issue_line is not None, "IssueCommands инициализация в run() не найдена"
    assert first_issue_handler_line is not None, "Handler с issue_commands не найден"
    assert post_init_issue_line is not None, "Закомментированная строка в post_init не найдена"
    
    # Проверяем правильный порядок
    assert app_builder_line < init_issue_line, \
        "Application.builder() должен быть ПЕРЕД инициализацией IssueCommands"
    assert init_issue_line < first_issue_handler_line, \
        "IssueCommands должен быть инициализирован ПЕРЕД первым handler с issue_commands"
    
    print("\n  ✅ Порядок инициализации IssueCommands правильный:")
    print("     1. Application.builder()")
    print("     2. IssueCommands инициализация")
    print("     3. Регистрация handlers")
    print("     4. post_init (IssueCommands уже создан, строка закомментирована)")
    
    return True

def verify_comment_in_post_init():
    """Проверка что в post_init строка с IssueCommands закомментирована"""
    print("\n🧪 Проверка что старая инициализация в post_init закомментирована...")
    
    import os
    bot_path = os.path.join(os.path.dirname(__file__), 'bot.py')
    
    with open(bot_path, 'r') as f:
        content = f.read()
    
    lines = content.split('\n')
    
    in_post_init = False
    found_comment = False
    found_active = False
    
    for i, line in enumerate(lines):
        if 'async def post_init' in line:
            in_post_init = True
        elif in_post_init and line.strip().startswith('def '):
            # Вышли из post_init
            break
        elif in_post_init:
            if 'self.issue_commands = IssueCommands' in line:
                if line.strip().startswith('#'):
                    found_comment = True
                    print(f"  ✅ Строка {i+1} закомментирована: {line.strip()}")
                else:
                    found_active = True
                    print(f"  ❌ Строка {i+1} НЕ закомментирована: {line.strip()}")
    
    assert found_comment, "Закомментированная строка с IssueCommands не найдена в post_init"
    assert not found_active, "Найдена незакомментированная строка с IssueCommands в post_init!"
    
    print("  ✅ Старая инициализация правильно закомментирована")
    return True

def main():
    print("=" * 60)
    print("   ПРОВЕРКА ИСПРАВЛЕНИЯ ISSUE_COMMANDS")
    print("=" * 60)
    
    try:
        if not verify_issue_commands_initialization():
            return 1
        
        if not verify_comment_in_post_init():
            return 1
        
        print("\n" + "=" * 60)
        print("✅ ВСЕ ПРОВЕРКИ ПРОЙДЕНЫ УСПЕШНО!")
        print("=" * 60)
        print("\n📝 Резюме исправления:")
        print("  1. ❌ Старое: IssueCommands в post_init (слишком поздно)")
        print("  2. ✅ Новое: IssueCommands после Application.builder()")
        print("  3. ✅ Переменная: application (не app)")
        print("  4. ✅ Логирование добавлено")
        
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
