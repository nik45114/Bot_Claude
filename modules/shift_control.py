#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Shift Control System - Система контроля и отчётов за сдачами смен
Включает прикрепление фото и OCR для проверки цифр
"""

import logging
import sqlite3
import json
import os
import base64
from datetime import datetime, date, timedelta
from typing import List, Dict, Optional, Tuple
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler

logger = logging.getLogger(__name__)

# Состояния для диалога сдачи смены
(SHIFT_MENU, SHIFT_CLUB_SELECT, SHIFT_DATA_INPUT, SHIFT_PHOTO_UPLOAD, 
 SHIFT_OCR_VERIFICATION, SHIFT_CONFIRMATION) = range(6)

class ShiftControlSystem:
    """Система контроля смен с фото и OCR"""
    
    def __init__(self, db_path: str, photo_storage_path: str = "/opt/club_assistant/photos"):
        self.db_path = db_path
        self.photo_storage_path = photo_storage_path
        self._init_database()
        self._init_photo_storage()
    
    def _init_database(self):
        """Инициализация базы данных для контроля смен"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Таблица для детальных отчетов по сменам
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS shift_control (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    admin_id INTEGER NOT NULL,
                    club_name TEXT NOT NULL,
                    shift_date DATE NOT NULL,
                    shift_time TEXT NOT NULL, -- 'morning' or 'evening'
                    
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
                    ocr_numbers TEXT, -- JSON с извлеченными числами
                    ocr_verified BOOLEAN DEFAULT 0,
                    ocr_confidence REAL DEFAULT 0,
                    
                    -- Статус и проверка
                    status TEXT DEFAULT 'pending', -- pending, verified, rejected
                    verified_by INTEGER,
                    verified_at TIMESTAMP,
                    verification_notes TEXT,
                    
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
            
            # Индексы для производительности
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_shift_control_admin ON shift_control(admin_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_shift_control_date ON shift_control(shift_date)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_shift_control_status ON shift_control(status)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_shift_control_club ON shift_control(club_name)')
            
            conn.commit()
            conn.close()
            logger.info("✅ Shift Control Database initialized")
            
        except Exception as e:
            logger.error(f"❌ Error initializing shift control database: {e}")
    
    def _init_photo_storage(self):
        """Инициализация директории для хранения фото"""
        try:
            os.makedirs(self.photo_storage_path, exist_ok=True)
            logger.info(f"✅ Photo storage initialized: {self.photo_storage_path}")
        except Exception as e:
            logger.error(f"❌ Error initializing photo storage: {e}")
    
    async def save_shift_photo(self, file_id: str, admin_id: int, club_name: str, 
                              shift_date: date, shift_time: str, bot) -> Optional[str]:
        """Сохранение фото смены"""
        try:
            # Получаем файл от Telegram
            file = await bot.get_file(file_id)
            
            # Создаем имя файла
            filename = f"{admin_id}_{club_name}_{shift_date}_{shift_time}_{datetime.now().strftime('%H%M%S')}.jpg"
            file_path = os.path.join(self.photo_storage_path, filename)
            
            # Скачиваем файл
            await file.download_to_drive(file_path)
            
            logger.info(f"✅ Photo saved: {file_path}")
            return file_path
            
        except Exception as e:
            logger.error(f"❌ Error saving shift photo: {e}")
            return None
    
    def extract_numbers_from_photo(self, photo_path: str) -> Dict:
        """Извлечение чисел из фото с помощью OCR"""
        try:
            # Здесь будет интеграция с OCR (Tesseract или другой)
            # Пока возвращаем заглушку
            
            import cv2
            import numpy as np
            
            # Загружаем изображение
            image = cv2.imread(photo_path)
            if image is None:
                return {'error': 'Could not load image'}
            
            # Простая обработка изображения для OCR
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            
            # Применяем пороговую обработку
            _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            
            # Здесь должен быть вызов OCR библиотеки
            # Пока возвращаем заглушку с примерными данными
            
            extracted_numbers = {
                'fact_cash': None,
                'fact_card': None,
                'qr_amount': None,
                'card2_amount': None,
                'safe_cash_end': None,
                'box_cash_end': None,
                'confidence': 0.0,
                'raw_text': '',
                'processing_time': 0.0
            }
            
            # Попытка извлечь числа из изображения
            # Это упрощенная версия - в реальности нужен полноценный OCR
            
            return extracted_numbers
            
        except Exception as e:
            logger.error(f"❌ Error extracting numbers from photo: {e}")
            return {'error': str(e)}
    
    def create_shift_report(self, admin_id: int, club_name: str, shift_date: date, 
                           shift_time: str, shift_data: Dict, photo_path: str = None,
                           ocr_data: Dict = None) -> Optional[int]:
        """Создание отчета о смене"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO shift_control 
                (admin_id, club_name, shift_date, shift_time, fact_cash, fact_card,
                 qr_amount, card2_amount, safe_cash_end, box_cash_end, photo_path,
                 ocr_text, ocr_numbers, ocr_verified, ocr_confidence)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                admin_id, club_name, shift_date, shift_time,
                shift_data.get('fact_cash', 0),
                shift_data.get('fact_card', 0),
                shift_data.get('qr_amount', 0),
                shift_data.get('card2_amount', 0),
                shift_data.get('safe_cash_end', 0),
                shift_data.get('box_cash_end', 0),
                photo_path,
                ocr_data.get('raw_text', '') if ocr_data else '',
                json.dumps(ocr_data) if ocr_data else None,
                ocr_data.get('confidence', 0) > 0.8 if ocr_data else False,
                ocr_data.get('confidence', 0) if ocr_data else 0
            ))
            
            shift_id = cursor.lastrowid
            
            # Обновляем статистику админа
            cursor.execute('''
                UPDATE admin_management 
                SET shift_count = shift_count + 1, 
                    last_shift_date = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE user_id = ?
            ''', (shift_date, admin_id))
            
            conn.commit()
            conn.close()
            
            logger.info(f"✅ Shift report created: ID {shift_id}")
            return shift_id
            
        except Exception as e:
            logger.error(f"❌ Error creating shift report: {e}")
            return None
    
    def get_shift_reports(self, admin_id: int = None, club_name: str = None,
                         status: str = None, page: int = 1, per_page: int = 10) -> Tuple[List[Dict], int]:
        """Получить отчеты о сменах с фильтрацией"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Строим WHERE условия
            where_conditions = []
            params = []
            
            if admin_id:
                where_conditions.append('admin_id = ?')
                params.append(admin_id)
            
            if club_name:
                where_conditions.append('club_name = ?')
                params.append(club_name)
            
            if status:
                where_conditions.append('status = ?')
                params.append(status)
            
            where_sql = ' AND '.join(where_conditions) if where_conditions else '1=1'
            
            # Получаем общее количество
            cursor.execute(f'SELECT COUNT(*) FROM shift_control WHERE {where_sql}', params)
            total = cursor.fetchone()[0]
            
            # Получаем страницу
            offset = (page - 1) * per_page
            cursor.execute(f'''
                SELECT id, admin_id, club_name, shift_date, shift_time, status,
                       fact_cash, fact_card, qr_amount, card2_amount, safe_cash_end, box_cash_end,
                       photo_path, ocr_verified, ocr_confidence, created_at
                FROM shift_control 
                WHERE {where_sql}
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?
            ''', params + [per_page, offset])
            
            reports = []
            for row in cursor.fetchall():
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
                    'created_at': row[15]
                })
            
            conn.close()
            return reports, total
            
        except Exception as e:
            logger.error(f"❌ Error getting shift reports: {e}")
            return [], 0
    
    def verify_shift_report(self, shift_id: int, verified_by: int, 
                           status: str, notes: str = None) -> bool:
        """Верификация отчета о смене"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Получаем старый статус
            cursor.execute('SELECT status FROM shift_control WHERE id = ?', (shift_id,))
            old_status = cursor.fetchone()[0]
            
            # Обновляем статус
            cursor.execute('''
                UPDATE shift_control 
                SET status = ?, verified_by = ?, verified_at = CURRENT_TIMESTAMP,
                    verification_notes = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (status, verified_by, notes, shift_id))
            
            # Записываем в историю
            cursor.execute('''
                INSERT INTO shift_status_history 
                (shift_id, old_status, new_status, changed_by, reason)
                VALUES (?, ?, ?, ?, ?)
            ''', (shift_id, old_status, status, verified_by, notes))
            
            conn.commit()
            conn.close()
            
            logger.info(f"✅ Shift report {shift_id} verified: {status}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error verifying shift report: {e}")
            return False
    
    def get_shift_statistics(self) -> Dict:
        """Получить статистику по сменам"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Общая статистика
            cursor.execute('SELECT COUNT(*) FROM shift_control')
            total_shifts = cursor.fetchone()[0]
            
            cursor.execute('SELECT COUNT(*) FROM shift_control WHERE status = "verified"')
            verified_shifts = cursor.fetchone()[0]
            
            cursor.execute('SELECT COUNT(*) FROM shift_control WHERE status = "pending"')
            pending_shifts = cursor.fetchone()[0]
            
            cursor.execute('SELECT COUNT(*) FROM shift_control WHERE ocr_verified = 1')
            ocr_verified_shifts = cursor.fetchone()[0]
            
            # Статистика по клубам
            cursor.execute('''
                SELECT club_name, COUNT(*) 
                FROM shift_control 
                GROUP BY club_name 
                ORDER BY COUNT(*) DESC
            ''')
            clubs_stats = dict(cursor.fetchall())
            
            # Статистика по дням недели
            cursor.execute('''
                SELECT strftime('%w', shift_date) as day_of_week, COUNT(*) 
                FROM shift_control 
                GROUP BY day_of_week
            ''')
            days_stats = dict(cursor.fetchall())
            
            # Средние суммы
            cursor.execute('''
                SELECT AVG(fact_cash), AVG(fact_card), AVG(safe_cash_end), AVG(box_cash_end)
                FROM shift_control 
                WHERE status = "verified"
            ''')
            avg_row = cursor.fetchone()
            avg_amounts = {
                'fact_cash': avg_row[0] or 0,
                'fact_card': avg_row[1] or 0,
                'safe_cash_end': avg_row[2] or 0,
                'box_cash_end': avg_row[3] or 0
            }
            
            conn.close()
            
            return {
                'total_shifts': total_shifts,
                'verified_shifts': verified_shifts,
                'pending_shifts': pending_shifts,
                'ocr_verified_shifts': ocr_verified_shifts,
                'clubs_stats': clubs_stats,
                'days_stats': days_stats,
                'avg_amounts': avg_amounts
            }
            
        except Exception as e:
            logger.error(f"❌ Error getting shift statistics: {e}")
            return {}


