#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
V2Ray Bot Commands
Команды для управления V2Ray через Telegram бота
"""

from telegram import Update
from telegram.ext import ContextTypes
import logging

logger = logging.getLogger(__name__)


class V2RayCommands:
    """Класс с командами V2Ray для бота"""
    
    def __init__(self, manager, admin_manager, owner_id: int):
        self.manager = manager
        self.admin_manager = admin_manager
        self.owner_id = owner_id  # Только владелец может управлять V2Ray
    
    def is_owner(self, user_id: int) -> bool:
        """Проверка: является ли пользователь владельцем"""
        return user_id == self.owner_id
    
    async def cmd_v2ray(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Главное меню V2Ray"""
        if not self.is_owner(update.effective_user.id):
            await update.message.reply_text("❌ Доступ запрещён")
            return
        
        text = """🔐 V2Ray Manager

Команды:

📡 Серверы:
/v2add <имя> <host> <user> <pass> - добавить сервер
/v2list - список серверов
/v2setup <имя> - установить V2Ray на сервер
/v2stats <имя> - статистика сервера

👤 Пользователи:
/v2user <сервер> <user_id> [email] - добавить пользователя
/v2remove <сервер> <uuid> - удалить пользователя

⚙️ Настройки:
/v2traffic <сервер> <тип> - изменить тип трафика
  Типы: tcp, ws, grpc, tls

Пример:
/v2add main 1.2.3.4 root MyPass123
/v2setup main
/v2user main @username Вася"""

        await update.message.reply_text(text)
    
    async def cmd_v2add(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Добавление сервера: /v2add <имя> <host> <user> <pass>"""
        if not self.is_owner(update.effective_user.id):
            return
        
        try:
            if len(context.args) < 4:
                await update.message.reply_text(
                    "Использование: /v2add <имя> <host> <user> <pass>\n\n"
                    "Пример: /v2add main 1.2.3.4 root MyPass123"
                )
                return
            
            name, host, username, password = context.args[0:4]
            
            await update.message.reply_text("⏳ Добавляю сервер...")
            
            if self.manager.add_server(name, host, username, password):
                await update.message.reply_text(
                    f"✅ Сервер '{name}' добавлен!\n\n"
                    f"🖥 Host: {host}\n"
                    f"👤 User: {username}\n\n"
                    f"Теперь выполни: /v2setup {name}"
                )
            else:
                await update.message.reply_text("❌ Ошибка добавления сервера")
            
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка: {e}")
    
    async def cmd_v2list(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Список серверов"""
        if not self.is_owner(update.effective_user.id):
            return
        
        servers = self.manager.list_servers()
        
        if not servers:
            await update.message.reply_text("📭 Нет серверов")
            return
        
        text = "📡 Серверы V2Ray:\n\n"
        
        for srv in servers:
            text += f"🔹 {srv['name']}\n"
            text += f"   Host: {srv['host']}\n"
            text += f"   Port: {srv['port']}\n"
            text += f"   Traffic: {srv['traffic_type']}\n\n"
        
        await update.message.reply_text(text)
    
    async def cmd_v2setup(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Установка V2Ray на сервер: /v2setup <имя>"""
        if not self.is_owner(update.effective_user.id):
            return
        
        try:
            if len(context.args) < 1:
                await update.message.reply_text("Использование: /v2setup <имя>")
                return
            
            server_name = context.args[0]
            
            await update.message.reply_text(f"⏳ Подключаюсь к серверу {server_name}...")
            
            server = self.manager.get_server(server_name)
            
            if not server:
                await update.message.reply_text(f"❌ Сервер {server_name} не найден")
                return
            
            if not server.connect():
                await update.message.reply_text("❌ Не удалось подключиться к серверу")
                return
            
            await update.message.reply_text("📥 Устанавливаю V2Ray (может занять 2-3 минуты)...")
            
            if not server.install_v2ray():
                await update.message.reply_text("❌ Ошибка установки V2Ray")
                server.disconnect()
                return
            
            await update.message.reply_text("⚙️ Создаю конфигурацию...")
            
            config = server.create_config(port=443, traffic_type="tcp")
            
            if not server.deploy_config(config):
                await update.message.reply_text("❌ Ошибка применения конфигурации")
                server.disconnect()
                return
            
            server.disconnect()
            
            await update.message.reply_text(
                f"✅ V2Ray установлен на {server_name}!\n\n"
                f"Теперь можешь добавлять пользователей:\n"
                f"/v2user {server_name} <user_id> [email]"
            )
            
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка: {e}")
    
    async def cmd_v2user(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Добавление пользователя: /v2user <сервер> <user_id> [email]"""
        if not self.is_owner(update.effective_user.id):
            return
        
        try:
            if len(context.args) < 2:
                await update.message.reply_text(
                    "Использование: /v2user <сервер> <user_id> [email]\n\n"
                    "Пример: /v2user main @username Вася"
                )
                return
            
            server_name = context.args[0]
            user_id = context.args[1]
            email = ' '.join(context.args[2:]) if len(context.args) > 2 else ""
            
            await update.message.reply_text(f"⏳ Добавляю пользователя на {server_name}...")
            
            server = self.manager.get_server(server_name)
            
            if not server:
                await update.message.reply_text(f"❌ Сервер {server_name} не найден")
                return
            
            if not server.connect():
                await update.message.reply_text("❌ Не удалось подключиться")
                return
            
            vless_link = server.add_user(user_id, email)
            
            server.disconnect()
            
            if not vless_link:
                await update.message.reply_text("❌ Ошибка добавления пользователя")
                return
            
            # Извлекаем UUID из ссылки
            import re
            uuid_match = re.search(r'vless://([^@]+)@', vless_link)
            user_uuid = uuid_match.group(1) if uuid_match else ""
            
            # Сохраняем в базу
            self.manager.save_user(server_name, user_id, user_uuid, vless_link, email)
            
            text = f"✅ Пользователь добавлен!\n\n"
            text += f"👤 ID: {user_id}\n"
            text += f"📧 Email: {email or 'не указан'}\n"
            text += f"🔑 UUID: {user_uuid}\n\n"
            text += f"🔗 VLESS ссылка:\n`{vless_link}`"
            
            await update.message.reply_text(text, parse_mode='Markdown')
            
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка: {e}")
    
    async def cmd_v2stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Статистика сервера: /v2stats <имя>"""
        if not self.is_owner(update.effective_user.id):
            return
        
        try:
            if len(context.args) < 1:
                await update.message.reply_text("Использование: /v2stats <имя>")
                return
            
            server_name = context.args[0]
            
            await update.message.reply_text("⏳ Получаю статистику...")
            
            server = self.manager.get_server(server_name)
            
            if not server:
                await update.message.reply_text(f"❌ Сервер {server_name} не найден")
                return
            
            if not server.connect():
                await update.message.reply_text("❌ Не удалось подключиться")
                return
            
            stats = server.get_stats()
            
            server.disconnect()
            
            if not stats:
                await update.message.reply_text("❌ Ошибка получения статистики")
                return
            
            status_emoji = "🟢" if stats['running'] else "🔴"
            
            text = f"📊 Статистика {server_name}\n\n"
            text += f"{status_emoji} Статус: {'Работает' if stats['running'] else 'Остановлен'}\n"
            text += f"🖥 Host: {stats['host']}\n"
            text += f"🔌 Port: {stats['port']}\n"
            text += f"📡 Network: {stats['network']}\n"
            text += f"👥 Пользователей: {stats['users']}"
            
            await update.message.reply_text(text)
            
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка: {e}")
    
    async def cmd_v2traffic(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Изменение типа трафика: /v2traffic <сервер> <тип>"""
        if not self.is_owner(update.effective_user.id):
            return
        
        try:
            if len(context.args) < 2:
                await update.message.reply_text(
                    "Использование: /v2traffic <сервер> <тип>\n\n"
                    "Типы трафика:\n"
                    "• tcp - обычный TCP\n"
                    "• ws - WebSocket\n"
                    "• grpc - gRPC\n"
                    "• tls - TLS шифрование\n\n"
                    "Пример: /v2traffic main ws"
                )
                return
            
            server_name = context.args[0]
            traffic_type = context.args[1].lower()
            
            if traffic_type not in ['tcp', 'ws', 'grpc', 'tls']:
                await update.message.reply_text("❌ Неверный тип трафика. Используй: tcp, ws, grpc, tls")
                return
            
            await update.message.reply_text(f"⏳ Изменяю тип трафика на {traffic_type}...")
            
            server = self.manager.get_server(server_name)
            
            if not server:
                await update.message.reply_text(f"❌ Сервер {server_name} не найден")
                return
            
            if not server.connect():
                await update.message.reply_text("❌ Не удалось подключиться")
                return
            
            if server.change_traffic_type(traffic_type):
                server.disconnect()
                await update.message.reply_text(
                    f"✅ Тип трафика изменён на {traffic_type}!\n\n"
                    f"⚠️ Все пользователи должны обновить свои ссылки.\n"
                    f"Создай новые: /v2user {server_name} <user_id>"
                )
            else:
                server.disconnect()
                await update.message.reply_text("❌ Ошибка изменения типа трафика")
            
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка: {e}")
    
    async def cmd_v2remove(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Удаление пользователя: /v2remove <сервер> <uuid>"""
        if not self.is_owner(update.effective_user.id):
            return
        
        try:
            if len(context.args) < 2:
                await update.message.reply_text(
                    "Использование: /v2remove <сервер> <uuid>\n\n"
                    "UUID можно получить из /v2stats"
                )
                return
            
            server_name = context.args[0]
            user_uuid = context.args[1]
            
            await update.message.reply_text("⏳ Удаляю пользователя...")
            
            server = self.manager.get_server(server_name)
            
            if not server:
                await update.message.reply_text(f"❌ Сервер {server_name} не найден")
                return
            
            if not server.connect():
                await update.message.reply_text("❌ Не удалось подключиться")
                return
            
            if server.remove_user(user_uuid):
                server.disconnect()
                await update.message.reply_text(f"✅ Пользователь {user_uuid} удалён")
            else:
                server.disconnect()
                await update.message.reply_text("❌ Ошибка удаления пользователя")
            
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка: {e}")
