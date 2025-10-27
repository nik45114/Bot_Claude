#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Enhanced Shift Submission - Улучшенная система сдачи смен с кнопочным интерфейсом
"""

import logging
import sqlite3
import json
import os
from datetime import datetime, date
from typing import List, Dict, Optional, Tuple
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import ContextTypes, ConversationHandler

logger = logging.getLogger(__name__)

# Состояния для диалога сдачи смены
(SHIFT_CLUB_SELECT, SHIFT_TIME_SELECT, SHIFT_DATA_INPUT, SHIFT_PHOTO_UPLOAD, 
 SHIFT_CONFIRMATION, SHIFT_COMPLETE) = range(6)

class EnhancedShiftSubmission:
    """Улучшенная система сдачи смен с кнопочным интерфейсом"""
    
    def __init__(self, db_path: str, photo_storage_path: str = "/opt/club_assistant/photos"):
        self.db_path = db_path
        self.photo_storage_path = photo_storage_path
        self.owner_id = None
        
        # Список доступных клубов
        self.clubs = ["Рио", "Москва", "СПб", "Казань", "Екатеринбург", "Новосибирск"]
        
        # Времена смен
        self.shift_times = ["morning", "evening"]
        
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
            
            # Таблица для смен
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS shift_submissions (
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
                    
                    -- Статус
                    status TEXT DEFAULT 'submitted',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    
                    FOREIGN KEY (admin_id) REFERENCES admin_management(user_id)
                )
            ''')
            
            conn.commit()
            conn.close()
            logger.info("✅ Enhanced Shift Submission Database initialized")
            
        except Exception as e:
            logger.error(f"❌ Error initializing shift submission database: {e}")
    
    def _init_photo_storage(self):
        """Инициализация директории для фото"""
        try:
            os.makedirs(self.photo_storage_path, exist_ok=True)
            logger.info(f"✅ Photo storage initialized: {self.photo_storage_path}")
        except Exception as e:
            logger.error(f"❌ Error initializing photo storage: {e}")
    
    async def save_shift_photo(self, file_id: str, admin_id: int, club_name: str, 
                              shift_date: date, shift_time: str, bot) -> Optional[str]:
        """Сохранение фото смены"""
        try:
            file = await bot.get_file(file_id)
            
            filename = f"{admin_id}_{club_name}_{shift_date}_{shift_time}_{datetime.now().strftime('%H%M%S')}.jpg"
            file_path = os.path.join(self.photo_storage_path, filename)
            
            await file.download_to_drive(file_path)
            
            logger.info(f"✅ Photo saved: {file_path}")
            return file_path
            
        except Exception as e:
            logger.error(f"❌ Error saving shift photo: {e}")
            return None
    
    def extract_numbers_from_photo(self, photo_path: str) -> Dict:
        """Извлечение чисел из фото с помощью OCR"""
        try:
            # Здесь будет интеграция с OCR
            # Пока возвращаем заглушку
            
            import cv2
            import numpy as np
            
            image = cv2.imread(photo_path)
            if image is None:
                return {'error': 'Could not load image'}
            
            # Простая обработка изображения
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            
            # Здесь должен быть вызов OCR библиотеки
            # Пока возвращаем заглушку
            
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
            
            return extracted_numbers
            
        except Exception as e:
            logger.error(f"❌ Error extracting numbers from photo: {e}")
            return {'error': str(e)}
    
    def create_shift_submission(self, admin_id: int, club_name: str, shift_date: date, 
                               shift_time: str, shift_data: Dict, photo_path: str = None,
                               ocr_data: Dict = None) -> Optional[int]:
        """Создание отчета о смене"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO shift_submissions 
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
            
            logger.info(f"✅ Shift submission created: ID {shift_id}")
            return shift_id
            
        except Exception as e:
            logger.error(f"❌ Error creating shift submission: {e}")
            return None


