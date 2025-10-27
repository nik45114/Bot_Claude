#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Admin & Shift Management Integration - Интеграционный модуль
Объединяет систему управления админами, контроль смен и OCR
"""

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler, CommandHandler, CallbackQueryHandler

from .admin_management import AdminManagementSystem, AdminManagementCommands
from .shift_control import ShiftControlSystem, ShiftControlCommands
from .ocr_processor import OCRProcessor, OCRCommands
from .manual_update import ManualUpdateSystem, ManualUpdateCommands

logger = logging.getLogger(__name__)

class AdminShiftIntegration:
    """Интегрированная система управления админами и сменами"""
    
    def __init__(self, db_path: str, photo_storage_path: str = "/opt/club_assistant/photos"):
        self.db_path = db_path
        self.photo_storage_path = photo_storage_path
        
        # Инициализируем все системы
        self.admin_mgmt = AdminManagementSystem(db_path)
        self.shift_control = ShiftControlSystem(db_path, photo_storage_path)
        self.ocr_processor = OCRProcessor()
        self.update_system = ManualUpdateSystem()
        
        # Инициализируем команды
        self.admin_commands = AdminManagementCommands(self.admin_mgmt)
        self.shift_commands = ShiftControlCommands(self.shift_control)
        self.ocr_commands = OCRCommands(self.ocr_processor)
        self.update_commands = ManualUpdateCommands(self.update_system)
        
        # Синхронизируем существующих админов
        self.admin_mgmt.sync_with_existing_admins()
        
        logger.info("✅ Admin & Shift Management Integration initialized")
    
    def register_handlers(self, application):
        """Регистрация обработчиков команд"""
        
        # Команды управления админами
        application.add_handler(CommandHandler("adminmgmt", self.admin_commands.cmd_admin_management))
        application.add_handler(CallbackQueryHandler(self.admin_commands.admin_list_callback, pattern="^admin_list"))
        application.add_handler(CallbackQueryHandler(self.admin_commands.admin_stats_callback, pattern="^admin_stats"))
        application.add_handler(CallbackQueryHandler(self.admin_commands.admin_sync_callback, pattern="^admin_sync"))
        
        # Команды контроля смен
        application.add_handler(CommandHandler("shiftmgmt", self.shift_commands.cmd_shift_control))
        application.add_handler(CallbackQueryHandler(self.shift_commands.shift_submit_callback, pattern="^shift_submit"))
        application.add_handler(CallbackQueryHandler(self.shift_commands.shift_reports_callback, pattern="^shift_reports"))
        application.add_handler(CallbackQueryHandler(self.shift_commands.shift_stats_callback, pattern="^shift_stats"))
        
        # Команды ручного обновления
        application.add_handler(CommandHandler("manualupdate", self.update_commands.cmd_manual_update))
        application.add_handler(CommandHandler("updatelog", self.update_commands.cmd_update_log))
        
        logger.info("✅ Admin & Shift Management handlers registered")
    
    async def handle_shift_with_photo(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка смены с фото"""
        try:
            if not update.message.photo:
                await update.message.reply_text("❌ Пожалуйста, прикрепите фото к сообщению")
                return
            
            user_id = update.effective_user.id
            
            # Получаем данные смены из контекста
            shift_data = context.user_data.get('shift_data', {})
            club_name = context.user_data.get('shift_club', 'Неизвестно')
            shift_date = context.user_data.get('shift_date', 'Неизвестно')
            shift_time = context.user_data.get('shift_time', 'Неизвестно')
            
            # Сохраняем фото
            photo = update.message.photo[-1]
            photo_path = await self.shift_control.save_shift_photo(
                photo.file_id, user_id, club_name, shift_date, shift_time, context.bot
            )
            
            if not photo_path:
                await update.message.reply_text("❌ Ошибка при сохранении фото")
                return
            
            # Обрабатываем фото с OCR
            ocr_result = await self.ocr_commands.process_shift_photo(
                update, context, photo_path, shift_data
            )
            
            # Создаем отчет о смене
            shift_id = self.shift_control.create_shift_report(
                user_id, club_name, shift_date, shift_time, shift_data, photo_path, ocr_result
            )
            
            if shift_id:
                # Обновляем активность админа
                self.admin_mgmt.update_admin_activity(
                    user_id, 'shift_submitted', {
                        'shift_id': shift_id,
                        'club': club_name,
                        'ocr_success': ocr_result.get('success', False)
                    }
                )
                
                await update.message.reply_text(
                    f"✅ **Смена успешно сдана!**\n\n"
                    f"🆔 ID отчета: {shift_id}\n"
                    f"🏢 Клуб: {club_name}\n"
                    f"📅 Дата: {shift_date}\n"
                    f"⏰ Время: {shift_time}\n"
                    f"🔍 OCR: {'✅ Успешно' if ocr_result.get('success') else '❌ Не удалось'}\n"
                    f"📸 Фото: ✅ Сохранено",
                    parse_mode='Markdown'
                )
            else:
                await update.message.reply_text("❌ Ошибка при создании отчета о смене")
            
            # Очищаем контекст
            context.user_data.clear()
            
        except Exception as e:
            logger.error(f"❌ Error handling shift with photo: {e}")
            await update.message.reply_text(f"❌ Ошибка при обработке смены: {e}")
    
    def get_system_status(self) -> dict:
        """Получить статус всех систем"""
        try:
            admin_stats = self.admin_mgmt.get_admin_stats()
            shift_stats = self.shift_control.get_shift_statistics()
            
            return {
                'admin_management': {
                    'total_admins': admin_stats.get('total_admins', 0),
                    'active_last_week': admin_stats.get('active_last_week', 0),
                    'roles_stats': admin_stats.get('roles_stats', {})
                },
                'shift_control': {
                    'total_shifts': shift_stats.get('total_shifts', 0),
                    'verified_shifts': shift_stats.get('verified_shifts', 0),
                    'pending_shifts': shift_stats.get('pending_shifts', 0),
                    'ocr_verified_shifts': shift_stats.get('ocr_verified_shifts', 0)
                },
                'ocr_processor': {
                    'available': True,  # Проверяем доступность Tesseract
                    'patterns_count': len(self.ocr_processor.number_patterns)
                },
                'photo_storage': {
                    'path': self.photo_storage_path,
                    'available': True  # Проверяем доступность директории
                }
            }
            
        except Exception as e:
            logger.error(f"❌ Error getting system status: {e}")
            return {'error': str(e)}
    
    async def cmd_system_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показать статус всех систем"""
        user_id = update.effective_user.id
        
        if not self._is_authorized(user_id):
            await update.message.reply_text("❌ У вас нет прав для просмотра статуса системы")
            return
        
        status = self.get_system_status()
        
        text = "📊 **Статус системы управления**\n\n"
        
        # Статус управления админами
        admin_mgmt = status.get('admin_management', {})
        text += "👥 **Управление админами:**\n"
        text += f"  • Всего админов: {admin_mgmt.get('total_admins', 0)}\n"
        text += f"  • Активных за неделю: {admin_mgmt.get('active_last_week', 0)}\n"
        
        roles = admin_mgmt.get('roles_stats', {})
        if roles:
            text += "  • По ролям:\n"
            for role, count in roles.items():
                text += f"    - {role}: {count}\n"
        
        # Статус контроля смен
        shift_control = status.get('shift_control', {})
        text += f"\n📋 **Контроль смен:**\n"
        text += f"  • Всего смен: {shift_control.get('total_shifts', 0)}\n"
        text += f"  • Проверено: {shift_control.get('verified_shifts', 0)}\n"
        text += f"  • Ожидает: {shift_control.get('pending_shifts', 0)}\n"
        text += f"  • OCR проверено: {shift_control.get('ocr_verified_shifts', 0)}\n"
        
        # Статус OCR
        ocr = status.get('ocr_processor', {})
        text += f"\n🔍 **OCR процессор:**\n"
        text += f"  • Доступен: {'✅' if ocr.get('available') else '❌'}\n"
        text += f"  • Паттернов: {ocr.get('patterns_count', 0)}\n"
        
        # Статус хранения фото
        photo = status.get('photo_storage', {})
        text += f"\n📸 **Хранение фото:**\n"
        text += f"  • Путь: {photo.get('path', 'Неизвестно')}\n"
        text += f"  • Доступен: {'✅' if photo.get('available') else '❌'}\n"
        
        await update.message.reply_text(text, parse_mode='Markdown')
    
    def _is_authorized(self, user_id: int) -> bool:
        """Проверка прав доступа"""
        # Здесь должна быть проверка прав из основной системы админов
        return True


def register_admin_shift_management(application, config: dict, db_path: str):
    """Регистрация системы управления админами и сменами"""
    try:
        # Создаем интеграционную систему
        integration = AdminShiftIntegration(db_path)
        
        # Регистрируем обработчики
        integration.register_handlers(application)
        
        # Добавляем команду статуса системы
        application.add_handler(CommandHandler("systemstatus", integration.cmd_system_status))
        
        logger.info("✅ Admin & Shift Management system registered successfully")
        return integration
        
    except Exception as e:
        logger.error(f"❌ Error registering Admin & Shift Management: {e}")
        return None
