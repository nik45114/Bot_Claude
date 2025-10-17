#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
V2Ray Bot Commands v2 - With REALITY Support
Команды для управления V2Ray с REALITY через Telegram бота
"""

from telegram import Update
from telegram.ext import ContextTypes
import logging

logger = logging.getLogger(__name__)


class V2RayCommands:
    """Класс с командами V2Ray для бота (с REALITY)"""
    
    def __init__(self, manager, admin_manager, owner_id: int):
        self.manager = manager
        self.admin_manager = admin_manager
        self.owner_id = owner_id
    
    def is_owner(self, user_id: int) -> bool:
        """Проверка: является ли пользователь владельцем"""
        return user_id == self.owner_id
    
    async def cmd_v2ray(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Главное меню V2Ray"""
        if not self.is_owner(update.effective_user.id):
            await update.message.reply_text("❌ Доступ запрещён")
            return
        
        text = """🔐 *V2Ray Manager (REALITY)*

━━━━━━━━━━━━━━━━━━━━━━

📡 *Управление серверами:*
• `/v2add` - добавить сервер
• `/v2list` - список серверов
• `/v2setup` - установить Xray
• `/v2stats` - статистика сервера

👤 *Управление пользователями:*
• `/v2user` - добавить пользователя
• `/v2remove` - удалить пользователя

⚙️ *Настройки:*
• `/v2sni` - изменить маскировку

━━━━━━━━━━━━━━━━━━━━━━

💻 *Системные требования:*
• OS: Debian/Ubuntu Linux
• Root доступ по SSH
• Открытый порт 443

🌐 *REALITY маскировка:*
• По умолчанию: `rutube.ru`
• Доступно: `youtube.com`, `yandex.ru`, `google.com`

📝 *Пример использования:*
`/v2add main 45.144.54.117 root MyPass123`
`/v2setup main`
`/v2user main @username Вася`
`/v2sni main youtube.com`"""

        await update.message.reply_text(text, parse_mode='Markdown')
    
    async def cmd_v2add(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Добавление сервера: /v2add <имя> <host> <user> <pass> [sni]"""
        if not self.is_owner(update.effective_user.id):
            return
        
        try:
            if len(context.args) < 4:
                await update.message.reply_text(
                    "Использование: /v2add <имя> <host> <user> <pass> [sni]\n\n"
                    "Пример:\n"
                    "/v2add main 45.144.54.117 root MyPass123\n"
                    "/v2add main 45.144.54.117 root MyPass123 youtube.com"
                )
                return
            
            name = context.args[0]
            host = context.args[1]
            username = context.args[2]
            password = context.args[3]
            sni = context.args[4] if len(context.args) > 4 else "rutube.ru"
            
            await update.message.reply_text("⏳ Добавляю сервер...")
            
            if self.manager.add_server(name, host, username, password, sni=sni):
                text = f"✅ *Сервер '{name}' добавлен!*\n\n"
                text += "━━━━━━━━━━━━━━━━━━━━━━\n\n"
                text += f"🖥 *Host:* `{host}`\n"
                text += f"👤 *User:* `{username}`\n"
                text += f"🌐 *SNI:* `{sni}`\n\n"
                text += "━━━━━━━━━━━━━━━━━━━━━━\n\n"
                text += f"📝 *Следующий шаг:*\n"
                text += f"`/v2setup {name}`"
                await update.message.reply_text(text, parse_mode='Markdown')
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
        
        text = "📡 *Серверы V2Ray (REALITY):*\n\n"
        text += "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        
        server_texts = []
        for srv in servers:
            srv_text = f"🔹 *{srv['name']}*\n"
            srv_text += f"   🖥 Host: `{srv['host']}`\n"
            srv_text += f"   🔌 Port: `{srv['port']}`\n"
            srv_text += f"   🌐 SNI: `{srv['sni']}`"
            server_texts.append(srv_text)
        
        text += "\n\n".join(server_texts)
        
        await update.message.reply_text(text, parse_mode='Markdown')
    
    async def cmd_v2setup(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Установка Xray на сервер: /v2setup <имя>"""
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
            
            await update.message.reply_text("📥 Устанавливаю Xray (2-3 минуты)...")
            
            if not server.install_v2ray():
                await update.message.reply_text("❌ Ошибка установки Xray")
                server.disconnect()
                return
            
            await update.message.reply_text("⚙️ Создаю REALITY конфигурацию...")
            
            # Получаем SNI из базы
            server_keys = self.manager.get_server_keys(server_name)
            sni = server_keys.get('sni', 'rutube.ru')
            
            config = server.create_reality_config(port=443, sni=sni)
            
            if not config:
                await update.message.reply_text("❌ Ошибка создания конфигурации")
                server.disconnect()
                return
            
            # Сохраняем ключи в базу
            client_keys = config.get('_client_keys', {})
            if client_keys:
                self.manager.save_server_keys(
                    server_name,
                    client_keys['public_key'],
                    client_keys['short_id']
                )
            
            if not server.deploy_config(config):
                await update.message.reply_text("❌ Ошибка применения конфигурации")
                server.disconnect()
                return
            
            server.disconnect()
            
            text = f"✅ *Xray установлен на {server_name}!*\n\n"
            text += "━━━━━━━━━━━━━━━━━━━━━━\n\n"
            text += f"🔐 *Протокол:* `REALITY`\n"
            text += f"🌐 *Маскировка:* `{sni}`\n\n"
            text += "━━━━━━━━━━━━━━━━━━━━━━\n\n"
            text += "📝 *Добавить пользователя:*\n"
            text += f"`/v2user {server_name} <user_id> [email]`"
            
            await update.message.reply_text(text, parse_mode='Markdown')
            
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
            
            # Получаем SNI из базы
            server_keys = self.manager.get_server_keys(server_name)
            sni = server_keys.get('sni', 'rutube.ru')
            
            if not server.connect():
                await update.message.reply_text("❌ Не удалось подключиться")
                return
            
            vless_link = server.add_user_reality(user_id, email, sni)
            
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
            
            text = "✅ *Пользователь добавлен!*\n\n"
            text += "━━━━━━━━━━━━━━━━━━━━━━\n\n"
            text += f"👤 *ID:* `{user_id}`\n"
            text += f"📧 *Email:* {email or 'не указан'}\n"
            text += f"🔑 *UUID:* `{user_uuid}`\n"
            text += f"🌐 *SNI:* `{sni}`\n\n"
            text += "━━━━━━━━━━━━━━━━━━━━━━\n\n"
            text += "🔗 *VLESS ссылка (REALITY):*\n"
            text += f"`{vless_link}`"
            
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
            status_text = "Работает" if stats['running'] else "Остановлен"
            
            text = f"📊 *Статистика {server_name}*\n\n"
            text += "━━━━━━━━━━━━━━━━━━━━━━\n\n"
            text += f"{status_emoji} *Статус:* {status_text}\n"
            text += f"🖥 *Host:* `{stats['host']}`\n"
            text += f"🔌 *Port:* `{stats['port']}`\n"
            text += f"🔐 *Protocol:* `{stats['protocol']}`\n"
            text += f"🌐 *SNI:* `{stats['sni']}`\n"
            text += f"👥 *Пользователей:* `{stats['users']}`"
            
            await update.message.reply_text(text, parse_mode='Markdown')
            
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка: {e}")
    
    async def cmd_v2sni(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Изменение SNI: /v2sni <сервер> <сайт>"""
        if not self.is_owner(update.effective_user.id):
            return
        
        try:
            if len(context.args) < 2:
                await update.message.reply_text(
                    "Использование: /v2sni <сервер> <сайт>\n\n"
                    "Популярные сайты для маскировки:\n"
                    "• rutube.ru (по умолчанию)\n"
                    "• youtube.com\n"
                    "• google.com\n"
                    "• yandex.ru\n"
                    "• vk.com\n\n"
                    "Пример: /v2sni main youtube.com"
                )
                return
            
            server_name = context.args[0]
            new_sni = context.args[1]
            
            await update.message.reply_text(f"⏳ Изменяю маскировку на {new_sni}...")
            
            server = self.manager.get_server(server_name)
            
            if not server:
                await update.message.reply_text(f"❌ Сервер {server_name} не найден")
                return
            
            if not server.connect():
                await update.message.reply_text("❌ Не удалось подключиться")
                return
            
            if server.change_sni(new_sni):
                server.disconnect()
                
                # Обновляем SNI в базе
                import sqlite3
                conn = sqlite3.connect(self.manager.db_path)
                cursor = conn.cursor()
                cursor.execute('UPDATE v2ray_servers SET sni = ? WHERE name = ?', (new_sni, server_name))
                conn.commit()
                conn.close()
                
                await update.message.reply_text(
                    f"✅ Маскировка изменена на {new_sni}!\n\n"
                    f"⚠️ Все пользователи должны обновить свои ссылки.\n"
                    f"Создай новые: /v2user {server_name} <user_id>"
                )
            else:
                server.disconnect()
                await update.message.reply_text("❌ Ошибка изменения маскировки")
            
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
