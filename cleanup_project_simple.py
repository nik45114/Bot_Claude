#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Project Cleanup Script - Скрипт очистки проекта от дублированных файлов и старых версий
"""

import os
import shutil
from pathlib import Path

def cleanup_project():
    """Очистка проекта от дублированных файлов и старых версий"""
    
    print("Начинаю очистку проекта...")
    
    # Список файлов для удаления
    files_to_remove = [
        # Старые версии ботов
        "bot_v4.2.py",
        "bot_v4.7.py", 
        "bot_v4.8.py",
        "bot_v4.9.py",
        "bot_v4.10.py",
        
        # Старые патчи
        "bot_py_PATCH_v4.13.py",
        "integration_patch.py",
        
        # Старые скрипты установки
        "install_admin_shift.sh",
        "auto_update.sh",
        "update.sh",
        
        # Старые миграции
        "migrate_nicknames.py",
        "migrate_to_v4.py",
        "migrate.py",
        
        # Старые конфиги
        "config_example_v4.2.json",
        "config_example_v4_10.json",
        
        # Старые requirements
        "requirements_v4.10.txt",
        
        # Старые README
        "README_V4.13.md",
        
        # Демо файлы
        "demo_finmon_wizard.py",
        "demo_finmon.py",
        "demo_product_sorting.py",
        
        # Тестовые файлы
        "test_admin_management.py",
        "test_admin_monitoring.py",
        "test_browser_headers.py",
        "test_content_generation.py",
        "test_debtor_improvements.py",
        "test_finmon_admins_fix.py",
        "test_finmon_button_wizard.py",
        "test_finmon_integration_simple.py",
        "test_finmon_integration.py",
        "test_finmon_simple.py",
        "test_finmon_time_detection.py",
        "test_finmon.py",
        "test_init_fix.py",
        "test_issue_commands_init.py",
        "test_json_error_handling.py",
        "test_new_modules.py",
        "test_owner_restrictions.py",
        "test_product_fixes.py",
        "test_product_sorting.py",
        "test_time_detection_standalone.py",
        "test_v2ray_improvements.py",
        "test_video_curl_errors.py",
        "test_video_openai_mock.py",
        
        # Старые документации
        "ADMIN_MANAGEMENT_IMPLEMENTATION.md",
        "ADMIN_MONITORING_SUMMARY.md",
        "BEFORE_AFTER_COMPARISON.md",
        "COMPLETION_SUMMARY.txt",
        "COMPLETION_SUMMARY_ADMIN_SHIFT.md",
        "DEBTOR_IMPROVEMENTS.md",
        "FINAL_IMPLEMENTATION_SUMMARY.md",
        "FINAL_SUMMARY_V4.11.md",
        "FINAL_SUMMARY.md",
        "FINAL_V4.13.md",
        "FINMON_ADMINS_FIX_SUMMARY.md",
        "FINMON_ARCHITECTURE.md",
        "FINMON_AUTO_SHIFT_DETECTION.md",
        "FINMON_BUTTON_WIZARD_SUMMARY.md",
        "FINMON_EXAMPLES.md",
        "FINMON_IMPLEMENTATION_SUMMARY.md",
        "FINMON_QUICKSTART.md",
        "FINMON_SIMPLE_SETUP.md",
        "FINMON_SIMPLE_SUMMARY.md",
        "FIX_SUMMARY.md",
        "FORMAT_GUIDE.md",
        "FULL_DOCUMENTATION_v2.3.md",
        "GITHUB_DEPLOY.md",
        "HOTFIX_DEPLOYMENT.md",
        "HOTFIX_SUMMARY.md",
        "IMPLEMENTATION_SUMMARY.md",
        "MIGRATION_V3_TO_V4.2.md",
        "NEW_FEATURES_GUIDE.md",
        "OPENAI_SORA_MIGRATION.md",
        "PR_ADMIN_SHIFT_MANAGEMENT.md",
        "PR_SUMMARY.md",
        "PRODUCT_FIX_SUMMARY.md",
        "QUICK_REFERENCE.md",
        "QUICKSTART.txt",
        "SECURITY_SUMMARY.md",
        "SORTING_FEATURES.md",
        "TELEGRAM_THEMES_RESEARCH.md",
        "UPDATE_TO_V4.11.md",
        "UPDATE_TO_V4.13.md",
        "V4.0_COMPLETE.md",
        "V4.0_RAG_ARCHITECTURE.md",
        "V2RAY_GUIDE.md",
        "V2RAY_IMPROVEMENTS_SUMMARY.md",
        "V2RAY_QUICK_REFERENCE.md",
        "V2RAY_WORKFLOW_DIAGRAM.md",
        "YESAI_SETUP.md",
        
        # Старые файлы данных
        "knowledge_cleaned_v2.jsonl",
        
        # Старые утилиты
        "analyze_db.py",
        "check_db.py",
        "fix_database.py",
        "kb_cleaner.py",
        "kb_importer.py",
        "manual_test_product.py",
        "run_migrations.py",
        "INTEGRATION_EXAMPLE.py",
    ]
    
    # Удаляем файлы
    removed_count = 0
    for file_path in files_to_remove:
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
                print(f"Удален: {file_path}")
                removed_count += 1
            except Exception as e:
                print(f"Ошибка удаления {file_path}: {e}")
        else:
            print(f"Не найден: {file_path}")
    
    # Очищаем модули от дублированных файлов
    modules_to_remove = [
        "modules/admin_management.py",  # Старая версия
        "modules/admin_shift_integration.py",  # Старая версия
        "modules/shift_control.py",  # Старая версия
        "modules/manual_update.py",  # Старая версия
        "modules/ocr_processor.py",  # Старая версия
        "modules/finmon_shift_wizard_old.py",  # Старая версия
        "modules/finmon_simple.py",  # Старая версия
        "modules/runtime_migrator.py",  # Не нужен
    ]
    
    for module_path in modules_to_remove:
        if os.path.exists(module_path):
            try:
                os.remove(module_path)
                print(f"Удален модуль: {module_path}")
                removed_count += 1
            except Exception as e:
                print(f"Ошибка удаления модуля {module_path}: {e}")
    
    print(f"\nОчистка завершена! Удалено файлов: {removed_count}")
    
    # Создаем чистую структуру
    create_clean_structure()
    
    return removed_count

def create_clean_structure():
    """Создание чистой структуры проекта"""
    
    print("\nСоздаю чистую структуру проекта...")
    
    # Создаем директории если их нет
    directories = [
        "modules",
        "migrations", 
        "photos",
        "backups"
    ]
    
    for directory in directories:
        if not os.path.exists(directory):
            os.makedirs(directory)
            print(f"Создана директория: {directory}")
    
    # Создаем .gitignore если его нет
    gitignore_content = """# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
