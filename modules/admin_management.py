#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Admin Management System - Расширенная система управления администраторами
Включает полную видимость всех админов, добавленных через addadmin
"""

import logging
import sqlite3
import json
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler

logger = logging.getLogger(__name__)

# Состояния для диалога управления админами
(ADMIN_MENU, ADMIN_LIST, ADMIN_DETAILS, ADMIN_EDIT, ADMIN_SEARCH) = range(5)

class AdminManagementSystem:
    """Система управления администраторами с полной видимостью"""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._init_database()
    
    def _init_database(self):
        """Инициализация базы данных для управления админами"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Создаем таблицу для расширенного управления админами
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS admin_management (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER UNIQUE NOT NULL,
                    username TEXT,
                    full_name TEXT,
                    role TEXT DEFAULT 'staff',
                    permissions TEXT, -- JSON строка с правами
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
            
            # Создаем таблицу для отслеживания активности админов
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS admin_activity (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    admin_id INTEGER NOT NULL,
                    action TEXT NOT NULL,
                    details TEXT, -- JSON с деталями
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (admin_id) REFERENCES admin_management(user_id)
                )
            ''')
            
            # Создаем таблицу для отчетов по сменам
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS shift_reports (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    admin_id INTEGER NOT NULL,
                    club_name TEXT NOT NULL,
                    shift_date DATE NOT NULL,
                    shift_time TEXT NOT NULL, -- 'morning' or 'evening'
                    shift_data TEXT, -- JSON с данными смены
                    photo_file_id TEXT, -- Telegram file_id фото
                    photo_path TEXT, -- Локальный путь к фото
                    ocr_data TEXT, -- JSON с результатами OCR
                    ocr_verified BOOLEAN DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (admin_id) REFERENCES admin_management(user_id)
                )
            ''')
            
            conn.commit()
            conn.close()
            logger.info("✅ Admin Management Database initialized")
            
        except Exception as e:
            logger.error(f"❌ Error initializing admin management database: {e}")
    
    def sync_with_existing_admins(self):
        """Синхронизация с существующими админами из основной таблицы"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Получаем всех админов из основной таблицы
            cursor.execute('''
                SELECT user_id, username, full_name, added_by, is_active, created_at
                FROM admins WHERE is_active = 1
            ''')
            existing_admins = cursor.fetchall()
            
            # Добавляем их в таблицу управления
            for admin in existing_admins:
                user_id, username, full_name, added_by, is_active, created_at = admin
                
                # Проверяем, есть ли уже в таблице управления
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
    
    def get_all_admins(self, page: int = 1, per_page: int = 10) -> Tuple[List[Dict], int]:
        """Получить всех админов с пагинацией"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Получаем общее количество
            cursor.execute('SELECT COUNT(*) FROM admin_management WHERE is_active = 1')
            total = cursor.fetchone()[0]
            
            # Получаем страницу
            offset = (page - 1) * per_page
            cursor.execute('''
                SELECT user_id, username, full_name, role, added_at, last_seen, 
                       shift_count, last_shift_date, notes
                FROM admin_management 
                WHERE is_active = 1
                ORDER BY updated_at DESC
                LIMIT ? OFFSET ?
            ''', (per_page, offset))
            
            admins = []
            for row in cursor.fetchall():
                admins.append({
                    'user_id': row[0],
                    'username': row[1],
                    'full_name': row[2],
                    'role': row[3],
                    'added_at': row[4],
                    'last_seen': row[5],
                    'shift_count': row[6],
                    'last_shift_date': row[7],
                    'notes': row[8]
                })
            
            conn.close()
            return admins, total
            
        except Exception as e:
            logger.error(f"❌ Error getting all admins: {e}")
            return [], 0
    
    def get_admin_details(self, user_id: int) -> Optional[Dict]:
        """Получить детальную информацию об админе"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT user_id, username, full_name, role, permissions, added_by,
                       added_at, last_seen, is_active, notes, shift_count,
                       last_shift_date, created_at, updated_at
                FROM admin_management 
                WHERE user_id = ?
            ''', (user_id,))
            
            row = cursor.fetchone()
            if not row:
                conn.close()
                return None
            
            # Получаем последние активности
            cursor.execute('''
                SELECT action, details, timestamp
                FROM admin_activity 
                WHERE admin_id = ?
                ORDER BY timestamp DESC
                LIMIT 10
            ''', (user_id,))
            
            activities = []
            for activity_row in cursor.fetchall():
                activities.append({
                    'action': activity_row[0],
                    'details': json.loads(activity_row[1]) if activity_row[1] else None,
                    'timestamp': activity_row[2]
                })
            
            # Получаем последние смены
            cursor.execute('''
                SELECT club_name, shift_date, shift_time, created_at
                FROM shift_reports 
                WHERE admin_id = ?
                ORDER BY created_at DESC
                LIMIT 5
            ''', (user_id,))
            
            recent_shifts = []
            for shift_row in cursor.fetchall():
                recent_shifts.append({
                    'club_name': shift_row[0],
                    'shift_date': shift_row[1],
                    'shift_time': shift_row[2],
                    'created_at': shift_row[3]
                })
            
            conn.close()
            
            return {
                'user_id': row[0],
                'username': row[1],
                'full_name': row[2],
                'role': row[3],
                'permissions': json.loads(row[4]) if row[4] else None,
                'added_by': row[5],
                'added_at': row[6],
                'last_seen': row[7],
                'is_active': row[8],
                'notes': row[9],
                'shift_count': row[10],
                'last_shift_date': row[11],
                'created_at': row[12],
                'updated_at': row[13],
                'activities': activities,
                'recent_shifts': recent_shifts
            }
            
        except Exception as e:
            logger.error(f"❌ Error getting admin details: {user_id}: {e}")
            return None
    
    def update_admin_activity(self, user_id: int, action: str, details: Dict = None):
        """Обновить активность админа"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Обновляем last_seen
            cursor.execute('''
                UPDATE admin_management 
                SET last_seen = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP
                WHERE user_id = ?
            ''', (user_id,))
            
            # Добавляем запись активности
            cursor.execute('''
                INSERT INTO admin_activity (admin_id, action, details)
                VALUES (?, ?, ?)
            ''', (user_id, action, json.dumps(details) if details else None))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"❌ Error updating admin activity: {e}")
    
    def search_admins(self, query: str) -> List[Dict]:
        """Поиск админов по имени, username или ID"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Пытаемся парсить как ID
            try:
                user_id_query = int(query)
                cursor.execute('''
                    SELECT user_id, username, full_name, role, added_at, last_seen
                    FROM admin_management 
                    WHERE user_id = ? AND is_active = 1
                ''', (user_id_query,))
            except ValueError:
                cursor.execute('''
                    SELECT user_id, username, full_name, role, added_at, last_seen
                    FROM admin_management 
                    WHERE (username LIKE ? OR full_name LIKE ?) AND is_active = 1
                    ORDER BY updated_at DESC
                    LIMIT 20
                ''', (f'%{query}%', f'%{query}%'))
            
            admins = []
            for row in cursor.fetchall():
                admins.append({
                    'user_id': row[0],
                    'username': row[1],
                    'full_name': row[2],
                    'role': row[3],
                    'added_at': row[4],
                    'last_seen': row[5]
                })
            
            conn.close()
            return admins
            
        except Exception as e:
            logger.error(f"❌ Error searching admins: {e}")
            return []
    
    def get_admin_stats(self) -> Dict:
        """Получить статистику по админам"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Общая статистика
            cursor.execute('SELECT COUNT(*) FROM admin_management WHERE is_active = 1')
            total_admins = cursor.fetchone()[0]
            
            cursor.execute('SELECT COUNT(*) FROM admin_management WHERE is_active = 0')
            inactive_admins = cursor.fetchone()[0]
            
            # Статистика по ролям
            cursor.execute('''
                SELECT role, COUNT(*) 
                FROM admin_management 
                WHERE is_active = 1 
                GROUP BY role
            ''')
            roles_stats = dict(cursor.fetchall())
            
            # Активные за последние 7 дней
            cursor.execute('''
                SELECT COUNT(DISTINCT admin_id) 
                FROM admin_activity 
                WHERE timestamp > datetime('now', '-7 days')
            ''')
            active_last_week = cursor.fetchone()[0]
            
            # Статистика смен
            cursor.execute('SELECT COUNT(*) FROM shift_reports')
            total_shifts = cursor.fetchone()[0]
            
            cursor.execute('''
                SELECT COUNT(*) 
                FROM shift_reports 
                WHERE created_at > datetime('now', '-7 days')
            ''')
            shifts_last_week = cursor.fetchone()[0]
            
            conn.close()
            
            return {
                'total_admins': total_admins,
                'inactive_admins': inactive_admins,
                'roles_stats': roles_stats,
                'active_last_week': active_last_week,
                'total_shifts': total_shifts,
                'shifts_last_week': shifts_last_week
            }
            
        except Exception as e:
            logger.error(f"❌ Error getting admin stats: {e}")
            return {}