class EnhancedShiftCommands:
    """Команды для улучшенной системы смен"""
    
    def __init__(self, shift_system: EnhancedShiftSubmission):
        self.shift_system = shift_system
    
    async def cmd_submit_shift(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Начать процесс сдачи смены"""
        user_id = update.effective_user.id
        
        # Проверяем права
        if not self._is_admin(user_id):
            await update.message.reply_text("❌ У вас нет прав для сдачи смен")
            return
        
        # Очищаем контекст
        context.user_data.clear()
        
        await self.show_club_selection(update, context)
        return SHIFT_CLUB_SELECT
    
    async def show_club_selection(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показать выбор клуба"""
        keyboard = []
        
        # Создаем кнопки для каждого клуба
        for club in self.shift_system.clubs:
            keyboard.append([InlineKeyboardButton(f"🏢 {club}", callback_data=f"club_{club}")])
        
        keyboard.append([InlineKeyboardButton("❌ Отмена", callback_data="cancel_shift")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        text = "🏢 **Выберите клуб для сдачи смены:**"
        
        if update.callback_query:
            await update.callback_query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
        else:
            await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='Markdown')
    
    async def club_selected_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка выбора клуба"""
        query = update.callback_query
        await query.answer()
        
        club_name = query.data.split('_')[1]
        context.user_data['shift_club'] = club_name
        
        await self.show_time_selection(update, context)
        return SHIFT_TIME_SELECT
    
    async def show_time_selection(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показать выбор времени смены"""
        keyboard = [
            [InlineKeyboardButton("☀️ Утренняя смена", callback_data="time_morning")],
            [InlineKeyboardButton("🌙 Вечерняя смена", callback_data="time_evening")],
            [InlineKeyboardButton("🔙 Назад", callback_data="back_to_clubs")],
            [InlineKeyboardButton("❌ Отмена", callback_data="cancel_shift")]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        club_name = context.user_data.get('shift_club', 'Неизвестно')
        text = f"⏰ **Выберите время смены для {club_name}:**"
        
        await update.callback_query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
    
    async def time_selected_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка выбора времени"""
        query = update.callback_query
        await query.answer()
        
        shift_time = query.data.split('_')[1]
        context.user_data['shift_time'] = shift_time
        context.user_data['shift_date'] = date.today()
        
        await self.show_data_input(update, context)
        return SHIFT_DATA_INPUT
    
    async def show_data_input(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показать форму ввода данных"""
        club_name = context.user_data.get('shift_club', 'Неизвестно')
        shift_time = context.user_data.get('shift_time', 'Неизвестно')
        shift_date = context.user_data.get('shift_date', 'Неизвестно')
        
        text = f"📊 **Введите данные смены**\n\n"
        text += f"🏢 Клуб: {club_name}\n"
        text += f"📅 Дата: {shift_date}\n"
        text += f"⏰ Время: {shift_time}\n\n"
        text += f"**Отправьте данные в следующем формате:**\n\n"
        text += f"```\n"
        text += f"Факт нал: 5000\n"
        text += f"Факт карта: 15000\n"
        text += f"QR: 2000\n"
        text += f"Карта2: 0\n"
        text += f"Сейф: 10000\n"
        text += f"Коробка: 5000\n"
        text += f"```\n\n"
        text += f"Или отправьте фото с данными для автоматического распознавания."
        
        keyboard = [
            [InlineKeyboardButton("📸 Отправить фото", callback_data="upload_photo")],
            [InlineKeyboardButton("🔙 Назад", callback_data="back_to_time")],
            [InlineKeyboardButton("❌ Отмена", callback_data="cancel_shift")]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.callback_query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
    
    async def upload_photo_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка загрузки фото"""
        query = update.callback_query
        await query.answer()
        
        text = "📸 **Отправьте фото с данными смены**\n\n"
        text += "Фото должно содержать:\n"
        text += "• Суммы наличных и безнала\n"
        text += "• Остатки в кассах\n"
        text += "• Четкий текст и цифры\n\n"
        text += "После отправки фото система автоматически извлечет числа."
        
        keyboard = [
            [InlineKeyboardButton("🔙 Назад", callback_data="back_to_data")],
            [InlineKeyboardButton("❌ Отмена", callback_data="cancel_shift")]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
        
        context.user_data['waiting_for_photo'] = True
        return SHIFT_PHOTO_UPLOAD
    
    async def handle_shift_photo(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка фото смены"""
        if not update.message.photo:
            await update.message.reply_text("❌ Пожалуйста, отправьте фото")
            return
        
        if not context.user_data.get('waiting_for_photo'):
            return
        
        user_id = update.effective_user.id
        club_name = context.user_data.get('shift_club')
        shift_date = context.user_data.get('shift_date')
        shift_time = context.user_data.get('shift_time')
        
        await update.message.reply_text("🔍 Обрабатываю фото...")
        
        # Сохраняем фото
        photo = update.message.photo[-1]
        photo_path = await self.shift_system.save_shift_photo(
            photo.file_id, user_id, club_name, shift_date, shift_time, context.bot
        )
        
        if not photo_path:
            await update.message.reply_text("❌ Ошибка при сохранении фото")
            return
        
        # Обрабатываем фото с OCR
        ocr_result = self.shift_system.extract_numbers_from_photo(photo_path)
        
        if ocr_result.get('error'):
            await update.message.reply_text(f"❌ Ошибка OCR: {ocr_result['error']}")
            return
        
        # Сохраняем результаты OCR
        context.user_data['ocr_result'] = ocr_result
        context.user_data['photo_path'] = photo_path
        context.user_data['waiting_for_photo'] = False
        
        await self.show_confirmation(update, context)
        return SHIFT_CONFIRMATION
    
    async def show_confirmation(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показать подтверждение данных"""
        club_name = context.user_data.get('shift_club')
        shift_date = context.user_data.get('shift_date')
        shift_time = context.user_data.get('shift_time')
        ocr_result = context.user_data.get('ocr_result', {})
        photo_path = context.user_data.get('photo_path')
        
        text = f"📋 **Подтверждение смены**\n\n"
        text += f"🏢 Клуб: {club_name}\n"
        text += f"📅 Дата: {shift_date}\n"
        text += f"⏰ Время: {shift_time}\n\n"
        
        if ocr_result:
            text += f"🔍 **Результаты OCR:**\n"
            numbers = ocr_result.get('numbers', {})
            
            field_names = {
                'fact_cash': 'Наличные',
                'fact_card': 'Карта',
                'qr_amount': 'QR',
                'card2_amount': 'Карта 2',
                'safe_cash_end': 'Сейф',
                'box_cash_end': 'Коробка'
            }
            
            for field, name in field_names.items():
                value = numbers.get(field)
                if value is not None:
                    text += f"  • {name}: {value:,.0f} ₽\n"
                else:
                    text += f"  • {name}: ❌ Не найдено\n"
            
            text += f"\n📊 Уверенность OCR: {ocr_result.get('confidence', 0):.1%}\n"
        
        text += f"\n📸 Фото: {'✅ Сохранено' if photo_path else '❌ Нет'}"
        
        keyboard = [
            [InlineKeyboardButton("✅ Подтвердить смену", callback_data="confirm_shift")],
            [InlineKeyboardButton("✏️ Редактировать данные", callback_data="edit_data")],
            [InlineKeyboardButton("🔙 Назад", callback_data="back_to_data")],
            [InlineKeyboardButton("❌ Отмена", callback_data="cancel_shift")]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='Markdown')
    
    async def confirm_shift_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Подтверждение смены"""
        query = update.callback_query
        await query.answer()
        
        user_id = update.effective_user.id
        club_name = context.user_data.get('shift_club')
        shift_date = context.user_data.get('shift_date')
        shift_time = context.user_data.get('shift_time')
        ocr_result = context.user_data.get('ocr_result', {})
        photo_path = context.user_data.get('photo_path')
        
        # Создаем данные смены
        shift_data = ocr_result.get('numbers', {})
        
        # Создаем отчет о смене
        shift_id = self.shift_system.create_shift_submission(
            user_id, club_name, shift_date, shift_time, shift_data, photo_path, ocr_result
        )
        
        if shift_id:
            text = f"✅ **Смена успешно сдана!**\n\n"
            text += f"🆔 ID отчета: {shift_id}\n"
            text += f"🏢 Клуб: {club_name}\n"
            text += f"📅 Дата: {shift_date}\n"
            text += f"⏰ Время: {shift_time}\n"
            text += f"🔍 OCR: {'✅ Успешно' if ocr_result.get('success') else '❌ Не удалось'}\n"
            text += f"📸 Фото: ✅ Сохранено\n\n"
            text += f"Отчет будет проверен администратором."
            
            keyboard = [
                [InlineKeyboardButton("📋 Посмотреть отчет", callback_data=f"view_report_{shift_id}")],
                [InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")]
            ]
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
        else:
            await query.edit_message_text("❌ Ошибка при создании отчета о смене")
        
        # Очищаем контекст
        context.user_data.clear()
        return SHIFT_COMPLETE
    
    async def cancel_shift_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Отмена смены"""
        query = update.callback_query
        await query.answer()
        
        context.user_data.clear()
        
        await query.edit_message_text(
            "❌ Сдача смены отменена",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")]])
        )
        
        return ConversationHandler.END
    
    def _is_admin(self, user_id: int) -> bool:
        """Проверка, является ли пользователь админом"""
        try:
            conn = sqlite3.connect(self.shift_system.db_path)
            cursor = conn.cursor()
            cursor.execute('SELECT COUNT(*) FROM admin_management WHERE user_id = ? AND is_active = 1', (user_id,))
            count = cursor.fetchone()[0]
            conn.close()
            return count > 0
        except:
            return False


def register_enhanced_shift_submission(application, config: dict, db_path: str, owner_id: int):
    """Регистрация улучшенной системы смен"""
    try:
        # Создаем систему
        shift_system = EnhancedShiftSubmission(db_path)
        shift_system.set_owner_id(owner_id)
        
        # Создаем команды
        commands = EnhancedShiftCommands(shift_system)
        
        # Создаем ConversationHandler для смен
        shift_conversation = ConversationHandler(
            entry_points=[CommandHandler("shift", commands.cmd_submit_shift)],
            states={
                SHIFT_CLUB_SELECT: [
                    CallbackQueryHandler(commands.club_selected_callback, pattern="^club_"),
                    CallbackQueryHandler(commands.cancel_shift_callback, pattern="^cancel_shift$")
                ],
                SHIFT_TIME_SELECT: [
                    CallbackQueryHandler(commands.time_selected_callback, pattern="^time_"),
                    CallbackQueryHandler(commands.show_club_selection, pattern="^back_to_clubs$"),
                    CallbackQueryHandler(commands.cancel_shift_callback, pattern="^cancel_shift$")
                ],
                SHIFT_DATA_INPUT: [
                    CallbackQueryHandler(commands.upload_photo_callback, pattern="^upload_photo$"),
                    CallbackQueryHandler(commands.show_time_selection, pattern="^back_to_time$"),
                    CallbackQueryHandler(commands.cancel_shift_callback, pattern="^cancel_shift$")
                ],
                SHIFT_PHOTO_UPLOAD: [
                    MessageHandler(filters.PHOTO, commands.handle_shift_photo),
                    CallbackQueryHandler(commands.show_data_input, pattern="^back_to_data$"),
                    CallbackQueryHandler(commands.cancel_shift_callback, pattern="^cancel_shift$")
                ],
                SHIFT_CONFIRMATION: [
                    CallbackQueryHandler(commands.confirm_shift_callback, pattern="^confirm_shift$"),
                    CallbackQueryHandler(commands.show_data_input, pattern="^edit_data$"),
                    CallbackQueryHandler(commands.show_data_input, pattern="^back_to_data$"),
                    CallbackQueryHandler(commands.cancel_shift_callback, pattern="^cancel_shift$")
                ],
                SHIFT_COMPLETE: [
                    CallbackQueryHandler(commands.cancel_shift_callback, pattern="^cancel_shift$")
                ]
            },
            fallbacks=[CallbackQueryHandler(commands.cancel_shift_callback, pattern="^cancel_shift$")]
        )
        
        application.add_handler(shift_conversation)
        
        logger.info("✅ Enhanced Shift Submission system registered")
        return shift_system
        
    except Exception as e:
        logger.error(f"❌ Error registering Enhanced Shift Submission: {e}")
        return None
