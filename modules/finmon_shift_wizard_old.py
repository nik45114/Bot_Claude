#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FinMon Shift Wizard - Simple shift submission without DB
Handles /shift command with inline confirmation
"""

import logging
from datetime import datetime, date, timedelta
from typing import Optional, Dict
import pytz
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler

logger = logging.getLogger(__name__)

# Conversation states
WAITING_PASTE, CONFIRM_SHIFT = range(2)

# Timezone and shift windows
TIMEZONE = 'Europe/Moscow'
SHIFT_CLOSE_TIMES = {
    'morning': {'hour': 10, 'minute': 0},   # 10:00 MSK
    'evening': {'hour': 22, 'minute': 0}    # 22:00 MSK
}
EARLY_OFFSET_HOURS = 1  # Allow early close 1 hour before
GRACE_MINUTES = 60      # Grace period after close time


def now_msk() -> datetime:
    """Get current time in Moscow timezone"""
    msk = pytz.timezone(TIMEZONE)
    return datetime.now(msk)


def get_current_shift_window() -> Optional[Dict]:
    """
    Auto-detect which shift should be closed based on current MSK time
    
    Returns:
        Dict with shift_time and reason, or None if outside windows
    """
    now = now_msk()
    current_hour = now.hour
    current_minute = now.minute
    
    # Morning shift window: 09:00 - 11:00 (10:00 ± 1h + grace)
    morning_close = SHIFT_CLOSE_TIMES['morning']['hour']
    if (current_hour == morning_close - 1) or \
       (current_hour == morning_close and current_minute <= GRACE_MINUTES) or \
       (current_hour == morning_close + 1 and current_minute == 0):
        return {
            'shift_time': 'morning',
            'shift_date': now.date(),
            'reason': 'auto'
        }
    
    # Evening shift window: 21:00 - 23:00 (22:00 ± 1h + grace)
    evening_close = SHIFT_CLOSE_TIMES['evening']['hour']
    if (current_hour == evening_close - 1) or \
       (current_hour == evening_close and current_minute <= GRACE_MINUTES) or \
       (current_hour == evening_close + 1 and current_minute == 0):
        return {
            'shift_time': 'evening',
            'shift_date': now.date(),
            'reason': 'auto'
        }
    
    # Special case: very early morning (00:00 - 00:30) for late evening shifts
    if current_hour == 0 and current_minute <= 30:
        yesterday = now.date() - timedelta(days=1)
        return {
            'shift_time': 'evening',
            'shift_date': yesterday,
            'reason': 'late'
        }
    
    return None


class ShiftWizard:
    """Wizard for shift submission"""
    
    def __init__(self, finmon_simple, schedule, owner_ids: list = None):
        """
        Initialize wizard
        
        Args:
            finmon_simple: FinMonSimple instance
            schedule: FinMonSchedule instance
            owner_ids: List of owner telegram IDs
        """
        self.finmon = finmon_simple
        self.schedule = schedule
        self.owner_ids = owner_ids or []
    
    def is_owner(self, user_id: int) -> bool:
        """Check if user is owner"""
        return user_id in self.owner_ids
    
    async def cmd_shift(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start shift submission process"""
        chat_id = update.effective_chat.id
        
        # Auto-detect club from chat ID
        club = self.finmon.get_club_from_chat(chat_id)
        
        # Detect current shift window
        shift_window = get_current_shift_window()
        
        # Store in context
        context.user_data['shift_club'] = club
        context.user_data['shift_window'] = shift_window
        
        # Build message
        msg = "📋 Сдача смены\n\n"
        
        if club:
            msg += f"🏢 Клуб: {club}\n"
        else:
            msg += "⚠️ Клуб не определён автоматически\n"
            msg += "Укажите клуб на первой строке (Рио или Север)\n\n"
        
        if shift_window:
            shift_label = "утро (ночная смена)" if shift_window['shift_time'] == 'morning' else "вечер (дневная смена)"
            msg += f"⏰ Время: {shift_label}\n"
            msg += f"📅 Дата: {shift_window['shift_date'].strftime('%d.%m.%Y')}\n\n"
        
        msg += "Вставьте данные смены одним сообщением:\n\n"
        msg += "Пример формата:\n"
        if not club:
            msg += "Рио\n"
        msg += "Факт нал: 3 440\n"
        msg += "Факт карта: 12 345\n"
        msg += "QR: 0\n"
        msg += "Карта2: не работает\n"
        msg += "Сейф: 5 000\n"
        msg += "Коробка: 2 000\n"
        
        await update.message.reply_text(msg)
        
        return WAITING_PASTE
    
    async def receive_paste(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Receive and parse pasted shift data"""
        text = update.message.text
        club = context.user_data.get('shift_club')
        
        # Parse the data
        data = self.finmon.parse_shift_paste(text, club)
        
        if not data or not data.get('club'):
            await update.message.reply_text(
                "❌ Не удалось разобрать данные\n"
                "Проверьте формат и попробуйте снова или используйте /cancel"
            )
            return WAITING_PASTE
        
        # Get shift window info
        shift_window = context.user_data.get('shift_window')
        if not shift_window:
            # Default to evening shift today if no window detected
            shift_window = {
                'shift_time': 'evening',
                'shift_date': date.today(),
                'reason': 'manual'
            }
        
        # Get duty name from schedule
        duty_name = ""
        if self.schedule:
            duty_name = self.schedule.get_duty_name(
                data['club'],
                shift_window['shift_date'],
                shift_window['shift_time']
            ) or ""
        
        # Store data in context
        context.user_data['shift_data'] = data
        context.user_data['shift_date'] = shift_window['shift_date']
        context.user_data['shift_time'] = shift_window['shift_time']
        context.user_data['duty_name'] = duty_name
        
        # Show summary with confirmation buttons
        summary = self.finmon.format_shift_summary(data, duty_name)
        
        keyboard = [
            [
                InlineKeyboardButton("✅ Подтвердить", callback_data="shift_confirm"),
                InlineKeyboardButton("❌ Отменить", callback_data="shift_cancel")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(summary, reply_markup=reply_markup)
        
        return CONFIRM_SHIFT
    
    async def confirm_shift(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Confirm and save shift"""
        query = update.callback_query
        await query.answer()
        
        data = context.user_data.get('shift_data')
        shift_date = context.user_data.get('shift_date')
        shift_time = context.user_data.get('shift_time')
        duty_name = context.user_data.get('duty_name', '')
        
        admin_id = update.effective_user.id
        admin_username = update.effective_user.username or ""
        
        # Submit shift
        success = self.finmon.submit_shift(
            data,
            admin_id,
            admin_username,
            shift_date,
            shift_time,
            duty_name
        )
        
        if success:
            # Get updated balances
            club = data['club']
            balances = self.finmon.get_club_balances(club)
            
            msg = "✅ Смена успешно сдана!\n\n"
            msg += f"🏢 {club}\n"
            msg += f"💰 Остатки:\n"
            msg += f"  • Офиц (сейф): {balances['official']:,.0f}\n"
            msg += f"  • Коробка: {balances['box']:,.0f}\n"
            
            await query.edit_message_text(msg)
        else:
            await query.edit_message_text("❌ Ошибка при сохранении смены")
        
        # Clear context
        context.user_data.clear()
        
        return ConversationHandler.END
    
    async def cancel_shift(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Cancel shift submission"""
        query = update.callback_query
        await query.answer()
        
        await query.edit_message_text("❌ Сдача смены отменена")
        
        # Clear context
        context.user_data.clear()
        
        return ConversationHandler.END
    
    async def cancel_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Cancel via /cancel command"""
        await update.message.reply_text("❌ Сдача смены отменена")
        context.user_data.clear()
        return ConversationHandler.END
    
    async def cmd_balances(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show current balances"""
        text = self.finmon.format_balances()
        await update.message.reply_text(text)
    
    async def cmd_movements(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show recent movements"""
        chat_id = update.effective_chat.id
        club = self.finmon.get_club_from_chat(chat_id)
        
        if not club:
            # Show all clubs
            text = ""
            for club_name in ["Рио", "Север"]:
                text += self.finmon.format_movements(club_name, limit=5)
                text += "\n"
        else:
            text = self.finmon.format_movements(club, limit=10)
        
        await update.message.reply_text(text)
