#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FinMon Shift Wizard - Button-based shift submission
Handles /shift command with step-by-step wizard
"""

import logging
from datetime import datetime, date, timedelta
from typing import Optional, Dict

# Try to use zoneinfo (Python 3.9+), fallback to pytz if needed
try:
    from zoneinfo import ZoneInfo
    PYTZ_AVAILABLE = False
except ImportError:
    try:
        import pytz
        PYTZ_AVAILABLE = True
    except ImportError:
        # Neither available, will use naive datetime
        PYTZ_AVAILABLE = False
        pytz = None

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler

logger = logging.getLogger(__name__)

# Conversation states
(SELECT_CLUB, SELECT_SHIFT_TIME, CONFIRM_IDENTITY, ENTER_FACT_CASH, ENTER_FACT_CARD, 
 ENTER_QR, ENTER_CARD2, MANAGE_EXPENSES, ENTER_EXPENSE_AMOUNT, ENTER_EXPENSE_REASON,
 ENTER_SAFE, ENTER_BOX, ENTER_TOVARKA, ENTER_GAMEPADS, ENTER_REPAIR, 
 ENTER_NEED_REPAIR, ENTER_GAMES, CONFIRM_SHIFT) = range(18)

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
    try:
        if PYTZ_AVAILABLE:
            msk = pytz.timezone(TIMEZONE)
            return datetime.now(msk)
        else:
            # Use zoneinfo (Python 3.9+)
            msk = ZoneInfo(TIMEZONE)
            return datetime.now(msk)
    except Exception as e:
        # Fallback to naive datetime if timezone not available
        logger.warning(f"⚠️ Timezone conversion failed: {e}, using naive datetime")
        return datetime.now()


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
        
        # Show identity confirmation
        user = update.effective_user
        username = f"@{user.username}" if user.username else "Без username"
        full_name = user.full_name or "Без имени"
        
        # Get expected duty name from schedule if available
        shift_window = context.user_data.get('shift_window')
        shift_date = shift_window['shift_date'] if shift_window else date.today()
        duty_name = ""
        if self.schedule:
            duty_name = self.schedule.get_duty_name(club, shift_date, shift_time) or ""
        
        msg = f"👤 Подтверждение личности\n\n"
        msg += f"🏢 Клуб: {club}\n"
        msg += f"⏰ Время: {shift_label}\n\n"
        msg += f"Вы: {full_name}\n"
        msg += f"Telegram: {username}\n"
        msg += f"ID: {user.id}\n\n"
        
        if duty_name:
            msg += f"⚠️ По расписанию дежурный: {duty_name}\n\n"
        
        msg += "Подтвердите, что это вы сдаёте смену:"
        
        keyboard = [
            [InlineKeyboardButton("✅ Подтверждаю, это я", callback_data="confirm_identity")],
            [InlineKeyboardButton("❌ Отменить", callback_data="shift_cancel")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(msg, reply_markup=reply_markup)
        return CONFIRM_IDENTITY
    
    async def confirm_identity(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle identity confirmation"""
        query = update.callback_query
        await query.answer()
        
        # Store confirmation
        context.user_data['identity_confirmed'] = True
        context.user_data['confirmation_timestamp'] = datetime.now().isoformat()
        
        club = context.user_data['shift_club']
        shift_time = context.user_data['shift_time']
        shift_label = "☀️ Утро (ночная смена)" if shift_time == "morning" else "🌙 Вечер (дневная смена)"
        prev_official = context.user_data.get('prev_official', 0)
        prev_box = context.user_data.get('prev_box', 0)
        
        msg = f"📋 Сдача смены\n\n"
        msg += f"🏢 Клуб: {club}\n"
        msg += f"⏰ Время: {shift_label}\n\n"
        msg += f"📊 Прошлые остатки:\n"
        msg += f"  • Основная: {prev_official:,.0f} ₽\n"
        msg += f"  • Коробка: {prev_box:,.0f} ₽\n\n"
        msg += "💰 Введите наличку факт:\n\nПример: 3440"
        
        await query.edit_message_text(msg)
        return ENTER_FACT_CASH
    
    async def receive_fact_cash(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Receive cash revenue"""
        try:
            value = float(update.message.text.replace(' ', '').replace(',', '.'))
            context.user_data['shift_data']['fact_cash'] = value
            
            msg = f"✅ Наличка факт: {value:,.0f} ₽\n\n"
            msg += "💳 Введите карту факт:\n\nПример: 12345"
            
            await update.message.reply_text(msg)
            return ENTER_FACT_CARD
        except ValueError:
            await update.message.reply_text("❌ Неверный формат. Введите число:")
            return ENTER_FACT_CASH
    
    async def receive_fact_card(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Receive card revenue"""
        try:
            value = float(update.message.text.replace(' ', '').replace(',', '.'))
            context.user_data['shift_data']['fact_card'] = value
            
            msg = f"✅ Карта факт: {value:,.0f} ₽\n\n"
            msg += "📱 Введите QR:\n\nПример: 500 (или 0 если нет)"
            
            await update.message.reply_text(msg)
            return ENTER_QR
        except ValueError:
            await update.message.reply_text("❌ Неверный формат. Введите число:")
            return ENTER_FACT_CARD
    
    async def receive_qr(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Receive QR revenue"""
        try:
            value = float(update.message.text.replace(' ', '').replace(',', '.'))
            context.user_data['shift_data']['qr'] = value
            
            msg = f"✅ QR: {value:,.0f} ₽\n\n"
            msg += "💳 Введите Новую кассу (Карта2):\n\nПример: 1000 (или 0 если не работает)"
            
            await update.message.reply_text(msg)
            return ENTER_CARD2
        except ValueError:
            await update.message.reply_text("❌ Неверный формат. Введите число:")
            return ENTER_QR
    
    async def receive_card2(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Receive card2 revenue"""
        try:
            value = float(update.message.text.replace(' ', '').replace(',', '.'))
            context.user_data['shift_data']['card2'] = value
            
            # Show expenses management menu
            return await self._show_expenses_menu(update.message, context)
        except ValueError:
            await update.message.reply_text("❌ Неверный формат. Введите число:")
            return ENTER_CARD2
    
    # ===== Expenses Management =====
    
    async def _show_expenses_menu(self, message_or_query, context: ContextTypes.DEFAULT_TYPE):
        """Show expenses management menu"""
        expenses = context.user_data.get('expenses', [])
        total_expenses = sum(exp['amount'] for exp in expenses)
        
        msg = f"✅ Новая касса: {context.user_data['shift_data']['card2']:,.0f} ₽\n\n"
        msg += "💸 Управление расходами\n\n"
        
        if expenses:
            msg += f"Списано наличных: {total_expenses:,.0f} ₽\n\n"
            for i, exp in enumerate(expenses, 1):
                msg += f"{i}. {exp['amount']:,.0f} ₽ - {exp['reason']}\n"
            msg += "\n"
        else:
            msg += "Расходов пока нет\n\n"
        
        msg += "Выберите действие:"
        
        keyboard = [
            [InlineKeyboardButton("💸 Списать расход", callback_data="add_expense")],
            [InlineKeyboardButton("➡️ Продолжить к остаткам", callback_data="skip_expenses")],
            [InlineKeyboardButton("❌ Отменить", callback_data="shift_cancel")]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        if hasattr(message_or_query, 'reply_text'):
            await message_or_query.reply_text(msg, reply_markup=reply_markup)
        else:
            await message_or_query.edit_message_text(msg, reply_markup=reply_markup)
        
        return MANAGE_EXPENSES
    
    async def start_add_expense(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start adding expense"""
        query = update.callback_query
        await query.answer()
        
        msg = "💸 Списание расхода\n\n"
        msg += "Введите сумму которая была выдана из кассы:\n\nПример: 1500"
        
        await query.edit_message_text(msg)
        return ENTER_EXPENSE_AMOUNT
    
    async def receive_expense_amount(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Receive expense amount"""
        try:
            amount = float(update.message.text.replace(' ', '').replace(',', '.'))
            if amount <= 0:
                await update.message.reply_text("❌ Сумма должна быть больше 0. Попробуйте снова:")
                return ENTER_EXPENSE_AMOUNT
            
            context.user_data['temp_expense_amount'] = amount
            
            msg = f"✅ Сумма: {amount:,.0f} ₽\n\n"
            msg += "Введите причину списания:\n\n"
            msg += "Примеры:\n"
            msg += "• Выдано игроку\n"
            msg += "• Оплата поставщику\n"
            msg += "• Сдача клиенту\n"
            msg += "• Расходы на закупку"
            
            await update.message.reply_text(msg)
            return ENTER_EXPENSE_REASON
        except ValueError:
            await update.message.reply_text("❌ Неверный формат. Введите число:")
            return ENTER_EXPENSE_AMOUNT
    
    async def receive_expense_reason(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Receive expense reason"""
        reason = update.message.text.strip()
        
        if not reason or len(reason) > 200:
            await update.message.reply_text(
                "❌ Причина должна быть от 1 до 200 символов. Попробуйте снова:"
            )
            return ENTER_EXPENSE_REASON
        
        amount = context.user_data.get('temp_expense_amount', 0)
        
        # Add expense to list
        if 'expenses' not in context.user_data:
            context.user_data['expenses'] = []
        
        context.user_data['expenses'].append({
            'amount': amount,
            'reason': reason
        })
        
        # Clear temp data
        context.user_data.pop('temp_expense_amount', None)
        
        # Show expenses menu again
        return await self._show_expenses_menu(update.message, context)
    
    async def skip_expenses(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Skip to safe input"""
        query = update.callback_query
        await query.answer()
        
        return await self._continue_to_safe(query, context)
    
    # ===== Safe and Box Input =====
    
    async def _continue_to_safe(self, message_or_query, context: ContextTypes.DEFAULT_TYPE):
        """Continue to safe input"""
        prev_official = context.user_data.get('prev_official', 0)
        
        msg = f"✅ Выручка введена\n\n"
        msg += "🔐 Введите остаток в сейфе (основная касса):\n\n"
        msg += f"Пример: 5000\n"
        msg += f"Прошлый раз было: {prev_official:,.0f} ₽"
        
        keyboard = [
            [InlineKeyboardButton("📦 Без изменений", callback_data="safe_no_change")],
            [InlineKeyboardButton("❌ Отменить", callback_data="shift_cancel")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        if hasattr(message_or_query, 'reply_text'):
            await message_or_query.reply_text(msg, reply_markup=reply_markup)
        else:
            await message_or_query.edit_message_text(msg, reply_markup=reply_markup)
        
        return ENTER_SAFE
    
    async def handle_safe_no_change(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle 'no change' button for safe"""
        query = update.callback_query
        await query.answer()
        
        # Use previous balance
        prev_official = context.user_data.get('prev_official', 0)
        context.user_data['shift_data']['safe_cash_end'] = prev_official
        
        return await self._continue_to_box(query, context)
    
    async def receive_safe(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Receive safe balance"""
        try:
            value = float(update.message.text.replace(' ', '').replace(',', '.'))
            context.user_data['shift_data']['safe_cash_end'] = value
            
            return await self._continue_to_box(update.message, context)
        except ValueError:
            await update.message.reply_text("❌ Неверный формат. Введите число:")
            return ENTER_SAFE
    
    async def _continue_to_box(self, message_or_query, context: ContextTypes.DEFAULT_TYPE):
        """Continue to box input"""
        prev_box = context.user_data.get('prev_box', 0)
        safe_value = context.user_data['shift_data']['safe_cash_end']
        
        msg = f"✅ Сейф: {safe_value:,.0f} ₽\n\n"
        msg += "📦 Введите остаток в коробке:\n\n"
        msg += f"Пример: 2000\n"
        msg += f"Прошлый раз было: {prev_box:,.0f} ₽"
        
        keyboard = [
            [InlineKeyboardButton("📦 Без изменений", callback_data="box_no_change")],
            [InlineKeyboardButton("❌ Отменить", callback_data="shift_cancel")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        if hasattr(message_or_query, 'reply_text'):
            await message_or_query.reply_text(msg, reply_markup=reply_markup)
        else:
            await message_or_query.edit_message_text(msg, reply_markup=reply_markup)
        
        return ENTER_BOX
    
    async def handle_box_no_change(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle 'no change' button for box"""
        query = update.callback_query
        await query.answer()
        
        # Use previous balance
        prev_box = context.user_data.get('prev_box', 0)
        context.user_data['shift_data']['box_cash_end'] = prev_box
        
        # Move to summary
        return await self._show_summary(query, context)
    
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
        """Show summary with previous balances, deltas and expenses"""
        club = context.user_data['shift_club']
        shift_time = context.user_data['shift_time']
        shift_label = "☀️ Утро (ночная смена)" if shift_time == "morning" else "🌙 Вечер (дневная смена)"
        data = context.user_data['shift_data']
        expenses = context.user_data.get('expenses', [])
        
        prev_official = context.user_data.get('prev_official', 0)
        prev_box = context.user_data.get('prev_box', 0)
        
        new_official = data['safe_cash_end']
        new_box = data['box_cash_end']
        
        delta_official = new_official - prev_official
        delta_box = new_box - prev_box
        
        # Calculate total expenses
        total_expenses = sum(exp['amount'] for exp in expenses)
        
        msg = "📊 Сводка смены\n\n"
        msg += f"🏢 Клуб: {club}\n"
        msg += f"⏰ Время: {shift_label}\n\n"
        
        msg += "💰 Выручка:\n"
        msg += f"  • Наличка факт: {data['fact_cash']:,.0f} ₽\n"
        msg += f"  • Карта факт: {data['fact_card']:,.0f} ₽\n"
        msg += f"  • QR: {data['qr']:,.0f} ₽\n"
        msg += f"  • Новая касса: {data['card2']:,.0f} ₽\n"
        
        if expenses:
            msg += f"\n💸 Расходы (списано):\n"
            for exp in expenses:
                msg += f"  • {exp['amount']:,.0f} ₽ - {exp['reason']}\n"
            msg += f"  ИТОГО: {total_expenses:,.0f} ₽\n"
        
        msg += "\n🔐 Остатки:\n"
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
        expenses = context.user_data.get('expenses', [])
        
        # Add club and expenses to data
        data['club'] = club
        data['expenses'] = expenses
        
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
        
        # Get identity confirmation data
        identity_confirmed = context.user_data.get('identity_confirmed', False)
        confirmation_timestamp = context.user_data.get('confirmation_timestamp', '')
        
        # Submit shift with expenses and confirmation
        success = self.finmon.submit_shift(
            data,
            admin_id,
            admin_username,
            shift_date,
            shift_time,
            duty_name,
            identity_confirmed=identity_confirmed,
            confirmation_timestamp=confirmation_timestamp
        )
        
        if success:
            # Get updated balances
            balances = self.finmon.get_club_balances(club)
            
            total_expenses = sum(exp['amount'] for exp in expenses)
            
            msg = "✅ Смена успешно сдана!\n\n"
            msg += f"🏢 {club}\n"
            if expenses:
                msg += f"💸 Списано расходов: {total_expenses:,.0f} ₽\n"
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
        
        # Clear shift data and expenses but keep club
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
        context.user_data['expenses'] = []
        
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
    
    # ===== Financial Monitoring Analytics =====
    
    async def cmd_finmon(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show financial monitoring menu"""
        # Owner only
        if not self.is_owner(update.effective_user.id):
            await update.message.reply_text("❌ Эта команда доступна только владельцу")
            return
        
        if not ANALYTICS_AVAILABLE:
            await update.message.reply_text("❌ Модуль аналитики недоступен")
            return
        
        text = """📊 Финансовый мониторинг
━━━━━━━━━━━━━━━━━━━━
Выберите отчет:"""
        
        keyboard = [
            [InlineKeyboardButton("📊 Выручка за период", callback_data="finmon_revenue")],
            [InlineKeyboardButton("🏢 Разбивка по клубам", callback_data="finmon_clubs")],
            [InlineKeyboardButton("👥 Сравнение админов", callback_data="finmon_admins")],
            [InlineKeyboardButton("⚠️ Выявление аномалий", callback_data="finmon_anomalies")],
            [InlineKeyboardButton("📈 История остатков", callback_data="finmon_history")]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        if update.message:
            await update.message.reply_text(text, reply_markup=reply_markup)
        else:
            await update.callback_query.edit_message_text(text, reply_markup=reply_markup)
    
    async def handle_finmon_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle finmon analytics callbacks"""
        query = update.callback_query
        await query.answer()
        
        if not self.is_owner(query.from_user.id):
            await query.answer("❌ Только для владельца", show_alert=True)
            return
        
        if not ANALYTICS_AVAILABLE:
            await query.edit_message_text("❌ Модуль аналитики недоступен")
            return
        
        analytics = FinMonAnalytics()
        
        # Revenue summary
        if query.data == "finmon_revenue":
            keyboard = [
                [
                    InlineKeyboardButton("День", callback_data="finmon_rev_day"),
                    InlineKeyboardButton("Неделя", callback_data="finmon_rev_week"),
                    InlineKeyboardButton("Месяц", callback_data="finmon_rev_month")
                ],
                [InlineKeyboardButton("◀️ Назад", callback_data="finmon_menu")]
            ]
            await query.edit_message_text(
                "📊 Выберите период:",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        
        elif query.data.startswith("finmon_rev_"):
            period = query.data.split('_')[-1]  # day, week, month
            summary = analytics.get_revenue_summary(period)
            text = analytics.format_revenue_summary(summary)
            
            keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data="finmon_revenue")]]
            await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
        
        # Club breakdown
        elif query.data == "finmon_clubs":
            keyboard = [
                [
                    InlineKeyboardButton("День", callback_data="finmon_club_day"),
                    InlineKeyboardButton("Неделя", callback_data="finmon_club_week"),
                    InlineKeyboardButton("Месяц", callback_data="finmon_club_month")
                ],
                [InlineKeyboardButton("◀️ Назад", callback_data="finmon_menu")]
            ]
            await query.edit_message_text(
                "🏢 Выберите период:",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        
        elif query.data.startswith("finmon_club_"):
            period = query.data.split('_')[-1]
            breakdown = analytics.get_club_breakdown(period)
            text = analytics.format_club_breakdown(breakdown, period)
            
            keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data="finmon_clubs")]]
            await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
        
        # Admin comparison
        elif query.data == "finmon_admins":
            keyboard = [
                [InlineKeyboardButton("Все клубы", callback_data="finmon_adm_all")],
                [InlineKeyboardButton("🏢 Рио", callback_data="finmon_adm_rio")],
                [InlineKeyboardButton("🏢 Север", callback_data="finmon_adm_sever")],
                [InlineKeyboardButton("◀️ Назад", callback_data="finmon_menu")]
            ]
            await query.edit_message_text(
                "👥 Выберите клуб:",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        
        elif query.data.startswith("finmon_adm_"):
            club_code = query.data.split('_')[-1]
            club = None if club_code == 'all' else ('Рио' if club_code == 'rio' else 'Север')
            
            admins = analytics.get_admin_comparison('month', club, weekday=4)  # Friday
            text = analytics.format_admin_comparison(admins, club, "Пятницы")
            
            keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data="finmon_admins")]]
            await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
        
        # Anomalies detection
        elif query.data == "finmon_anomalies":
            anomalies = analytics.detect_anomalies('month', threshold=0.15, min_shifts=3)
            text = analytics.format_anomalies(anomalies)
            
            keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data="finmon_menu")]]
            await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
        
        # Balance history
        elif query.data == "finmon_history":
            keyboard = [
                [InlineKeyboardButton("Все клубы", callback_data="finmon_hist_all")],
                [InlineKeyboardButton("🏢 Рио", callback_data="finmon_hist_rio")],
                [InlineKeyboardButton("🏢 Север", callback_data="finmon_hist_sever")],
                [InlineKeyboardButton("◀️ Назад", callback_data="finmon_menu")]
            ]
            await query.edit_message_text(
                "📈 Выберите клуб:",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        
        elif query.data.startswith("finmon_hist_"):
            club_code = query.data.split('_')[-1]
            club = None if club_code == 'all' else ('Рио' if club_code == 'rio' else 'Север')
            
            history = analytics.get_balance_history(30, club)
            text = analytics.format_balance_history(history, club)
            
            keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data="finmon_history")]]
            await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
        
        # Back to main menu
        elif query.data == "finmon_menu":
            await self.cmd_finmon(update, context)