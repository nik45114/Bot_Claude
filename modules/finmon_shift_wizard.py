#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FinMon Shift Wizard - Button-based shift submission
Handles /shift command with step-by-step wizard
"""

import logging
from datetime import datetime, date, timedelta
from typing import Optional, Dict
import pytz
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler

logger = logging.getLogger(__name__)

# Conversation states
(SELECT_CLUB, SELECT_SHIFT_TIME, ENTER_FACT_CASH, ENTER_FACT_CARD, 
 ENTER_QR, ENTER_CARD2, ENTER_SAFE, ENTER_BOX, ENTER_TOVARKA,
 ENTER_GAMEPADS, ENTER_REPAIR, ENTER_NEED_REPAIR, ENTER_GAMES,
 CONFIRM_SHIFT) = range(14)

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
    """Wizard for button-based shift submission"""
    
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
        
        # Initialize shift data in context
        context.user_data['shift_data'] = {
            'fact_cash': 0.0,
            'fact_card': 0.0,
            'qr': 0.0,
            'card2': 0.0,
            'safe_cash_end': 0.0,
            'box_cash_end': 0.0,
            'tovarka': 0.0,
            'gamepads': 0,
            'repair': 0,
            'need_repair': 0,
            'games': 0
        }
        
        if club:
            # Club auto-detected, move to shift time selection
            context.user_data['shift_club'] = club
            context.user_data['shift_window'] = shift_window
            
            msg = f"📋 Сдача смены\n\n🏢 Клуб: {club}\n\nВыберите время смены:"
            
            keyboard = [
                [InlineKeyboardButton("☀️ Утро", callback_data="shift_time_morning")],
                [InlineKeyboardButton("🌙 Вечер", callback_data="shift_time_evening")],
                [InlineKeyboardButton("❌ Отменить", callback_data="shift_cancel")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(msg, reply_markup=reply_markup)
            return SELECT_SHIFT_TIME
        else:
            # Club not auto-detected, ask user to select
            msg = "📋 Сдача смены\n\n⚠️ Клуб не определён автоматически\n\nВыберите клуб:"
            
            keyboard = [
                [InlineKeyboardButton("🏢 Рио", callback_data="club_rio")],
                [InlineKeyboardButton("🏢 Север", callback_data="club_sever")],
                [InlineKeyboardButton("❌ Отменить", callback_data="shift_cancel")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(msg, reply_markup=reply_markup)
            return SELECT_CLUB
    
    async def select_club(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle club selection"""
        query = update.callback_query
        await query.answer()
        
        if query.data == "club_rio":
            club = "Рио"
        elif query.data == "club_sever":
            club = "Север"
        else:
            await query.edit_message_text("❌ Сдача смены отменена")
            context.user_data.clear()
            return ConversationHandler.END
        
        context.user_data['shift_club'] = club
        
        # Detect shift window
        shift_window = get_current_shift_window()
        context.user_data['shift_window'] = shift_window
        
        msg = f"📋 Сдача смены\n\n🏢 Клуб: {club}\n\nВыберите время смены:"
        
        keyboard = [
            [InlineKeyboardButton("☀️ Утро", callback_data="shift_time_morning")],
            [InlineKeyboardButton("🌙 Вечер", callback_data="shift_time_evening")],
            [InlineKeyboardButton("❌ Отменить", callback_data="shift_cancel")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(msg, reply_markup=reply_markup)
        return SELECT_SHIFT_TIME
    
    async def select_shift_time(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle shift time selection and show previous balances"""
        query = update.callback_query
        await query.answer()
        
        if query.data == "shift_time_morning":
            shift_time = "morning"
            shift_label = "☀️ Утро (ночная смена)"
        elif query.data == "shift_time_evening":
            shift_time = "evening"
            shift_label = "🌙 Вечер (дневная смена)"
        else:
            await query.edit_message_text("❌ Сдача смены отменена")
            context.user_data.clear()
            return ConversationHandler.END
        
        context.user_data['shift_time'] = shift_time
        club = context.user_data['shift_club']
        
        # Get previous balances
        prev_balances = self.finmon.get_club_balances(club)
        prev_official = prev_balances.get('official', 0) if prev_balances else 0
        prev_box = prev_balances.get('box', 0) if prev_balances else 0
        
        # Store previous balances for delta calculation
        context.user_data['prev_official'] = prev_official
        context.user_data['prev_box'] = prev_box
        
        msg = f"📋 Сдача смены\n\n"
        msg += f"🏢 Клуб: {club}\n"
        msg += f"⏰ Время: {shift_label}\n\n"
        msg += f"📊 Прошлый раз:\n"
        msg += f"  • Основная: {prev_official:,.0f} ₽\n"
        msg += f"  • Коробка: {prev_box:,.0f} ₽\n\n"
        msg += "Теперь введите данные смены.\n\n"
        msg += "💰 Выручка - Наличка факт:"
        
        keyboard = [
            [InlineKeyboardButton("Ввести вручную", callback_data="enter_manual")],
            [InlineKeyboardButton("❌ Отменить", callback_data="shift_cancel")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(msg, reply_markup=reply_markup)
        return ENTER_FACT_CASH
    
    async def prompt_fact_cash(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Prompt for cash revenue input"""
        query = update.callback_query
        await query.answer()
        
        msg = "💰 Введите наличку факт (только число):\n\nПример: 3440"
        await query.edit_message_text(msg)
        return ENTER_FACT_CASH
    
    async def receive_fact_cash(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Receive cash revenue"""
        try:
            value = float(update.message.text.replace(' ', '').replace(',', '.'))
            context.user_data['shift_data']['fact_cash'] = value
            
            msg = f"✅ Наличка факт: {value:,.0f} ₽\n\n"
            msg += "💳 Введите карту факт:"
            
            keyboard = [
                [InlineKeyboardButton("Ввести вручную", callback_data="enter_manual")],
                [InlineKeyboardButton("❌ Отменить", callback_data="shift_cancel")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(msg, reply_markup=reply_markup)
            return ENTER_FACT_CARD
        except ValueError:
            await update.message.reply_text("❌ Неверный формат. Введите число:")
            return ENTER_FACT_CASH
    
    async def prompt_fact_card(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Prompt for card revenue input"""
        query = update.callback_query
        await query.answer()
        
        msg = "💳 Введите карту факт (только число):\n\nПример: 12345"
        await query.edit_message_text(msg)
        return ENTER_FACT_CARD
    
    async def receive_fact_card(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Receive card revenue"""
        try:
            value = float(update.message.text.replace(' ', '').replace(',', '.'))
            context.user_data['shift_data']['fact_card'] = value
            
            msg = f"✅ Карта факт: {value:,.0f} ₽\n\n"
            msg += "📱 Введите QR:"
            
            keyboard = [
                [InlineKeyboardButton("Ввести вручную", callback_data="enter_manual")],
                [InlineKeyboardButton("0 (нет)", callback_data="value_0")],
                [InlineKeyboardButton("❌ Отменить", callback_data="shift_cancel")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(msg, reply_markup=reply_markup)
            return ENTER_QR
        except ValueError:
            await update.message.reply_text("❌ Неверный формат. Введите число:")
            return ENTER_FACT_CARD
    
    async def prompt_qr(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Prompt for QR revenue input"""
        query = update.callback_query
        await query.answer()
        
        if query.data == "value_0":
            context.user_data['shift_data']['qr'] = 0.0
            return await self._continue_to_card2(query, context)
        
        msg = "📱 Введите QR (только число):\n\nПример: 500"
        await query.edit_message_text(msg)
        return ENTER_QR
    
    async def receive_qr(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Receive QR revenue"""
        try:
            value = float(update.message.text.replace(' ', '').replace(',', '.'))
            context.user_data['shift_data']['qr'] = value
            
            return await self._continue_to_card2(update.message, context)
        except ValueError:
            await update.message.reply_text("❌ Неверный формат. Введите число:")
            return ENTER_QR
    
    async def _continue_to_card2(self, message_or_query, context: ContextTypes.DEFAULT_TYPE):
        """Continue to card2 input"""
        msg = f"✅ QR: {context.user_data['shift_data']['qr']:,.0f} ₽\n\n"
        msg += "💳 Введите Новую кассу (Карта2):"
        
        keyboard = [
            [InlineKeyboardButton("Ввести вручную", callback_data="enter_manual")],
            [InlineKeyboardButton("0 (не работает)", callback_data="value_0")],
            [InlineKeyboardButton("❌ Отменить", callback_data="shift_cancel")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        if hasattr(message_or_query, 'reply_text'):
            await message_or_query.reply_text(msg, reply_markup=reply_markup)
        else:
            await message_or_query.edit_message_text(msg, reply_markup=reply_markup)
        
        return ENTER_CARD2
    
    async def prompt_card2(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Prompt for card2 revenue input"""
        query = update.callback_query
        await query.answer()
        
        if query.data == "value_0":
            context.user_data['shift_data']['card2'] = 0.0
            return await self._continue_to_safe(query, context)
        
        msg = "💳 Введите Новую кассу (только число):\n\nПример: 1000"
        await query.edit_message_text(msg)
        return ENTER_CARD2
    
    async def receive_card2(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Receive card2 revenue"""
        try:
            value = float(update.message.text.replace(' ', '').replace(',', '.'))
            context.user_data['shift_data']['card2'] = value
            
            return await self._continue_to_safe(update.message, context)
        except ValueError:
            await update.message.reply_text("❌ Неверный формат. Введите число:")
            return ENTER_CARD2
    
    async def _continue_to_safe(self, message_or_query, context: ContextTypes.DEFAULT_TYPE):
        """Continue to safe input"""
        msg = f"✅ Новая касса: {context.user_data['shift_data']['card2']:,.0f} ₽\n\n"
        msg += "🔐 Остатки - Сейф (основная):"
        
        keyboard = [
            [InlineKeyboardButton("Ввести вручную", callback_data="enter_manual")],
            [InlineKeyboardButton("❌ Отменить", callback_data="shift_cancel")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        if hasattr(message_or_query, 'reply_text'):
            await message_or_query.reply_text(msg, reply_markup=reply_markup)
        else:
            await message_or_query.edit_message_text(msg, reply_markup=reply_markup)
        
        return ENTER_SAFE
    
    async def prompt_safe(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Prompt for safe balance input"""
        query = update.callback_query
        await query.answer()
        
        msg = "🔐 Введите остаток в сейфе (только число):\n\nПример: 5000"
        await query.edit_message_text(msg)
        return ENTER_SAFE
    
    async def receive_safe(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Receive safe balance"""
        try:
            value = float(update.message.text.replace(' ', '').replace(',', '.'))
            context.user_data['shift_data']['safe_cash_end'] = value
            
            msg = f"✅ Сейф: {value:,.0f} ₽\n\n"
            msg += "📦 Введите остаток в коробке:"
            
            keyboard = [
                [InlineKeyboardButton("Ввести вручную", callback_data="enter_manual")],
                [InlineKeyboardButton("❌ Отменить", callback_data="shift_cancel")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(msg, reply_markup=reply_markup)
            return ENTER_BOX
        except ValueError:
            await update.message.reply_text("❌ Неверный формат. Введите число:")
            return ENTER_SAFE
    
    async def prompt_box(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Prompt for box balance input"""
        query = update.callback_query
        await query.answer()
        
        msg = "📦 Введите остаток в коробке (только число):\n\nПример: 2000"
        await query.edit_message_text(msg)
        return ENTER_BOX
    
    async def receive_box(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Receive box balance"""
        try:
            value = float(update.message.text.replace(' ', '').replace(',', '.'))
            context.user_data['shift_data']['box_cash_end'] = value
            
            # Move to summary
            return await self._show_summary(update.message, context)
        except ValueError:
            await update.message.reply_text("❌ Неверный формат. Введите число:")
            return ENTER_BOX
    
    async def _show_summary(self, message_or_query, context: ContextTypes.DEFAULT_TYPE):
        """Show summary with previous balances and deltas"""
        club = context.user_data['shift_club']
        shift_time = context.user_data['shift_time']
        shift_label = "☀️ Утро (ночная смена)" if shift_time == "morning" else "🌙 Вечер (дневная смена)"
        data = context.user_data['shift_data']
        
        prev_official = context.user_data.get('prev_official', 0)
        prev_box = context.user_data.get('prev_box', 0)
        
        new_official = data['safe_cash_end']
        new_box = data['box_cash_end']
        
        delta_official = new_official - prev_official
        delta_box = new_box - prev_box
        
        msg = "📊 Сводка смены\n\n"
        msg += f"🏢 Клуб: {club}\n"
        msg += f"⏰ Время: {shift_label}\n\n"
        
        msg += "💰 Выручка:\n"
        msg += f"  • Наличка факт: {data['fact_cash']:,.0f} ₽\n"
        msg += f"  • Карта факт: {data['fact_card']:,.0f} ₽\n"
        msg += f"  • QR: {data['qr']:,.0f} ₽\n"
        msg += f"  • Новая касса: {data['card2']:,.0f} ₽\n\n"
        
        msg += "🔐 Остатки:\n"
        msg += f"  • Сейф (офиц): {new_official:,.0f} ₽\n"
        msg += f"  • Коробка: {new_box:,.0f} ₽\n\n"
        
        msg += "📈 Прошлый раз:\n"
        msg += f"  • Основная: {prev_official:,.0f} ₽\n"
        msg += f"  • Коробка: {prev_box:,.0f} ₽\n\n"
        
        msg += "📊 Движение:\n"
        msg += f"  • Основная: {delta_official:+,.0f} ₽\n"
        msg += f"  • Коробка: {delta_box:+,.0f} ₽\n"
        
        keyboard = [
            [InlineKeyboardButton("✅ Подтвердить", callback_data="shift_confirm")],
            [InlineKeyboardButton("✏️ Изменить", callback_data="shift_edit")],
            [InlineKeyboardButton("❌ Отменить", callback_data="shift_cancel")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        if hasattr(message_or_query, 'reply_text'):
            await message_or_query.reply_text(msg, reply_markup=reply_markup)
        else:
            await message_or_query.edit_message_text(msg, reply_markup=reply_markup)
        
        return CONFIRM_SHIFT
    
    async def confirm_shift(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Confirm and save shift"""
        query = update.callback_query
        await query.answer()
        
        data = context.user_data.get('shift_data')
        club = context.user_data.get('shift_club')
        shift_time = context.user_data.get('shift_time')
        
        # Add club to data
        data['club'] = club
        
        # Get shift date
        shift_window = context.user_data.get('shift_window')
        if shift_window:
            shift_date = shift_window['shift_date']
        else:
            shift_date = date.today()
        
        # Get duty name from schedule
        duty_name = ""
        if self.schedule:
            duty_name = self.schedule.get_duty_name(club, shift_date, shift_time) or ""
        
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
            balances = self.finmon.get_club_balances(club)
            
            msg = "✅ Смена успешно сдана!\n\n"
            msg += f"🏢 {club}\n"
            msg += f"💰 Остатки:\n"
            msg += f"  • Офиц (сейф): {balances['official']:,.0f} ₽\n"
            msg += f"  • Коробка: {balances['box']:,.0f} ₽\n"
            
            await query.edit_message_text(msg)
        else:
            await query.edit_message_text("❌ Ошибка при сохранении смены")
        
        # Clear context
        context.user_data.clear()
        
        return ConversationHandler.END
    
    async def edit_shift(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Edit shift - restart from beginning"""
        query = update.callback_query
        await query.answer()
        
        club = context.user_data.get('shift_club')
        
        # Clear shift data but keep club
        context.user_data['shift_data'] = {
            'fact_cash': 0.0,
            'fact_card': 0.0,
            'qr': 0.0,
            'card2': 0.0,
            'safe_cash_end': 0.0,
            'box_cash_end': 0.0,
            'tovarka': 0.0,
            'gamepads': 0,
            'repair': 0,
            'need_repair': 0,
            'games': 0
        }
        
        msg = f"📋 Сдача смены\n\n🏢 Клуб: {club}\n\nВыберите время смены:"
        
        keyboard = [
            [InlineKeyboardButton("☀️ Утро", callback_data="shift_time_morning")],
            [InlineKeyboardButton("🌙 Вечер", callback_data="shift_time_evening")],
            [InlineKeyboardButton("❌ Отменить", callback_data="shift_cancel")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(msg, reply_markup=reply_markup)
        return SELECT_SHIFT_TIME
    
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
    
    async def cmd_shift_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show shift menu in club chats"""
        chat_id = update.effective_chat.id
        club = self.finmon.get_club_from_chat(chat_id)
        
        if not club:
            await update.message.reply_text(
                "⚠️ Эта команда доступна только в чатах клубов.\n"
                "Используйте /shift для сдачи смены."
            )
            return
        
        msg = f"📋 Меню смены - {club}\n\n"
        msg += "Доступные команды:\n"
        msg += "• /shift - Сдать смену\n"
        msg += "• /balances - Текущие остатки\n"
        msg += "• /movements - Последние движения\n"
        
        keyboard = [
            [InlineKeyboardButton("📋 Сдать смену", callback_data="menu_shift")],
            [InlineKeyboardButton("💰 Остатки", callback_data="menu_balances")],
            [InlineKeyboardButton("📊 Движения", callback_data="menu_movements")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(msg, reply_markup=reply_markup)
    
    async def handle_menu_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle menu button callbacks"""
        query = update.callback_query
        await query.answer()
        
        if query.data == "menu_shift":
            # Start shift wizard
            await query.message.delete()
            # Create a fake update for cmd_shift
            fake_update = update
            fake_update.message = query.message
            return await self.cmd_shift(fake_update, context)
        elif query.data == "menu_balances":
            text = self.finmon.format_balances()
            await query.edit_message_text(text)
        elif query.data == "menu_movements":
            chat_id = query.message.chat.id
            club = self.finmon.get_club_from_chat(chat_id)
            if club:
                text = self.finmon.format_movements(club, limit=10)
            else:
                text = "Не удалось определить клуб"
            await query.edit_message_text(text)