*.egg-info/
.installed.cfg
*.egg

# Virtual environments
venv/
env/
ENV/

# IDE
.vscode/
.idea/
*.swp
*.swo

# Logs
*.log

# Database
*.db
*.sqlite
*.sqlite3

# Photos and backups
photos/
backups/

# Config files with sensitive data
config.json
.env

# Old versions
bot_v*.py
*_old.py
*_backup.py
"""
    
    if not os.path.exists(".gitignore"):
        with open(".gitignore", "w", encoding="utf-8") as f:
            f.write(gitignore_content)
        print("Создан .gitignore")

def fix_bot_py():
    """Исправление основного файла bot.py"""
    
    print("\nИсправляю bot.py...")
    
    try:
        with open("bot.py", "r", encoding="utf-8") as f:
            content = f.read()
        
        # Удаляем дублированные импорты
        content = remove_duplicate_imports(content)
        
        # Удаляем дублированные функции
        content = remove_duplicate_functions(content)
        
        # Обновляем версию
        content = content.replace('VERSION = "4.10"', 'VERSION = "4.15"')
        content = content.replace('VERSION = "4.13"', 'VERSION = "4.15"')
        
        # Сохраняем исправленный файл
        with open("bot.py", "w", encoding="utf-8") as f:
            f.write(content)
        
        print("bot.py исправлен")
        
    except Exception as e:
        print(f"Ошибка исправления bot.py: {e}")

def remove_duplicate_imports(content):
    """Удаление дублированных импортов"""
    
    lines = content.split('\n')
    seen_imports = set()
    cleaned_lines = []
    
    for line in lines:
        if line.strip().startswith('import ') or line.strip().startswith('from '):
            if line.strip() not in seen_imports:
                seen_imports.add(line.strip())
                cleaned_lines.append(line)
            else:
                print(f"Удален дублированный импорт: {line.strip()}")
        else:
            cleaned_lines.append(line)
    
    return '\n'.join(cleaned_lines)

def remove_duplicate_functions(content):
    """Удаление дублированных функций"""
    
    # Список функций которые могут быть дублированы
    duplicate_functions = [
        'cmd_admin',
        'cmd_admins', 
        'cmd_help',
        'cmd_update',
        'handle_photo',
        'handle_message'
    ]
    
    lines = content.split('\n')
    cleaned_lines = []
    in_function = False
    current_function = None
    function_count = {}
    
    i = 0
    while i < len(lines):
        line = lines[i]
        
        # Проверяем начало функции
        if 'async def ' in line or 'def ' in line:
            for func_name in duplicate_functions:
                if f'def {func_name}' in line:
                    if func_name in function_count:
                        function_count[func_name] += 1
                        if function_count[func_name] > 1:
                            # Пропускаем дублированную функцию
                            print(f"Удалена дублированная функция: {func_name}")
                            # Пропускаем до следующей функции или класса
                            while i < len(lines) and not (lines[i].strip().startswith('def ') or lines[i].strip().startswith('class ') or lines[i].strip().startswith('async def ')):
                                i += 1
                            i -= 1  # Возвращаемся на строку с функцией
                            break
                    else:
                        function_count[func_name] = 1
                    break
        
        cleaned_lines.append(line)
        i += 1
    
    return '\n'.join(cleaned_lines)

def create_clean_requirements():
    """Создание чистого requirements.txt"""
    
    print("\nСоздаю чистый requirements.txt...")
    
    requirements_content = """# Core dependencies
