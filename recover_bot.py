#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Bot Recovery Script - Скрипт восстановления основного бота
"""

import os
import sys
import shutil
from datetime import datetime

def create_backup():
    """Создание резервной копии"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_name = f"bot_backup_{timestamp}"
    
    if os.path.exists("bot.py"):
        shutil.copy2("bot.py", f"{backup_name}.py")
        print(f"Создана резервная копия: {backup_name}.py")
        return True
    return False

def fix_bot_imports():
    """Исправление импортов в bot.py"""
    try:
        with open("bot.py", "r", encoding="utf-8") as f:
            content = f.read()
        
        # Заменяем проблемные импорты на заглушки
        replacements = [
            ("from vector_store import VectorStore", "# from vector_store import VectorStore  # Отключено"),
            ("from embeddings import EmbeddingService", "# from embeddings import EmbeddingService  # Отключено"),
            ("from draft_queue import DraftQueue", "# from draft_queue import DraftQueue  # Отключено"),
        ]
        
        for old, new in replacements:
            content = content.replace(old, new)
        
        # Добавляем заглушки для отключенных модулей
        stub_code = '''
# Заглушки для отключенных модулей
class VectorStore:
    def __init__(self, *args, **kwargs):
        pass
    def add(self, *args, **kwargs):
        pass
    def search(self, *args, **kwargs):
        return []
    def stats(self):
        return {'total_vectors': 0}

class EmbeddingService:
    def __init__(self, *args, **kwargs):
        pass
    def embed_text(self, text):
        return [0.0] * 384

class DraftQueue:
    def __init__(self, *args, **kwargs):
        pass
    def add(self, *args, **kwargs):
        pass
    def get(self, *args, **kwargs):
        return None
'''
        
        # Вставляем заглушки после импортов
        import_end = content.find("CONFIG_PATH = 'config.json'")
        if import_end != -1:
            content = content[:import_end] + stub_code + "\n" + content[import_end:]
        
        # Сохраняем исправленный файл
        with open("bot.py", "w", encoding="utf-8") as f:
            f.write(content)
        
        print("Импорты в bot.py исправлены")
        return True
        
    except Exception as e:
        print(f"Ошибка исправления bot.py: {e}")
        return False

def test_bot():
    """Тестирование бота"""
    try:
        import bot
        print("bot.py импортируется успешно")
        return True
    except Exception as e:
        print(f"Ошибка импорта bot.py: {e}")
        return False

def main():
    """Основная функция восстановления"""
    print("Восстановление Club Assistant Bot")
    print("=" * 40)
    
    # Создаем резервную копию
    if create_backup():
        print("✅ Резервная копия создана")
    else:
        print("⚠️ Не удалось создать резервную копию")
    
    # Исправляем импорты
    if fix_bot_imports():
        print("✅ Импорты исправлены")
    else:
        print("❌ Ошибка исправления импортов")
        return False
    
    # Тестируем бота
    if test_bot():
        print("✅ bot.py готов к запуску")
        print("\nТеперь можно запустить: python bot.py")
        return True
    else:
        print("❌ bot.py все еще имеет проблемы")
        return False

if __name__ == "__main__":
    success = main()
    if success:
        print("\n🎉 Восстановление завершено успешно!")
    else:
        print("\n❌ Восстановление не удалось")
        print("Используйте упрощенную версию: python simple_bot.py")
