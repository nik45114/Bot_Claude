#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
V2Ray Bot Commands v2 - With REALITY Support
Команды для управления V2Ray с REALITY через Telegram бота
"""

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
import logging

logger = logging.getLogger(__name__)


class V2RayCommands:
    """Класс с командами V2Ray для бота (с REALITY)"""
    
    def __init__(self, manager, admin_manager, owner_id: int = None, owner_ids: list = None):
        self.manager = manager
        self.admin_manager = admin_manager
        # Support both single owner_id and list of owner_ids
        if owner_ids:
            self.owner_ids = owner_ids
        elif owner_id:
            self.owner_ids = [owner_id]
        else:
            self.owner_ids = []
    
    def is_owner(self, user_id: int) -> bool:
        """Проверка: является ли пользователь владельцем"""
        return user_id in self.owner_ids
    
    async def cmd_v2ray(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Главное меню V2Ray"""
        if not self.is_owner(update.effective_user.id):
            await update.message.reply_text("❌ Доступ запрещён")
            return
        
        text = """🔐 V2Ray Manager (REALITY)

━━━━━━━━━━━━━━━━━━━━━━━━━━━
📋 Системные требования:
━━━━━━━━━━━━━━━━━━━━━━━━━━━
  • ОС: Debian/Ubuntu Linux
  • Python: 3.8+
  • Требуется: SSH доступ с root

━━━━━━━━━━━━━━━━━━━━━━━━━━━
🌐 REALITY маскировка:
━━━━━━━━━━━━━━━━━━━━━━━━━━━
• По умолчанию: rutube.ru
• Доступны: youtube.com, yandex.ru"""

        keyboard = [
            [InlineKeyboardButton("📡 Серверы", callback_data="v2_servers")],
            [InlineKeyboardButton("👤 Пользователи", callback_data="v2_users")],
            [InlineKeyboardButton("📖 Справка по командам", callback_data="v2_help")],
            [InlineKeyboardButton("◀️ Главное меню", callback_data="main_menu")]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(text, reply_markup=reply_markup)
    
    async def cmd_v2add(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Добавление сервера"""
        if not self.is_owner(update.effective_user.id):
            logger.warning(f"Unauthorized v2add attempt by user {update.effective_user.id}")
            return
        
        try:
            logger.info(f"🔍 v2add called by {update.effective_user.id}")
            logger.info(f"📋 Args received: {context.args}")
            logger.info(f"📋 Args count: {len(context.args)}")
            
            if len(context.args) < 4:
                await update.message.reply_text(
                    "❌ Недостаточно параметров\n\n"
                    "Использование:\n"
                    "/v2add <имя> <host> <user> <pass> [sni]\n\n"
                    "Примеры:\n"
                    "/v2add ger 45.144.54.117 root MyPass123\n"
                    "/v2add ger 45.144.54.117 root MyPass123 youtube.com"
                )
                return
            
            name = context.args[0]
            host = context.args[1]
            username = context.args[2]
            password = context.args[3]
            sni = context.args[4] if len(context.args) > 4 else "rutube.ru"
            
            logger.info(f"📝 Parsed params:")
            logger.info(f"  • name: {name}")
            logger.info(f"  • host: {host}")
            logger.info(f"  • username: {username}")
            logger.info(f"  • password: {'*' * len(password)}")
            logger.info(f"  • sni: {sni}")
            
            await update.message.reply_text("⏳ Добавляю сервер...")
            
            logger.info(f"🔄 Calling manager.add_server...")
            result = self.manager.add_server(name, host, username, password, sni=sni)
            logger.info(f"📤 manager.add_server returned: {result}")
            
            if result:
                keyboard = [
                    [InlineKeyboardButton("🔧 Установить Xray", callback_data=f"v2setup_{name}")],
                    [InlineKeyboardButton("📊 Статистика", callback_data=f"v2stats_{name}")],
                    [InlineKeyboardButton("◀️ V2Ray меню", callback_data="v2ray")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                logger.info(f"✅ Server {name} added successfully")
                await update.message.reply_text(
                    f"✅ Сервер добавлен успешно!\n\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"🖥️ Сервер: {name}\n"
                    f"📍 Host: {host}\n"
                    f"👤 User: {username}\n"
                    f"🌐 SNI: {sni}\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━",
                    reply_markup=reply_markup
                )
            else:
                logger.error(f"❌ manager.add_server returned False for {name}")
                await update.message.reply_text(
                    "❌ Ошибка добавления сервера\n\n"
                    "Проверьте логи: journalctl -u club_assistant -n 50"
                )
        
        except Exception as e:
            logger.error(f"❌ Exception in cmd_v2add: {e}", exc_info=True)
            await update.message.reply_text(
                f"❌ Ошибка: {str(e)}\n\n"
                f"Тип ошибки: {type(e).__name__}"
            )
    
    async def cmd_v2list(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Список серверов"""
        if not self.is_owner(update.effective_user.id):
            return
        
        servers = self.manager.list_servers()
        
        if not servers:
            await update.message.reply_text("📭 Нет серверов")
            return
        
        text = "📡 Серверы V2Ray (REALITY):\n\n"
        
        for srv in servers:
            text += f"━━━━━━━━━━━━━━━━━━━━━━\n"
            text += f"🖥️ {srv['name']}\n"
            text += f"  📍 Host: `{srv['host']}`\n"
            text += f"  🔌 Port: {srv['port']}\n"
            text += f"  🌐 SNI: {srv['sni']}\n"
        
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
                    client_keys['short_id'],
                    client_keys.get('private_key', '')
                )
            
            if not server.deploy_config(config):
                await update.message.reply_text("❌ Ошибка применения конфигурации")
                server.disconnect()
                return
            
            server.disconnect()
            
            await update.message.reply_text(
                f"✅ Xray установлен на {server_name}!\n\n"
                f"🔐 Протокол: REALITY\n"
                f"🌐 Маскировка: {sni}\n\n"
                f"Теперь можешь добавлять пользователей:\n"
                f"/v2user {server_name} <user_id> [email]"
            )
            
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка: {e}")
    
    async def cmd_v2user(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Добавление пользователя на сервер"""
        if not self.is_owner(update.effective_user.id):
            return
        
        try:
            logger.info(f"🔍 v2user called with args: {context.args}")
            
            if len(context.args) < 3:
                await update.message.reply_text(
                    "Использование: /v2user <сервер> <user_id> <комментарий>\n\n"
                    "Пример:\n"
                    "/v2user ger 1 Nikita\n"
                    "/v2user fr 2 \"Vasya Pupkin\""
                )
                return
            
            server_name = context.args[0]
            user_id = context.args[1]
            comment = ' '.join(context.args[2:])  # Все остальное - комментарий
            
            logger.info(f"📝 Parsed: server={server_name}, user_id={user_id}, comment={comment}")
            
            await update.message.reply_text(f"⏳ Добавляю пользователя на {server_name}...")
            
            # Добавляем пользователя
            logger.info(f"🔄 Calling manager.add_user...")
            result = self.manager.add_user(server_name, user_id, comment)
            logger.info(f"📤 manager.add_user returned: {result}")
            
            if result and 'vless' in result:
                keyboard = [
                    [InlineKeyboardButton("👥 Список пользователей", callback_data=f"v2users_{server_name}")],
                    [InlineKeyboardButton("🔄 Изменить SNI", callback_data=f"v2changesni_{server_name}_{user_id}")],
                    [InlineKeyboardButton("◀️ Назад", callback_data=f"v2server_{server_name}")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await update.message.reply_text(
                    f"✅ Пользователь добавлен!\n\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"👤 ID: {user_id}\n"
                    f"📝 Комментарий: {comment}\n"
                    f"🖥️ Сервер: {server_name}\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
                    f"🔐 VLESS ссылка:\n"
                    f"<code>{result['vless']}</code>",
                    parse_mode='HTML',
                    reply_markup=reply_markup
                )
            else:
                logger.error(f"❌ manager.add_user failed or returned invalid data")
                await update.message.reply_text(
                    "❌ Ошибка добавления пользователя\n\n"
                    "Проверьте логи: journalctl -u club_assistant -n 100 --no-pager"
                )
        
        except Exception as e:
            logger.error(f"❌ cmd_v2user error: {e}", exc_info=True)
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
            
            status_emoji = "✅" if stats['running'] else "❌"
            
            text = f"📊 Статистика {server_name}\n\n"
            text += f"━━━━━━━━━━━━━━━━━━━━━━\n"
            text += f"{status_emoji} Статус: {'🟢 Работает' if stats['running'] else '🔴 Остановлен'}\n"
            text += f"📍 Host: {stats['host']}\n"
            text += f"🔌 Port: {stats['port']}\n"
            text += f"🔐 Protocol: {stats['protocol']}\n"
            text += f"🌐 SNI: {stats['sni']}\n"
            text += f"👥 Пользователей: {stats['users']}\n"
            text += f"━━━━━━━━━━━━━━━━━━━━━━"
            
            await update.message.reply_text(text)
            
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка: {e}")
    
    async def cmd_v2traffic(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Статистика трафика (placeholder)"""
        if not self.is_owner(update.effective_user.id):
            return
        
        await update.message.reply_text("⚠️ Функция в разработке")
    
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