class ShiftControlCommands:
    """Команды для контроля смен"""
    
    def __init__(self, shift_control: ShiftControlSystem):
        self.shift_control = shift_control
    
    async def cmd_shift_control(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Главное меню контроля смен"""
        user_id = update.effective_user.id
        
        # Проверяем права
        if not self._is_authorized(user_id):
            await update.message.reply_text("❌ У вас нет прав для контроля смен")
            return
        
        keyboard = [
            [InlineKeyboardButton("📋 Сдать смену", callback_data="shift_submit")],
            [InlineKeyboardButton("📊 Отчеты смен", callback_data="shift_reports")],
            [InlineKeyboardButton("🔍 Поиск смены", callback_data="shift_search")],
            [InlineKeyboardButton("📈 Статистика", callback_data="shift_stats")],
            [InlineKeyboardButton("✅ Верификация", callback_data="shift_verification")]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "📋 **Контроль смен**\n\n"
            "Выберите действие:",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    
    async def shift_submit_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Начать процесс сдачи смены"""
        query = update.callback_query
        await query.answer()
        
        # Список доступных клубов
        clubs = ["Рио", "Москва", "СПб", "Казань", "Екатеринбург"]
        
        keyboard = []
        for club in clubs:
            keyboard.append([InlineKeyboardButton(f"🏢 {club}", callback_data=f"shift_club_{club}")])
        
        keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="shift_menu")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "🏢 **Выберите клуб для сдачи смены:**",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    
    async def shift_reports_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показать отчеты о сменах"""
        query = update.callback_query
        await query.answer()
        
        page = int(context.user_data.get('shift_page', 1))
        reports, total = self.shift_control.get_shift_reports(page=page)
        
        if not reports:
            await query.edit_message_text("❌ Отчеты о сменах не найдены")
            return
        
        text = f"📋 **Отчеты о сменах** (стр. {page})\n\n"
        
        for report in reports:
            status_emoji = "✅" if report['status'] == 'verified' else "⏳" if report['status'] == 'pending' else "❌"
            ocr_emoji = "🔍" if report['ocr_verified'] else "❌"
            
            text += f"{status_emoji} **ID:** {report['id']}\n"
            text += f"🏢 **Клуб:** {report['club_name']}\n"
            text += f"📅 **Дата:** {report['shift_date']}\n"
            text += f"⏰ **Время:** {report['shift_time']}\n"
            text += f"💰 **Нал:** {report['fact_cash']:,.0f} ₽\n"
            text += f"💳 **Карта:** {report['fact_card']:,.0f} ₽\n"
            text += f"🔍 **OCR:** {ocr_emoji} ({report['ocr_confidence']:.1%})\n"
            text += f"📸 **Фото:** {'Есть' if report['photo_path'] else 'Нет'}\n\n"
        
        # Кнопки навигации
        keyboard = []
        if page > 1:
            keyboard.append([InlineKeyboardButton("⬅️ Назад", callback_data=f"shift_reports_{page-1}")])
        
        if page * 10 < total:
            keyboard.append([InlineKeyboardButton("➡️ Вперед", callback_data=f"shift_reports_{page+1}")])
        
        keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="shift_menu")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
    
    async def shift_stats_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показать статистику по сменам"""
        query = update.callback_query
        await query.answer()
        
        stats = self.shift_control.get_shift_statistics()
        
        text = "📈 **Статистика смен**\n\n"
        text += f"📋 **Всего смен:** {stats.get('total_shifts', 0)}\n"
        text += f"✅ **Проверено:** {stats.get('verified_shifts', 0)}\n"
        text += f"⏳ **Ожидает:** {stats.get('pending_shifts', 0)}\n"
        text += f"🔍 **OCR проверено:** {stats.get('ocr_verified_shifts', 0)}\n\n"
        
        text += "🏢 **По клубам:**\n"
        for club, count in list(stats.get('clubs_stats', {}).items())[:5]:
            text += f"  • {club}: {count}\n"
        
        text += f"\n💰 **Средние суммы:**\n"
        avg = stats.get('avg_amounts', {})
        text += f"  • Нал: {avg.get('fact_cash', 0):,.0f} ₽\n"
        text += f"  • Карта: {avg.get('fact_card', 0):,.0f} ₽\n"
        text += f"  • Сейф: {avg.get('safe_cash_end', 0):,.0f} ₽\n"
        text += f"  • Коробка: {avg.get('box_cash_end', 0):,.0f} ₽\n"
        
        keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="shift_menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
    
    def _is_authorized(self, user_id: int) -> bool:
        """Проверка прав доступа"""
        # Здесь должна быть проверка прав из основной системы админов
        return True
