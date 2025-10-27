#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Enhanced Admin & Shift Management - Улучшенная система с кнопочным интерфейсом
Отчеты видны только владельцу с возможностью расшарить админу
"""

import logging
import sqlite3
import json
import os
from datetime import datetime, date, timedelta
from typing import List, Dict, Optional, Tuple
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler

logger = logging.getLogger(__name__)

# Состояния для диалогов
(MAIN_MENU, ADMIN_MENU, SHIFT_MENU, REPORT_MENU, SHARE_MENU) = range(5)

class EnhancedAdminShiftSystem:
    """Улучшенная система управления админами и сменами с кнопочным интерфейсом"""
    
    def __init__(self, db_path: str, photo_storage_path: str = "/opt/club_assistant/photos"):
        self.db_path = db_path
        self.photo_storage_path = photo_storage_path
        self.owner_id = None  # Будет установлен при инициализации
        self._init_database()
        self._init_photo_storage()
    
    def set_owner_id(self, owner_id: int):
        """Установка ID владельца"""
        self.owner_id = owner_id
    
    def _init_database(self):
        """Инициализация базы данных"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Таблица для расширенного управления админами
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS admin_management (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER UNIQUE NOT NULL,
                    username TEXT,
                    full_name TEXT,
                    role TEXT DEFAULT 'staff',
                    permissions TEXT,
                    added_by INTEGER,
                    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_seen TIMESTAMP,
                    is_active BOOLEAN DEFAULT 1,
                    notes TEXT,
                    shift_count INTEGER DEFAULT 0,
                    last_shift_date DATE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Таблица для активности админов
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS admin_activity (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    admin_id INTEGER NOT NULL,
                    action TEXT NOT NULL,
                    details TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (admin_id) REFERENCES admin_management(user_id)
                )
            ''')
            
            # Таблица для контроля смен
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS shift_control (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    admin_id INTEGER NOT NULL,
                    club_name TEXT NOT NULL,
                    shift_date DATE NOT NULL,
                    shift_time TEXT NOT NULL,
                    
                    -- Данные смены
                    fact_cash REAL DEFAULT 0,
                    fact_card REAL DEFAULT 0,
                    qr_amount REAL DEFAULT 0,
                    card2_amount REAL DEFAULT 0,
                    safe_cash_end REAL DEFAULT 0,
                    box_cash_end REAL DEFAULT 0,
                    
                    -- Фото и OCR
                    photo_file_id TEXT,
                    photo_path TEXT,
                    ocr_text TEXT,
                    ocr_numbers TEXT,
                    ocr_verified BOOLEAN DEFAULT 0,
                    ocr_confidence REAL DEFAULT 0,
                    
                    -- Статус и проверка
                    status TEXT DEFAULT 'pending',
                    verified_by INTEGER,
                    verified_at TIMESTAMP,
                    verification_notes TEXT,
                    
                    -- Права доступа
                    visible_to_owner_only BOOLEAN DEFAULT 1,
                    shared_with_admins TEXT, -- JSON список ID админов
                    
                    -- Метаданные
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    
                    FOREIGN KEY (admin_id) REFERENCES admin_management(user_id),
                    FOREIGN KEY (verified_by) REFERENCES admin_management(user_id)
                )
            ''')
            
            # Таблица для истории изменений статуса
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS shift_status_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    shift_id INTEGER NOT NULL,
                    old_status TEXT,
                    new_status TEXT,
                    changed_by INTEGER NOT NULL,
                    reason TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (shift_id) REFERENCES shift_control(id),
                    FOREIGN KEY (changed_by) REFERENCES admin_management(user_id)
                )
            ''')
            
            # Создаем индексы
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_admin_management_user_id ON admin_management(user_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_shift_control_admin ON shift_control(admin_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_shift_control_date ON shift_control(shift_date)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_shift_control_status ON shift_control(status)')
            
            conn.commit()
            conn.close()
            logger.info("✅ Enhanced Admin & Shift Management Database initialized")
            
        except Exception as e:
            logger.error(f"❌ Error initializing database: {e}")
    
    def _init_photo_storage(self):
        """Инициализация директории для фото"""
        try:
            os.makedirs(self.photo_storage_path, exist_ok=True)
            logger.info(f"✅ Photo storage initialized: {self.photo_storage_path}")
        except Exception as e:
            logger.error(f"❌ Error initializing photo storage: {e}")
    
    def sync_with_existing_admins(self):
        """Синхронизация с существующими админами"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT user_id, username, full_name, added_by, is_active, created_at
                FROM admins WHERE is_active = 1
            ''')
            existing_admins = cursor.fetchall()
            
            for admin in existing_admins:
                user_id, username, full_name, added_by, is_active, created_at = admin
                
                cursor.execute('SELECT user_id FROM admin_management WHERE user_id = ?', (user_id,))
                if not cursor.fetchone():
                    cursor.execute('''
                        INSERT INTO admin_management 
                        (user_id, username, full_name, added_by, is_active, created_at)
                        VALUES (?, ?, ?, ?, ?, ?)
                    ''', (user_id, username, full_name, added_by, is_active, created_at))
            
            conn.commit()
            conn.close()
            logger.info(f"✅ Synced {len(existing_admins)} existing admins")
            
        except Exception as e:
            logger.error(f"❌ Error syncing existing admins: {e}")
    
    def is_owner(self, user_id: int) -> bool:
        """Проверка, является ли пользователь владельцем"""
        return user_id == self.owner_id
    
    def is_admin(self, user_id: int) -> bool:
        """Проверка, является ли пользователь админом"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('SELECT COUNT(*) FROM admin_management WHERE user_id = ? AND is_active = 1', (user_id,))
            count = cursor.fetchone()[0]
            conn.close()
            return count > 0
        except:
            return False
    
    def get_accessible_reports(self, user_id: int) -> List[Dict]:
        """Получить отчеты доступные пользователю"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            if self.is_owner(user_id):
                # Владелец видит все отчеты
                cursor.execute('''
                    SELECT id, admin_id, club_name, shift_date, shift_time, status,
                           fact_cash, fact_card, qr_amount, card2_amount, safe_cash_end, box_cash_end,
                           photo_path, ocr_verified, ocr_confidence, created_at, visible_to_owner_only, shared_with_admins
                    FROM shift_control 
                    ORDER BY created_at DESC
                    LIMIT 50
                ''')
            else:
                # Админы видят только расшаренные отчеты
                cursor.execute('''
                    SELECT id, admin_id, club_name, shift_date, shift_time, status,
                           fact_cash, fact_card, qr_amount, card2_amount, safe_cash_end, box_cash_end,
                           photo_path, ocr_verified, ocr_confidence, created_at, visible_to_owner_only, shared_with_admins
                    FROM shift_control 
                    WHERE visible_to_owner_only = 0 OR shared_with_admins LIKE ?
                    ORDER BY created_at DESC
                    LIMIT 50
                ''', (f'%{user_id}%',))
            
            reports = []
            for row in cursor.fetchall():
                shared_with = json.loads(row[17]) if row[17] else []
                reports.append({
                    'id': row[0],
                    'admin_id': row[1],
                    'club_name': row[2],
                    'shift_date': row[3],
                    'shift_time': row[4],
                    'status': row[5],
                    'fact_cash': row[6],
                    'fact_card': row[7],
                    'qr_amount': row[8],
                    'card2_amount': row[9],
                    'safe_cash_end': row[10],
                    'box_cash_end': row[11],
                    'photo_path': row[12],
                    'ocr_verified': row[13],
                    'ocr_confidence': row[14],
                    'created_at': row[15],
                    'visible_to_owner_only': row[16],
                    'shared_with_admins': shared_with
                })
            
            conn.close()
            return reports
            
        except Exception as e:
            logger.error(f"❌ Error getting accessible reports: {e}")
            return []
    
    def share_report_with_admin(self, report_id: int, admin_id: int, shared_by: int) -> bool:
        """Расшарить отчет с админом"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Получаем текущие настройки расшаривания
            cursor.execute('SELECT shared_with_admins FROM shift_control WHERE id = ?', (report_id,))
            row = cursor.fetchone()
            
            if not row:
                conn.close()
                return False
            
            shared_with = json.loads(row[0]) if row[0] else []
            
            if admin_id not in shared_with:
                shared_with.append(admin_id)
                
                cursor.execute('''
                    UPDATE shift_control 
                    SET shared_with_admins = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                ''', (json.dumps(shared_with), report_id))
                
                # Записываем в историю
                cursor.execute('''
                    INSERT INTO shift_status_history 
                    (shift_id, old_status, new_status, changed_by, reason)
                    VALUES (?, ?, ?, ?, ?)
                ''', (report_id, 'private', 'shared', shared_by, f'Shared with admin {admin_id}'))
                
                conn.commit()
            
            conn.close()
            return True
            
        except Exception as e:
            logger.error(f"❌ Error sharing report: {e}")
            return False
    
    def unshare_report_with_admin(self, report_id: int, admin_id: int, unshared_by: int) -> bool:
        """Убрать доступ к отчету у админа"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('SELECT shared_with_admins FROM shift_control WHERE id = ?', (report_id,))
            row = cursor.fetchone()
            
            if not row:
                conn.close()
                return False
            
            shared_with = json.loads(row[0]) if row[0] else []
            
            if admin_id in shared_with:
                shared_with.remove(admin_id)
                
                cursor.execute('''
                    UPDATE shift_control 
                    SET shared_with_admins = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                ''', (json.dumps(shared_with), report_id))
                
                # Записываем в историю
                cursor.execute('''
                    INSERT INTO shift_status_history 
                    (shift_id, old_status, new_status, changed_by, reason)
                    VALUES (?, ?, ?, ?, ?)
                ''', (report_id, 'shared', 'private', unshared_by, f'Unshared with admin {admin_id}'))
                
                conn.commit()
            
            conn.close()
            return True
            
        except Exception as e:
            logger.error(f"❌ Error unsharing report: {e}")
            return False
    
    def get_admins_list(self) -> List[Dict]:
        """Получить список админов"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT user_id, username, full_name, role, added_at, last_seen, shift_count
                FROM admin_management 
                WHERE is_active = 1
                ORDER BY updated_at DESC
            ''')
            
            admins = []
            for row in cursor.fetchall():
                admins.append({
                    'user_id': row[0],
                    'username': row[1],
                    'full_name': row[2],
                    'role': row[3],
                    'added_at': row[4],
                    'last_seen': row[5],
                    'shift_count': row[6]
                })
            
            conn.close()
            return admins
            
        except Exception as e:
            logger.error(f"❌ Error getting admins list: {e}")
            return []


class EnhancedAdminShiftCommands:
    """Команды для улучшенной системы управления"""
    
    def __init__(self, system: EnhancedAdminShiftSystem):
        self.system = system
    
    async def cmd_admin_panel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Главная команда для открытия админ-панели"""
        user_id = update.effective_user.id
        
        if not self.system.is_admin(user_id) and not self.system.is_owner(user_id):
            await update.message.reply_text("❌ У вас нет прав доступа к админ-панели")
            return
        
        await self.show_main_menu(update, context)
    
    async def show_main_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показать главное меню"""
        user_id = update.effective_user.id
        is_owner = self.system.is_owner(user_id)
        
        keyboard = []
        
        if is_owner:
            keyboard.append([InlineKeyboardButton("👥 Управление админами", callback_data="admin_mgmt")])
            keyboard.append([InlineKeyboardButton("📋 Отчеты смен", callback_data="shift_reports")])
            keyboard.append([InlineKeyboardButton("📊 Статистика", callback_data="system_stats")])
            keyboard.append([InlineKeyboardButton("🔄 Обновления", callback_data="system_update")])
        else:
            keyboard.append([InlineKeyboardButton("📋 Мои отчеты", callback_data="my_reports")])
            keyboard.append([InlineKeyboardButton("📊 Статистика", callback_data="my_stats")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        text = "🔧 **Админ-панель**\n\n"
        if is_owner:
            text += "Выберите раздел для управления:"
        else:
            text += "Доступные функции:"
        
        if update.callback_query:
            await update.callback_query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
        else:
            await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='Markdown')
    
    async def admin_mgmt_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Меню управления админами"""
        query = update.callback_query
        await query.answer()
        
        keyboard = [
            [InlineKeyboardButton("👥 Список админов", callback_data="admin_list")],
            [InlineKeyboardButton("🔍 Поиск админа", callback_data="admin_search")],
            [InlineKeyboardButton("📊 Статистика админов", callback_data="admin_stats")],
            [InlineKeyboardButton("🔄 Синхронизация", callback_data="admin_sync")],
            [InlineKeyboardButton("🔙 Назад", callback_data="main_menu")]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "👥 **Управление администраторами**\n\n"
            "Выберите действие:",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    
    async def shift_reports_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Меню отчетов смен"""
        query = update.callback_query
        await query.answer()
        
        keyboard = [
            [InlineKeyboardButton("📋 Все отчеты", callback_data="reports_all")],
            [InlineKeyboardButton("⏳ Ожидают проверки", callback_data="reports_pending")],
            [InlineKeyboardButton("✅ Проверенные", callback_data="reports_verified")],
            [InlineKeyboardButton("🔍 Поиск отчета", callback_data="reports_search")],
            [InlineKeyboardButton("📊 Статистика смен", callback_data="shift_stats")],
            [InlineKeyboardButton("🔙 Назад", callback_data="main_menu")]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "📋 **Отчеты смен**\n\n"
            "Выберите действие:",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    
    async def reports_all_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показать все отчеты"""
        query = update.callback_query
        await query.answer()
        
        user_id = update.effective_user.id
        reports = self.system.get_accessible_reports(user_id)
        
        if not reports:
            await query.edit_message_text(
                "❌ Отчеты не найдены",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="shift_reports")]])
            )
            return
        
        # Показываем первые 10 отчетов
        text = "📋 **Все отчеты**\n\n"
        
        for i, report in enumerate(reports[:10]):
            status_emoji = "✅" if report['status'] == 'verified' else "⏳" if report['status'] == 'pending' else "❌"
            ocr_emoji = "🔍" if report['ocr_verified'] else "❌"
            private_emoji = "🔒" if report['visible_to_owner_only'] else "🔓"
            
            text += f"{status_emoji} **#{report['id']}** {private_emoji}\n"
            text += f"🏢 {report['club_name']} | 📅 {report['shift_date']} | ⏰ {report['shift_time']}\n"
            text += f"💰 Нал: {report['fact_cash']:,.0f} ₽ | 💳 Карта: {report['fact_card']:,.0f} ₽\n"
            text += f"🔍 OCR: {ocr_emoji} | 📸 {'Есть' if report['photo_path'] else 'Нет'}\n\n"
        
        if len(reports) > 10:
            text += f"... и еще {len(reports) - 10} отчетов\n\n"
        
        keyboard = []
        for report in reports[:5]:  # Кнопки для первых 5 отчетов
            keyboard.append([InlineKeyboardButton(
                f"📋 Отчет #{report['id']} - {report['club_name']}", 
                callback_data=f"report_detail_{report['id']}"
            )])
        
        keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="shift_reports")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
    
    async def report_detail_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Детали отчета"""
        query = update.callback_query
        await query.answer()
        
        report_id = int(query.data.split('_')[-1])
        user_id = update.effective_user.id
        
        # Получаем детали отчета
        reports = self.system.get_accessible_reports(user_id)
        report = next((r for r in reports if r['id'] == report_id), None)
        
        if not report:
            await query.edit_message_text("❌ Отчет не найден")
            return
        
        status_emoji = "✅" if report['status'] == 'verified' else "⏳" if report['status'] == 'pending' else "❌"
        ocr_emoji = "🔍" if report['ocr_verified'] else "❌"
        private_emoji = "🔒" if report['visible_to_owner_only'] else "🔓"
        
        text = f"📋 **Отчет #{report['id']}** {private_emoji}\n\n"
        text += f"🏢 **Клуб:** {report['club_name']}\n"
        text += f"📅 **Дата:** {report['shift_date']}\n"
        text += f"⏰ **Время:** {report['shift_time']}\n"
        text += f"📊 **Статус:** {status_emoji} {report['status']}\n\n"
        
        text += f"💰 **Выручка:**\n"
        text += f"  • Наличные: {report['fact_cash']:,.0f} ₽\n"
        text += f"  • Карта: {report['fact_card']:,.0f} ₽\n"
        text += f"  • QR: {report['qr_amount']:,.0f} ₽\n"
        text += f"  • Карта 2: {report['card2_amount']:,.0f} ₽\n\n"
        
        text += f"💵 **Кассы:**\n"
        text += f"  • Сейф: {report['safe_cash_end']:,.0f} ₽\n"
        text += f"  • Коробка: {report['box_cash_end']:,.0f} ₽\n\n"
        
        text += f"🔍 **OCR:** {ocr_emoji} ({report['ocr_confidence']:.1%})\n"
        text += f"📸 **Фото:** {'Есть' if report['photo_path'] else 'Нет'}\n"
        text += f"📅 **Создан:** {report['created_at'][:16]}\n"
        
        keyboard = []
        
        if self.system.is_owner(user_id):
            keyboard.append([InlineKeyboardButton("✅ Подтвердить", callback_data=f"verify_report_{report_id}")])
            keyboard.append([InlineKeyboardButton("❌ Отклонить", callback_data=f"reject_report_{report_id}")])
            
            if report['visible_to_owner_only']:
                keyboard.append([InlineKeyboardButton("🔓 Расшарить", callback_data=f"share_report_{report_id}")])
            else:
                keyboard.append([InlineKeyboardButton("🔒 Сделать приватным", callback_data=f"unshare_report_{report_id}")])
        
        keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="reports_all")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
    
    async def share_report_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Расшарить отчет с админами"""
        query = update.callback_query
        await query.answer()
        
        report_id = int(query.data.split('_')[-1])
        
        # Получаем список админов
        admins = self.system.get_admins_list()
        
        if not admins:
            await query.edit_message_text("❌ Админы не найдены")
            return
        
        keyboard = []
        for admin in admins[:10]:  # Показываем первых 10 админов
            username = f"@{admin['username']}" if admin['username'] else "Без username"
            keyboard.append([InlineKeyboardButton(
                f"👤 {admin['full_name'] or username}",
                callback_data=f"share_with_{admin['user_id']}_{report_id}"
            )])
        
        keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data=f"report_detail_{report_id}")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "🔓 **Расшарить отчет с админом**\n\n"
            "Выберите админа для предоставления доступа к отчету:",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    
    async def share_with_admin_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Расшарить отчет с конкретным админом"""
        query = update.callback_query
        await query.answer()
        
        parts = query.data.split('_')
        admin_id = int(parts[2])
        report_id = int(parts[3])
        
        success = self.system.share_report_with_admin(report_id, admin_id, update.effective_user.id)
        
        if success:
            await query.edit_message_text(
                f"✅ Отчет #{report_id} расшарен с админом {admin_id}",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data=f"report_detail_{report_id}")]])
            )
        else:
            await query.edit_message_text(
                f"❌ Ошибка при расшаривании отчета",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data=f"report_detail_{report_id}")]])
            )
    
    async def main_menu_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Возврат в главное меню"""
        query = update.callback_query
        await query.answer()
        
        await self.show_main_menu(update, context)
    
    async def admin_list_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Список админов"""
        query = update.callback_query
        await query.answer()
        
        admins = self.system.get_admins_list()
        
        if not admins:
            await query.edit_message_text("❌ Админы не найдены")
            return
        
        text = "👥 **Список администраторов**\n\n"
        
        for admin in admins[:10]:
            username = f"@{admin['username']}" if admin['username'] else "Без username"
            last_seen = admin['last_seen'] or "Никогда"
            
            text += f"🆔 **ID:** {admin['user_id']}\n"
            text += f"👤 **Имя:** {admin['full_name'] or 'Не указано'}\n"
            text += f"📱 **Username:** {username}\n"
            text += f"🎭 **Роль:** {admin['role']}\n"
            text += f"📅 **Добавлен:** {admin['added_at'][:10]}\n"
            text += f"👁 **Последний вход:** {last_seen[:16]}\n"
            text += f"📊 **Смен сдано:** {admin['shift_count'] or 0}\n\n"
        
        keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="admin_mgmt")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
    
    async def system_stats_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Статистика системы"""
        query = update.callback_query
        await query.answer()
        
        try:
            conn = sqlite3.connect(self.system.db_path)
            cursor = conn.cursor()
            
            # Статистика админов
            cursor.execute('SELECT COUNT(*) FROM admin_management WHERE is_active = 1')
            total_admins = cursor.fetchone()[0]
            
            cursor.execute('SELECT COUNT(*) FROM admin_management WHERE last_seen > datetime("now", "-7 days")')
            active_admins = cursor.fetchone()[0]
            
            # Статистика смен
            cursor.execute('SELECT COUNT(*) FROM shift_control')
            total_shifts = cursor.fetchone()[0]
            
            cursor.execute('SELECT COUNT(*) FROM shift_control WHERE status = "verified"')
            verified_shifts = cursor.fetchone()[0]
            
            cursor.execute('SELECT COUNT(*) FROM shift_control WHERE status = "pending"')
            pending_shifts = cursor.fetchone()[0]
            
            cursor.execute('SELECT COUNT(*) FROM shift_control WHERE ocr_verified = 1')
            ocr_verified_shifts = cursor.fetchone()[0]
            
            conn.close()
            
            text = "📊 **Статистика системы**\n\n"
            text += f"👥 **Админы:**\n"
            text += f"  • Всего: {total_admins}\n"
            text += f"  • Активных за неделю: {active_admins}\n\n"
            
            text += f"📋 **Смены:**\n"
            text += f"  • Всего: {total_shifts}\n"
            text += f"  • Проверено: {verified_shifts}\n"
            text += f"  • Ожидает: {pending_shifts}\n"
            text += f"  • OCR проверено: {ocr_verified_shifts}\n"
            
            keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="main_menu")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
            
        except Exception as e:
            logger.error(f"❌ Error getting system stats: {e}")
            await query.edit_message_text("❌ Ошибка получения статистики")


