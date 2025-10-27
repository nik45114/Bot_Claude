#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Enhanced Admin & Shift Integration - Интеграция улучшенных систем
Объединяет кнопочный интерфейс, приватные отчеты и удобную работу
"""

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler, CommandHandler, CallbackQueryHandler, MessageHandler, filters

from .enhanced_admin_shift import EnhancedAdminShiftSystem, EnhancedAdminShiftCommands
from .enhanced_shift_submission import EnhancedShiftSubmission, EnhancedShiftCommands

logger = logging.getLogger(__name__)

class EnhancedAdminShiftIntegration:
    """Интеграция улучшенных систем управления"""
    
    def __init__(self, db_path: str, photo_storage_path: str = "/opt/club_assistant/photos"):
        self.db_path = db_path
        self.photo_storage_path = photo_storage_path
        self.owner_id = None
        
        # Инициализируем системы
        self.admin_shift_system = EnhancedAdminShiftSystem(db_path, photo_storage_path)
        self.shift_submission_system = EnhancedShiftSubmission(db_path, photo_storage_path)
        
        # Инициализируем команды
        self.admin_commands = EnhancedAdminShiftCommands(self.admin_shift_system)
        self.shift_commands = EnhancedShiftCommands(self.shift_submission_system)
        
        logger.info("✅ Enhanced Admin & Shift Integration initialized")
    
    def set_owner_id(self, owner_id: int):
        """Установка ID владельца"""
        self.owner_id = owner_id
        self.admin_shift_system.set_owner_id(owner_id)
        self.shift_submission_system.set_owner_id(owner_id)
    
    def register_handlers(self, application):
        """Регистрация всех обработчиков"""
        
        # Основные команды
        application.add_handler(CommandHandler("adminpanel", self.admin_commands.cmd_admin_panel))
        
        # Callback handlers для админ-панели
        application.add_handler(CallbackQueryHandler(self.admin_commands.admin_mgmt_callback, pattern="^admin_mgmt$"))
        application.add_handler(CallbackQueryHandler(self.admin_commands.shift_reports_callback, pattern="^shift_reports$"))
        application.add_handler(CallbackQueryHandler(self.admin_commands.reports_all_callback, pattern="^reports_all$"))
        application.add_handler(CallbackQueryHandler(self.admin_commands.report_detail_callback, pattern="^report_detail_"))
        application.add_handler(CallbackQueryHandler(self.admin_commands.share_report_callback, pattern="^share_report_"))
        application.add_handler(CallbackQueryHandler(self.admin_commands.share_with_admin_callback, pattern="^share_with_"))
        application.add_handler(CallbackQueryHandler(self.admin_commands.main_menu_callback, pattern="^main_menu$"))
        application.add_handler(CallbackQueryHandler(self.admin_commands.admin_list_callback, pattern="^admin_list$"))
        application.add_handler(CallbackQueryHandler(self.admin_commands.system_stats_callback, pattern="^system_stats$"))
        
        # ConversationHandler для смен
        from .enhanced_shift_submission import (
            SHIFT_CLUB_SELECT, SHIFT_TIME_SELECT, SHIFT_DATA_INPUT, 
            SHIFT_PHOTO_UPLOAD, SHIFT_CONFIRMATION, SHIFT_COMPLETE
        )
        
        shift_conversation = ConversationHandler(
            entry_points=[CommandHandler("shift", self.shift_commands.cmd_submit_shift)],
            states={
                SHIFT_CLUB_SELECT: [
                    CallbackQueryHandler(self.shift_commands.club_selected_callback, pattern="^club_"),
                    CallbackQueryHandler(self.shift_commands.cancel_shift_callback, pattern="^cancel_shift$")
                ],
                SHIFT_TIME_SELECT: [
                    CallbackQueryHandler(self.shift_commands.time_selected_callback, pattern="^time_"),
                    CallbackQueryHandler(self.shift_commands.show_club_selection, pattern="^back_to_clubs$"),
                    CallbackQueryHandler(self.shift_commands.cancel_shift_callback, pattern="^cancel_shift$")
                ],
                SHIFT_DATA_INPUT: [
                    CallbackQueryHandler(self.shift_commands.upload_photo_callback, pattern="^upload_photo$"),
                    CallbackQueryHandler(self.shift_commands.show_time_selection, pattern="^back_to_time$"),
                    CallbackQueryHandler(self.shift_commands.cancel_shift_callback, pattern="^cancel_shift$")
                ],
                SHIFT_PHOTO_UPLOAD: [
                    MessageHandler(filters.PHOTO, self.shift_commands.handle_shift_photo),
                    CallbackQueryHandler(self.shift_commands.show_data_input, pattern="^back_to_data$"),
                    CallbackQueryHandler(self.shift_commands.cancel_shift_callback, pattern="^cancel_shift$")
                ],
                SHIFT_CONFIRMATION: [
                    CallbackQueryHandler(self.shift_commands.confirm_shift_callback, pattern="^confirm_shift$"),
                    CallbackQueryHandler(self.shift_commands.show_data_input, pattern="^edit_data$"),
                    CallbackQueryHandler(self.shift_commands.show_data_input, pattern="^back_to_data$"),
                    CallbackQueryHandler(self.shift_commands.cancel_shift_callback, pattern="^cancel_shift$")
                ],
                SHIFT_COMPLETE: [
                    CallbackQueryHandler(self.shift_commands.cancel_shift_callback, pattern="^cancel_shift$")
                ]
            },
            fallbacks=[CallbackQueryHandler(self.shift_commands.cancel_shift_callback, pattern="^cancel_shift$")]
        )
        
        application.add_handler(shift_conversation)
        
        logger.info("✅ Enhanced Admin & Shift Integration handlers registered")
    
    async def handle_shift_with_photo(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка фото смены (интеграция с основной системой)"""
        try:
            if not update.message.photo:
                return
            
            if not context.user_data.get('waiting_for_photo'):
                return
            
            user_id = update.effective_user.id
            
            # Получаем данные смены из контекста
            shift_data = context.user_data.get('shift_data', {})
            club_name = context.user_data.get('shift_club', 'Неизвестно')
            shift_date = context.user_data.get('shift_date', 'Неизвестно')
            shift_time = context.user_data.get('shift_time', 'Неизвестно')
            
            # Сохраняем фото
            photo = update.message.photo[-1]
            photo_path = await self.shift_submission_system.save_shift_photo(
                photo.file_id, user_id, club_name, shift_date, shift_time, context.bot
            )
            
            if not photo_path:
                await update.message.reply_text("❌ Ошибка при сохранении фото")
                return
            
            # Обрабатываем фото с OCR
            ocr_result = self.shift_submission_system.extract_numbers_from_photo(photo_path)
            
            if ocr_result.get('error'):
                await update.message.reply_text(f"❌ Ошибка OCR: {ocr_result['error']}")
                return
            
            # Сохраняем результаты OCR
            context.user_data['ocr_result'] = ocr_result
            context.user_data['photo_path'] = photo_path
            context.user_data['waiting_for_photo'] = False
            
            # Показываем подтверждение
            await self.shift_commands.show_confirmation(update, context)
            
        except Exception as e:
            logger.error(f"❌ Error handling shift with photo: {e}")
            await update.message.reply_text(f"❌ Ошибка при обработке фото: {e}")
    
    def get_system_status(self) -> dict:
        """Получить статус всех систем"""
        try:
            # Статистика админов
            admins = self.admin_shift_system.get_admins_list()
            total_admins = len(admins)
            active_admins = len([a for a in admins if a['last_seen']])
            
            # Статистика отчетов
            reports = self.admin_shift_system.get_accessible_reports(self.owner_id)
            total_reports = len(reports)
            verified_reports = len([r for r in reports if r['status'] == 'verified'])
            pending_reports = len([r for r in reports if r['status'] == 'pending'])
            ocr_verified_reports = len([r for r in reports if r['ocr_verified']])
            
            return {
                'admin_management': {
                    'total_admins': total_admins,
                    'active_admins': active_admins,
                    'roles_stats': {}
                },
                'shift_control': {
                    'total_reports': total_reports,
                    'verified_reports': verified_reports,
                    'pending_reports': pending_reports,
                    'ocr_verified_reports': ocr_verified_reports
                },
                'photo_storage': {
                    'path': self.photo_storage_path,
                    'available': True
                },
                'system_status': 'operational'
            }
            
        except Exception as e:
            logger.error(f"❌ Error getting system status: {e}")
            return {'error': str(e)}
    
    async def cmd_system_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показать статус всех систем"""
        user_id = update.effective_user.id
        
        if not self.admin_shift_system.is_admin(user_id) and not self.admin_shift_system.is_owner(user_id):
            await update.message.reply_text("❌ У вас нет прав для просмотра статуса системы")
            return
        
        status = self.get_system_status()
        
        text = "📊 **Статус системы управления**\n\n"
        
        # Статус управления админами
        admin_mgmt = status.get('admin_management', {})
        text += "👥 **Управление админами:**\n"
        text += f"  • Всего админов: {admin_mgmt.get('total_admins', 0)}\n"
        text += f"  • Активных: {admin_mgmt.get('active_admins', 0)}\n"
        
        # Статус контроля смен
        shift_control = status.get('shift_control', {})
        text += f"\n📋 **Контроль смен:**\n"
        text += f"  • Всего отчетов: {shift_control.get('total_reports', 0)}\n"
        text += f"  • Проверено: {shift_control.get('verified_reports', 0)}\n"
        text += f"  • Ожидает: {shift_control.get('pending_reports', 0)}\n"
        text += f"  • OCR проверено: {shift_control.get('ocr_verified_reports', 0)}\n"
        
        # Статус хранения фото
        photo = status.get('photo_storage', {})
        text += f"\n📸 **Хранение фото:**\n"
        text += f"  • Путь: {photo.get('path', 'Неизвестно')}\n"
        text += f"  • Доступен: {'✅' if photo.get('available') else '❌'}\n"
        
        # Общий статус
        system_status = status.get('system_status', 'unknown')
        text += f"\n🔧 **Общий статус:** {'✅ Работает' if system_status == 'operational' else '❌ Проблемы'}\n"
        
        keyboard = [
            [InlineKeyboardButton("🔧 Админ-панель", callback_data="admin_panel")],
            [InlineKeyboardButton("📋 Отчеты", callback_data="shift_reports")]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='Markdown')


def register_enhanced_admin_shift_management(application, config: dict, db_path: str, owner_id: int):
    """Регистрация улучшенной системы управления админами и сменами"""
    try:
        # Создаем интеграционную систему
        integration = EnhancedAdminShiftIntegration(db_path)
        integration.set_owner_id(owner_id)
        
        # Синхронизируем существующих админов
        integration.admin_shift_system.sync_with_existing_admins()
        
        # Регистрируем обработчики
        integration.register_handlers(application)
        
        # Добавляем команду статуса системы
        application.add_handler(CommandHandler("systemstatus", integration.cmd_system_status))
        
        logger.info("✅ Enhanced Admin & Shift Management system registered successfully")
        return integration
        
    except Exception as e:
        logger.error(f"❌ Error registering Enhanced Admin & Shift Management: {e}")
        return None