python-telegram-bot==20.7
openai==0.28.1
numpy==1.24.3
scikit-learn==1.3.0
paramiko==3.4.0
requests==2.31.0

# Data handling
pydantic>=2.0.0
gspread>=5.0.0
oauth2client>=4.1.3
python-dotenv>=1.0.0
pytz>=2024.1

# OCR and image processing
opencv-python>=4.8.0
pytesseract>=0.3.10
Pillow>=10.0.0

# Database
sqlite3

# Additional utilities
json
datetime
os
shutil
subprocess
logging
re
base64
"""
    
    with open("requirements.txt", "w", encoding="utf-8") as f:
        f.write(requirements_content)
    
    print("requirements.txt обновлен")

def create_clean_readme():
    """Создание чистого README.md"""
    
    print("\nСоздаю чистый README.md...")
    
    readme_content = """# Club Assistant Bot v4.15

## Описание

Улучшенная система управления администраторами и контроля смен с кнопочным интерфейсом.

## Основные возможности

- Кнопочный интерфейс - удобная навигация по меню
- Приватные отчеты - контроль доступа на уровне каждого отчета
- Система смен - сдача смен с фото и OCR
- Управление админами - полная видимость всех администраторов
- Ручное обновление - обновление через команды в боте

## Команды

### Основные:
- `/adminpanel` - админ-панель с кнопочным интерфейсом
- `/shift` - сдача смены с фото и OCR
- `/systemstatus` - статус системы

### Обновления:
- `/manualupdate` - ручное обновление через бота
- `/updatelog` - лог обновлений

## Установка

### Автоматическая:
```bash
python3 enhanced_integration_patch.py bot.py
./setup_enhanced_admin_shift.sh
python3 migrate_enhanced_admin_shift.py
systemctl restart club_assistant
```

### Ручная:
1. Установите зависимости: `pip install -r requirements.txt`
2. Настройте config.json
3. Запустите миграцию: `python3 migrate_enhanced_admin_shift.py`
4. Запустите бота: `python3 bot.py`

## Структура проекта

```
├── bot.py                          # Основной файл бота
├── modules/                        # Модули системы
│   ├── enhanced_admin_shift.py     # Улучшенная система админов
│   ├── enhanced_shift_submission.py # Улучшенная система смен
│   └── enhanced_admin_shift_integration.py # Интеграция
├── migrations/                     # Миграции базы данных
├── photos/                         # Хранение фото смен
├── backups/                        # Резервные копии
└── requirements.txt                # Зависимости
```

## Документация

- `ENHANCED_ADMIN_SHIFT_GUIDE.md` - полное руководство
- `ENHANCED_COMPLETION_SUMMARY.md` - описание всех изменений

## Поддержка

При возникновении проблем:
1. Проверьте логи: `journalctl -u club_assistant -n 50`
2. Проверьте статус: `/systemstatus`
3. Проверьте админ-панель: `/adminpanel`

## Лицензия

MIT License
"""
    
    with open("README.md", "w", encoding="utf-8") as f:
        f.write(readme_content)
    
    print("README.md обновлен")

if __name__ == "__main__":
    print("Скрипт очистки проекта Club Assistant Bot")
    print("=" * 50)
    
    # Очищаем проект
    removed_count = cleanup_project()
    
    # Исправляем bot.py
    fix_bot_py()
    
    # Создаем чистые файлы
    create_clean_requirements()
    create_clean_readme()
    
    print("\n" + "=" * 50)
    print("Очистка проекта завершена!")
    print(f"Удалено файлов: {removed_count}")
    print("\nСледующие шаги:")
    print("1. Проверьте bot.py на ошибки")
    print("2. Запустите миграцию: python3 migrate_enhanced_admin_shift.py")
    print("3. Перезапустите бота: systemctl restart club_assistant")
    print("4. Проверьте работу: /adminpanel")