def register_enhanced_admin_shift_management(application, config: dict, db_path: str, owner_id: int):
    """Регистрация улучшенной системы управления админами и сменами"""
    try:
        # Создаем систему
        system = EnhancedAdminShiftSystem(db_path)
        system.set_owner_id(owner_id)
        system.sync_with_existing_admins()
        
        # Создаем команды
        commands = EnhancedAdminShiftCommands(system)
        
        # Регистрируем обработчики
        application.add_handler(CommandHandler("adminpanel", commands.cmd_admin_panel))
        
        # Callback handlers
        application.add_handler(CallbackQueryHandler(commands.admin_mgmt_callback, pattern="^admin_mgmt$"))
        application.add_handler(CallbackQueryHandler(commands.shift_reports_callback, pattern="^shift_reports$"))
        application.add_handler(CallbackQueryHandler(commands.reports_all_callback, pattern="^reports_all$"))
        application.add_handler(CallbackQueryHandler(commands.report_detail_callback, pattern="^report_detail_"))
        application.add_handler(CallbackQueryHandler(commands.share_report_callback, pattern="^share_report_"))
        application.add_handler(CallbackQueryHandler(commands.share_with_admin_callback, pattern="^share_with_"))
        application.add_handler(CallbackQueryHandler(commands.main_menu_callback, pattern="^main_menu$"))
        application.add_handler(CallbackQueryHandler(commands.admin_list_callback, pattern="^admin_list$"))
        application.add_handler(CallbackQueryHandler(commands.system_stats_callback, pattern="^system_stats$"))
        
        logger.info("✅ Enhanced Admin & Shift Management system registered")
        return system
        
    except Exception as e:
        logger.error(f"❌ Error registering Enhanced Admin & Shift Management: {e}")
        return None
