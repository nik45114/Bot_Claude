#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Manual Update Function - Функция для ручного обновления через бота
Позволяет обновить бота через команду в Telegram
"""

import logging
import subprocess
import os
import shutil
from datetime import datetime
from typing import Tuple, Dict
from telegram import Update
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)

class ManualUpdateSystem:
    """Система ручного обновления через бота"""
    
    def __init__(self, bot_dir: str = "/opt/club_assistant", backup_dir: str = None):
        self.bot_dir = bot_dir
        self.backup_dir = backup_dir or os.path.join(bot_dir, "backups")
        self.log_file = os.path.join(bot_dir, "update.log")
        
        # Создаем директорию для бэкапов
        os.makedirs(self.backup_dir, exist_ok=True)
    
    def log_update(self, message: str):
        """Логирование процесса обновления"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"[{timestamp}] {message}\n"
        
        try:
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(log_entry)
        except Exception as e:
            logger.error(f"❌ Error writing to log: {e}")
    
    def create_backup(self) -> Tuple[bool, str]:
        """Создание резервной копии перед обновлением"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_name = f"backup_manual_{timestamp}"
            backup_path = os.path.join(self.backup_dir, backup_name)
            
            # Создаем директорию бэкапа
            os.makedirs(backup_path, exist_ok=True)
            
            # Файлы для бэкапа
            files_to_backup = [
                "bot.py",
                "config.json",
                "knowledge.db",
                "requirements.txt"
            ]
            
            backed_up_files = []
            
            for file_name in files_to_backup:
                source_path = os.path.join(self.bot_dir, file_name)
                if os.path.exists(source_path):
                    dest_path = os.path.join(backup_path, file_name)
                    shutil.copy2(source_path, dest_path)
                    backed_up_files.append(file_name)
            
            self.log_update(f"✅ Backup created: {backup_name} ({len(backed_up_files)} files)")
            return True, f"✅ Бэкап создан: {backup_name}\nФайлы: {', '.join(backed_up_files)}"
            
        except Exception as e:
            error_msg = f"❌ Ошибка создания бэкапа: {e}"
            self.log_update(error_msg)
            return False, error_msg
    
    def check_git_status(self) -> Tuple[bool, str]:
        """Проверка статуса Git репозитория"""
        try:
            # Проверяем, что мы в Git репозитории
            result = subprocess.run(
                ['git', 'status', '--porcelain'],
                cwd=self.bot_dir,
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode != 0:
                return False, "❌ Не удалось проверить статус Git репозитория"
            
            # Проверяем наличие изменений
            if result.stdout.strip():
                return False, f"❌ Обнаружены несохраненные изменения:\n{result.stdout.strip()}"
            
            # Проверяем подключение к удаленному репозиторию
            result = subprocess.run(
                ['git', 'remote', '-v'],
                cwd=self.bot_dir,
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode != 0 or not result.stdout.strip():
                return False, "❌ Удаленный репозиторий не настроен"
            
            self.log_update("✅ Git status check passed")
            return True, "✅ Git репозиторий в порядке"
            
        except subprocess.TimeoutExpired:
            error_msg = "❌ Таймаут при проверке Git статуса"
            self.log_update(error_msg)
            return False, error_msg
        except Exception as e:
            error_msg = f"❌ Ошибка проверки Git: {e}"
            self.log_update(error_msg)
            return False, error_msg
    
    def fetch_updates(self) -> Tuple[bool, str]:
        """Получение обновлений с GitHub"""
        try:
            # Fetch обновлений
            result = subprocess.run(
                ['git', 'fetch', 'origin', 'main'],
                cwd=self.bot_dir,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode != 0:
                error_msg = f"❌ Ошибка при получении обновлений:\n{result.stderr}"
                self.log_update(error_msg)
                return False, error_msg
            
            # Проверяем количество новых коммитов
            result = subprocess.run(
                ['git', 'rev-list', '--count', 'HEAD..origin/main'],
                cwd=self.bot_dir,
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode != 0:
                error_msg = "❌ Ошибка при подсчете коммитов"
                self.log_update(error_msg)
                return False, error_msg
            
            try:
                commits_count = int(result.stdout.strip())
            except ValueError:
                error_msg = f"❌ Неверный формат количества коммитов: {result.stdout.strip()}"
                self.log_update(error_msg)
                return False, error_msg
            
            if commits_count == 0:
                return True, "✅ Бот уже использует последнюю версию"
            
            self.log_update(f"✅ Found {commits_count} new commits")
            return True, f"✅ Найдено {commits_count} новых коммитов"
            
        except subprocess.TimeoutExpired:
            error_msg = "❌ Таймаут при получении обновлений"
            self.log_update(error_msg)
            return False, error_msg
        except Exception as e:
            error_msg = f"❌ Ошибка получения обновлений: {e}"
            self.log_update(error_msg)
            return False, error_msg
    
    def apply_updates(self) -> Tuple[bool, str]:
        """Применение обновлений"""
        try:
            # Pull обновлений
            result = subprocess.run(
                ['git', 'pull', 'origin', 'main'],
                cwd=self.bot_dir,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode != 0:
                error_msg = f"❌ Ошибка при применении обновлений:\n{result.stderr}"
                self.log_update(error_msg)
                return False, error_msg
            
            # Проверяем, что обновились нужные файлы
            updated_files = []
            if "bot.py" in result.stdout:
                updated_files.append("bot.py")
            if "requirements.txt" in result.stdout:
                updated_files.append("requirements.txt")
            
            self.log_update(f"✅ Updates applied successfully: {', '.join(updated_files)}")
            return True, f"✅ Обновления применены успешно\nОбновленные файлы: {', '.join(updated_files)}"
            
        except subprocess.TimeoutExpired:
            error_msg = "❌ Таймаут при применении обновлений"
            self.log_update(error_msg)
            return False, error_msg
        except Exception as e:
            error_msg = f"❌ Ошибка применения обновлений: {e}"
            self.log_update(error_msg)
            return False, error_msg
    
    def install_dependencies(self) -> Tuple[bool, str]:
        """Установка зависимостей"""
        try:
            requirements_file = os.path.join(self.bot_dir, "requirements.txt")
            if not os.path.exists(requirements_file):
                return True, "⚠️ Файл requirements.txt не найден, пропускаем установку зависимостей"
            
            # Устанавливаем зависимости
            result = subprocess.run(
                ['pip3', 'install', '-r', requirements_file, '--break-system-packages'],
                cwd=self.bot_dir,
                capture_output=True,
                text=True,
                timeout=120
            )
            
            if result.returncode != 0:
                error_msg = f"❌ Ошибка установки зависимостей:\n{result.stderr}"
                self.log_update(error_msg)
                return False, error_msg
            
            self.log_update("✅ Dependencies installed successfully")
            return True, "✅ Зависимости установлены успешно"
            
        except subprocess.TimeoutExpired:
            error_msg = "❌ Таймаут при установке зависимостей"
            self.log_update(error_msg)
            return False, error_msg
        except Exception as e:
            error_msg = f"❌ Ошибка установки зависимостей: {e}"
            self.log_update(error_msg)
            return False, error_msg
    
    def restart_bot_service(self) -> Tuple[bool, str]:
        """Перезапуск сервиса бота"""
        try:
            # Останавливаем сервис
            result = subprocess.run(
                ['systemctl', 'stop', 'club_assistant'],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode != 0:
                error_msg = f"❌ Ошибка остановки сервиса:\n{result.stderr}"
                self.log_update(error_msg)
                return False, error_msg
            
            # Ждем немного
            import time
            time.sleep(2)
            
            # Запускаем сервис
            result = subprocess.run(
                ['systemctl', 'start', 'club_assistant'],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode != 0:
                error_msg = f"❌ Ошибка запуска сервиса:\n{result.stderr}"
                self.log_update(error_msg)
                return False, error_msg
            
            # Проверяем статус
            time.sleep(3)
            result = subprocess.run(
                ['systemctl', 'is-active', 'club_assistant'],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode != 0 or result.stdout.strip() != 'active':
                error_msg = "❌ Сервис не запустился корректно"
                self.log_update(error_msg)
                return False, error_msg
            
            self.log_update("✅ Bot service restarted successfully")
            return True, "✅ Сервис бота перезапущен успешно"
            
        except subprocess.TimeoutExpired:
            error_msg = "❌ Таймаут при перезапуске сервиса"
            self.log_update(error_msg)
            return False, error_msg
        except Exception as e:
            error_msg = f"❌ Ошибка перезапуска сервиса: {e}"
            self.log_update(error_msg)
            return False, error_msg
    
    def perform_full_update(self) -> Tuple[bool, str]:
        """Выполнение полного обновления"""
        try:
            self.log_update("🚀 Starting manual update process")
            
            steps = []
            
            # Шаг 1: Создание бэкапа
            success, message = self.create_backup()
            steps.append(f"1. Бэкап: {message}")
            if not success:
                return False, "\n".join(steps)
            
            # Шаг 2: Проверка Git
            success, message = self.check_git_status()
            steps.append(f"2. Git статус: {message}")
            if not success:
                return False, "\n".join(steps)
            
            # Шаг 3: Получение обновлений
            success, message = self.fetch_updates()
            steps.append(f"3. Получение обновлений: {message}")
            if not success:
                return False, "\n".join(steps)
            
            # Если нет обновлений
            if "уже использует последнюю версию" in message:
                return True, "\n".join(steps)
            
            # Шаг 4: Применение обновлений
            success, message = self.apply_updates()
            steps.append(f"4. Применение обновлений: {message}")
            if not success:
                return False, "\n".join(steps)
            
            # Шаг 5: Установка зависимостей
            success, message = self.install_dependencies()
            steps.append(f"5. Зависимости: {message}")
            if not success:
                return False, "\n".join(steps)
            
            # Шаг 6: Перезапуск сервиса
            success, message = self.restart_bot_service()
            steps.append(f"6. Перезапуск: {message}")
            if not success:
                return False, "\n".join(steps)
            
            self.log_update("✅ Manual update completed successfully")
            return True, "\n".join(steps)
            
        except Exception as e:
            error_msg = f"❌ Критическая ошибка обновления: {e}"
            self.log_update(error_msg)
            return False, error_msg
    
    def get_update_log(self, lines: int = 20) -> str:
        """Получить последние записи из лога обновлений"""
        try:
            if not os.path.exists(self.log_file):
                return "📝 Лог обновлений пуст"
            
            with open(self.log_file, "r", encoding="utf-8") as f:
                all_lines = f.readlines()
            
            recent_lines = all_lines[-lines:] if len(all_lines) > lines else all_lines
            return "📝 **Последние записи лога обновлений:**\n\n" + "".join(recent_lines)
            
        except Exception as e:
            return f"❌ Ошибка чтения лога: {e}"


class ManualUpdateCommands:
    """Команды для ручного обновления"""
    
    def __init__(self, update_system: ManualUpdateSystem):
        self.update_system = update_system
    
    async def cmd_manual_update(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда ручного обновления"""
        user_id = update.effective_user.id
        
        # Проверяем права (только владелец)
        if not self._is_owner(user_id):
            await update.message.reply_text("❌ Эта команда доступна только владельцу бота")
            return
        
        await update.message.reply_text("🔄 Начинаю процесс ручного обновления...")
        
        try:
            success, message = self.update_system.perform_full_update()
            
            if success:
                await update.message.reply_text(
                    f"✅ **Обновление завершено успешно!**\n\n{message}",
                    parse_mode='Markdown'
                )
            else:
                await update.message.reply_text(
                    f"❌ **Ошибка при обновлении**\n\n{message}",
                    parse_mode='Markdown'
                )
                
        except Exception as e:
            await update.message.reply_text(f"❌ Критическая ошибка: {e}")
    
    async def cmd_update_log(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показать лог обновлений"""
        user_id = update.effective_user.id
        
        if not self._is_owner(user_id):
            await update.message.reply_text("❌ Эта команда доступна только владельцу бота")
            return
        
        log_text = self.update_system.get_update_log()
        await update.message.reply_text(log_text, parse_mode='Markdown')
    
    def _is_owner(self, user_id: int) -> bool:
        """Проверка, является ли пользователь владельцем"""
        # Здесь должна быть проверка из основной системы админов
        # Пока возвращаем True для тестирования
        return True