class AdminManagementCommands:
    """Команды для управления администраторами"""
    
    def __init__(self, admin_mgmt: AdminManagementSystem):
        self.admin_mgmt = admin_mgmt
    
    async def cmd_admin_management(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Главное меню управления админами"""
        user_id = update.effective_user.id
        
        # Проверяем права (только владелец и менеджеры)
        if not self._is_authorized(user_id):
            await update.message.reply_text("❌ У вас нет прав для управления администраторами")
            return
        
        keyboard = [
            [InlineKeyboardButton("👥 Список админов", callback_data="admin_list")],
            [InlineKeyboardButton("🔍 Поиск админа", callback_data="admin_search")],
            [InlineKeyboardButton("📊 Статистика", callback_data="admin_stats")],
            [InlineKeyboardButton("🔄 Синхронизация", callback_data="admin_sync")]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "👥 **Управление администраторами**\n\n"
            "Выберите действие:",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    
    async def admin_list_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показать список всех админов"""
        query = update.callback_query
        await query.answer()
        
        page = int(context.user_data.get('admin_page', 1))
        admins, total = self.admin_mgmt.get_all_admins(page=page)
        
        if not admins:
            await query.edit_message_text("❌ Администраторы не найдены")
            return
        
        text = f"👥 **Список администраторов** (стр. {page})\n\n"
        
        for admin in admins:
            username = f"@{admin['username']}" if admin['username'] else "Без username"
            full_name = admin['full_name'] or "Не указано"
            last_seen = admin['last_seen'] or "Никогда"
            shift_count = admin['shift_count'] or 0
            
            text += f"🆔 **ID:** {admin['user_id']}\n"
            text += f"👤 **Имя:** {full_name}\n"
            text += f"📱 **Username:** {username}\n"
            text += f"🎭 **Роль:** {admin['role']}\n"
            text += f"📅 **Добавлен:** {admin['added_at'][:10]}\n"
            text += f"👁 **Последний вход:** {last_seen[:16]}\n"
            text += f"📊 **Смен сдано:** {shift_count}\n"
            text += f"📋 **Последняя смена:** {admin['last_shift_date'] or 'Нет'}\n\n"
        
        # Кнопки навигации
        keyboard = []
        if page > 1:
            keyboard.append([InlineKeyboardButton("⬅️ Назад", callback_data=f"admin_list_{page-1}")])
        
        if page * 10 < total:
            keyboard.append([InlineKeyboardButton("➡️ Вперед", callback_data=f"admin_list_{page+1}")])
        
        keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="admin_menu")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
    
    async def admin_stats_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показать статистику по админам"""
        query = update.callback_query
        await query.answer()
        
        stats = self.admin_mgmt.get_admin_stats()
        
        text = "📊 **Статистика администраторов**\n\n"
        text += f"👥 **Всего админов:** {stats.get('total_admins', 0)}\n"
        text += f"❌ **Неактивных:** {stats.get('inactive_admins', 0)}\n"
        text += f"🔥 **Активных за неделю:** {stats.get('active_last_week', 0)}\n\n"
        
        text += "🎭 **По ролям:**\n"
        for role, count in stats.get('roles_stats', {}).items():
            text += f"  • {role}: {count}\n"
        
        text += f"\n📋 **Смены:**\n"
        text += f"  • Всего сдано: {stats.get('total_shifts', 0)}\n"
        text += f"  • За неделю: {stats.get('shifts_last_week', 0)}\n"
        
        keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="admin_menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
    
    async def admin_sync_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Синхронизация с существующими админами"""
        query = update.callback_query
        await query.answer()
        
        await query.edit_message_text("🔄 Синхронизация с существующими админами...")
        
        self.admin_mgmt.sync_with_existing_admins()
        
        await query.edit_message_text(
            "✅ Синхронизация завершена!\n\n"
            "Все админы из основной таблицы добавлены в систему управления.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="admin_menu")]])
        )
    
    def _is_authorized(self, user_id: int) -> bool:
        """Проверка прав доступа"""
        # Здесь должна быть проверка прав из основной системы админов
        # Пока возвращаем True для тестирования
        return True
