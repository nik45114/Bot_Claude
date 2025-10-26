#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FinMon Wizard - Conversation Handler for Shift Submission
"""

import logging
from datetime import datetime, date, timedelta
from typing import Optional, Dict, Any
import pytz
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from .models import Shift
from .db import FinMonDB
from .sheets import GoogleSheetsSync

logger = logging.getLogger(__name__)

# Shift configuration constants
TIMEZONE = 'Europe/Moscow'
SHIFT_CLOSE_TIMES = {
    'morning': '10:00',
    'evening': '22:00'
}
EARLY_CLOSE_OFFSET_HOURS = 1  # Allow early close 1 hour before
GRACE_MINUTES_AFTER_CLOSE = 60  # Grace period after official close time

# Состояния conversation handler
(SELECT_CLUB, SELECT_TIME, ENTER_FACT_CASH, ENTER_FACT_CARD, ENTER_QR, ENTER_CARD2,
 ENTER_SAFE_CASH, ENTER_BOX_CASH, ENTER_GOODS_CASH,
 ENTER_COMPENSATIONS, ENTER_SALARY, ENTER_OTHER_EXPENSES,
 ENTER_JOYSTICKS_TOTAL, ENTER_JOYSTICKS_REPAIR, ENTER_JOYSTICKS_NEED, ENTER_GAMES,
 SELECT_TOILET_PAPER, SELECT_PAPER_TOWELS,
 ENTER_NOTES, CONFIRM_SHIFT) = range(20)


def now_msk() -> datetime:
    """Get current time in Moscow timezone"""
    msk = pytz.timezone(TIMEZONE)
    return datetime.now(msk)


def parse_msk_time(time_str: str, ref_date: date = None) -> datetime:
    """
    Parse time string (HH:MM) to MSK datetime
    
    Args:
        time_str: Time in format "HH:MM"
        ref_date: Reference date (default: today in MSK)
    
    Returns:
        datetime object in MSK timezone
    """
    if ref_date is None:
        ref_date = now_msk().date()
    
    msk = pytz.timezone(TIMEZONE)
    hour, minute = map(int, time_str.split(':'))
    dt = datetime(ref_date.year, ref_date.month, ref_date.day, hour, minute)
    return msk.localize(dt)


def is_within_window(
    now: datetime,
    close_time_str: str,
    early_offset_hours: int,
    grace_minutes: int,
    ref_date: date = None
) -> bool:
    """
    Check if current time is within the shift close window
    
    Args:
        now: Current datetime in MSK
        close_time_str: Official close time (HH:MM)
        early_offset_hours: Hours before close time for early closing
        grace_minutes: Minutes after close time (grace period)
        ref_date: Reference date for the shift
    
    Returns:
        True if within window, False otherwise
    """
    if ref_date is None:
        ref_date = now.date()
    
    close_time = parse_msk_time(close_time_str, ref_date)
    early_time = close_time - timedelta(hours=early_offset_hours)
    grace_end = close_time + timedelta(minutes=grace_minutes)
    
    return early_time <= now <= grace_end


def get_current_shift_for_close() -> Optional[Dict[str, Any]]:
    """
    Auto-detect which shift should be closed based on current MSK time
    
    Returns:
        Dictionary with shift_time, shift_date, and reason, or None if outside windows
        {
            'shift_time': 'morning' or 'evening',
            'shift_date': date object,
            'reason': 'auto' or 'early' or 'grace'
        }
    """
    now = now_msk()
    today = now.date()
    current_hour = now.hour
    current_minute = now.minute
    
    # Morning shift window: 09:00 - 11:00 (10:00 ± 1 hour + grace)
    if is_within_window(now, SHIFT_CLOSE_TIMES['morning'], 
                        EARLY_CLOSE_OFFSET_HOURS, GRACE_MINUTES_AFTER_CLOSE):
        # Determine reason
        close_time = parse_msk_time(SHIFT_CLOSE_TIMES['morning'], today)
        early_time = close_time - timedelta(hours=EARLY_CLOSE_OFFSET_HOURS)
        
        if now < close_time:
            reason = 'early' if now >= early_time else 'auto'
        else:
            reason = 'grace'
        
        return {
            'shift_time': 'morning',
            'shift_date': today,
            'reason': reason
        }
    
    # Evening shift window: 21:00 - 23:00 (22:00 ± 1 hour + grace)
    # Plus grace window from 00:00 to 00:30 next day for late evening shifts
    if is_within_window(now, SHIFT_CLOSE_TIMES['evening'],
                        EARLY_CLOSE_OFFSET_HOURS, GRACE_MINUTES_AFTER_CLOSE):
        close_time = parse_msk_time(SHIFT_CLOSE_TIMES['evening'], today)
        early_time = close_time - timedelta(hours=EARLY_CLOSE_OFFSET_HOURS)
        
        if now < close_time:
            reason = 'early' if now >= early_time else 'auto'
        else:
            reason = 'grace'
        
        return {
            'shift_time': 'evening',
            'shift_date': today,
            'reason': reason
        }
    
    # Special case: Very early morning (00:00 - 00:30) - might be closing yesterday's evening shift
    if current_hour == 0 and current_minute <= 30:
        yesterday = today - timedelta(days=1)
        yesterday_evening_close = parse_msk_time(SHIFT_CLOSE_TIMES['evening'], yesterday)
        grace_end = yesterday_evening_close + timedelta(minutes=GRACE_MINUTES_AFTER_CLOSE)
        
        if now <= grace_end:
            return {
                'shift_time': 'evening',
                'shift_date': yesterday,
                'reason': 'grace'
            }
    
    return None


class FinMonWizard:
    """Wizard для сдачи смены"""
    
    def __init__(self, db: FinMonDB, sheets: GoogleSheetsSync, owner_ids: list):
        self.db = db
        self.sheets = sheets
        self.owner_ids = owner_ids
    
    def is_owner(self, user_id: int) -> bool:
        """Проверка что пользователь - владелец"""
        return user_id in self.owner_ids
    
    async def cmd_shift(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Начать сдачу смены - /shift"""
        user_id = update.effective_user.id
        
        # Инициализация данных в context
        context.user_data['shift_data'] = {}
        
        # Выбор клуба
        clubs = self.db.get_clubs()
        
        # Auto-detect current shift
        detected_shift = get_current_shift_for_close()
        
        keyboard = []
        for club in clubs:
            club_label = self.db.get_club_display_name(club['id'])
            keyboard.append([
                InlineKeyboardButton(club_label, callback_data=f"finmon_club_{club['id']}")
            ])
        
        keyboard.append([InlineKeyboardButton("❌ Отмена", callback_data="finmon_cancel")])
        
        # Build message with auto-detection info
        message = "📊 СДАЧА СМЕНЫ\n\n"
        
        if detected_shift:
            shift_emoji = "☀️" if detected_shift['shift_time'] == 'morning' else "🌙"
            shift_label = "Утро" if detected_shift['shift_time'] == 'morning' else "Вечер"
            date_str = detected_shift['shift_date'].strftime('%d.%m')
            
            if detected_shift['reason'] == 'early':
                message += f"⏱️ Можно закрыть смену раньше:\n{shift_emoji} {shift_label} {date_str}\n\n"
            elif detected_shift['reason'] == 'grace':
                message += f"⏰ Период закрытия смены:\n{shift_emoji} {shift_label} {date_str}\n\n"
            else:
                message += f"✅ Время закрытия смены:\n{shift_emoji} {shift_label} {date_str}\n\n"
            
            # Store detected shift in context for later use
            context.user_data['detected_shift'] = detected_shift
        
        message += "Выберите клуб:"
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(message, reply_markup=reply_markup)
        
        return SELECT_CLUB
    
    async def select_club(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Выбор клуба"""
        query = update.callback_query
        await query.answer()
        
        club_id = int(query.data.split('_')[-1])
        context.user_data['shift_data']['club_id'] = club_id
        
        club_name = self.db.get_club_display_name(club_id)
        
        # Check if we have a detected shift
        detected_shift = context.user_data.get('detected_shift')
        
        keyboard = []
        message = f"📊 Клуб: {club_name}\n\n"
        
        if detected_shift:
            # Show auto-detected shift as primary option
            shift_emoji = "☀️" if detected_shift['shift_time'] == 'morning' else "🌙"
            shift_label = "Утро" if detected_shift['shift_time'] == 'morning' else "Вечер"
            date_str = detected_shift['shift_date'].strftime('%d.%m')
            
            button_text = f"Закрыть смену ({shift_emoji} {shift_label} {date_str})"
            keyboard.append([
                InlineKeyboardButton(button_text, callback_data="finmon_close_auto")
            ])
            
            # Add manual override options
            keyboard.append([InlineKeyboardButton("🔁 Выбрать вручную", callback_data="finmon_choose_manual")])
            keyboard.append([InlineKeyboardButton("⏱️ Закрыть раньше", callback_data="finmon_close_early")])
            
            message += "Выберите действие:"
        else:
            # No auto-detection, show manual options
            keyboard.append([InlineKeyboardButton("☀️ Закрыть утреннюю", callback_data="finmon_close_manual_morning")])
            keyboard.append([InlineKeyboardButton("🌙 Закрыть вечернюю", callback_data="finmon_close_manual_evening")])
            keyboard.append([InlineKeyboardButton("⏱️ Закрыть раньше", callback_data="finmon_close_early")])
            
            message += "Выберите смену для закрытия:"
        
        keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data="finmon_back_club")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(message, reply_markup=reply_markup)
        
        return SELECT_TIME
    
    async def close_auto(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Close shift using auto-detected time"""
        query = update.callback_query
        await query.answer()
        
        detected_shift = context.user_data.get('detected_shift')
        if not detected_shift:
            await query.edit_message_text("❌ Ошибка: смена не определена автоматически")
            return ConversationHandler.END
        
        # Set shift time and date from detection
        context.user_data['shift_data']['shift_time'] = detected_shift['shift_time']
        context.user_data['shift_data']['shift_date'] = detected_shift['shift_date']
        
        time_label = "Утро" if detected_shift['shift_time'] == "morning" else "Вечер"
        club_name = self.db.get_club_display_name(context.user_data['shift_data']['club_id'])
        
        await query.edit_message_text(
            f"📊 {club_name} - {time_label}\n\n"
            "💰 Введите ВЫРУЧКУ НАЛИЧНЫМИ (факт):\n"
            "(например: 2640 или 0)"
        )
        
        return ENTER_FACT_CASH
    
    async def close_manual_morning(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Manually close morning shift"""
        query = update.callback_query
        await query.answer()
        
        context.user_data['shift_data']['shift_time'] = 'morning'
        context.user_data['shift_data']['shift_date'] = now_msk().date()
        
        club_name = self.db.get_club_display_name(context.user_data['shift_data']['club_id'])
        
        await query.edit_message_text(
            f"📊 {club_name} - Утро\n\n"
            "💰 Введите ВЫРУЧКУ НАЛИЧНЫМИ (факт):\n"
            "(например: 2640 или 0)"
        )
        
        return ENTER_FACT_CASH
    
    async def close_manual_evening(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Manually close evening shift"""
        query = update.callback_query
        await query.answer()
        
        context.user_data['shift_data']['shift_time'] = 'evening'
        context.user_data['shift_data']['shift_date'] = now_msk().date()
        
        club_name = self.db.get_club_display_name(context.user_data['shift_data']['club_id'])
        
        await query.edit_message_text(
            f"📊 {club_name} - Вечер\n\n"
            "💰 Введите ВЫРУЧКУ НАЛИЧНЫМИ (факт):\n"
            "(например: 2640 или 0)"
        )
        
        return ENTER_FACT_CASH
    
    async def close_early(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Show options for early closure"""
        query = update.callback_query
        await query.answer()
        
        club_name = self.db.get_club_display_name(context.user_data['shift_data']['club_id'])
        
        # For early closure, show both shift options with today's date
        keyboard = [
            [InlineKeyboardButton("☀️ Утро (сегодня)", callback_data="finmon_early_morning_today")],
            [InlineKeyboardButton("🌙 Вечер (сегодня)", callback_data="finmon_early_evening_today")],
            [InlineKeyboardButton("☀️ Утро (вчера)", callback_data="finmon_early_morning_yesterday")],
            [InlineKeyboardButton("🌙 Вечер (вчера)", callback_data="finmon_early_evening_yesterday")],
            [InlineKeyboardButton("◀️ Назад", callback_data="finmon_back_to_shift_select")]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            f"📊 {club_name}\n\n"
            "⏱️ Выберите смену для раннего закрытия:",
            reply_markup=reply_markup
        )
        
        return SELECT_TIME
    
    async def early_shift_selected(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Handle early shift selection"""
        query = update.callback_query
        await query.answer()
        
        # Parse callback data: finmon_early_{shift}_{when}
        parts = query.data.split('_')
        shift_time = parts[2]  # morning or evening
        when = parts[3]  # today or yesterday
        
        today = now_msk().date()
        if when == 'yesterday':
            shift_date = today - timedelta(days=1)
        else:
            shift_date = today
        
        context.user_data['shift_data']['shift_time'] = shift_time
        context.user_data['shift_data']['shift_date'] = shift_date
        
        time_label = "Утро" if shift_time == "morning" else "Вечер"
        date_str = shift_date.strftime('%d.%m')
        club_name = self.db.get_club_display_name(context.user_data['shift_data']['club_id'])
        
        await query.edit_message_text(
            f"📊 {club_name} - {time_label} {date_str}\n\n"
            "💰 Введите ВЫРУЧКУ НАЛИЧНЫМИ (факт):\n"
            "(например: 2640 или 0)"
        )
        
        return ENTER_FACT_CASH
    
    async def choose_manual(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Switch to manual shift selection"""
        query = update.callback_query
        await query.answer()
        
        club_name = self.db.get_club_display_name(context.user_data['shift_data']['club_id'])
        
        keyboard = [
            [InlineKeyboardButton("☀️ Утро", callback_data="finmon_close_manual_morning")],
            [InlineKeyboardButton("🌙 Вечер", callback_data="finmon_close_manual_evening")],
            [InlineKeyboardButton("◀️ Назад", callback_data="finmon_back_to_shift_select")]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            f"📊 {club_name}\n\n"
            "Выберите время смены:",
            reply_markup=reply_markup
        )
        
        return SELECT_TIME
    
    async def back_to_shift_select(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Go back to shift selection"""
        # Re-run select_club logic
        return await self.select_club(update, context)
    
    async def select_time(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Выбор времени смены"""
        query = update.callback_query
        await query.answer()
        
        shift_time = query.data.split('_')[-1]
        context.user_data['shift_data']['shift_time'] = shift_time
        context.user_data['shift_data']['shift_date'] = date.today()
        
        time_label = "Утро" if shift_time == "morning" else "Вечер"
        club_name = self.db.get_club_display_name(context.user_data['shift_data']['club_id'])
        
        await query.edit_message_text(
            f"📊 {club_name} - {time_label}\n\n"
            "💰 Введите ВЫРУЧКУ НАЛИЧНЫМИ (факт):\n"
            "(например: 2640 или 0)"
        )
        
        return ENTER_FACT_CASH
    
    async def enter_fact_cash(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Ввод наличной выручки"""
        try:
            value = float(update.message.text.strip())
            context.user_data['shift_data']['fact_cash'] = value
            
            await update.message.reply_text(
                "💳 Введите ВЫРУЧКУ БЕЗНАЛИЧНЫМИ (факт безнал):\n"
                "(например: 5547 или 0)"
            )
            
            return ENTER_FACT_CARD
        except ValueError:
            await update.message.reply_text(
                "❌ Неверный формат! Введите число (например: 2640)"
            )
            return ENTER_FACT_CASH
    
    async def enter_fact_card(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Ввод безналичной выручки"""
        try:
            value = float(update.message.text.strip())
            context.user_data['shift_data']['fact_card'] = value
            
            await update.message.reply_text(
                "📱 Введите выручку QR:\n"
                "(например: 1680 или 0)"
            )
            
            return ENTER_QR
        except ValueError:
            await update.message.reply_text("❌ Неверный формат! Введите число")
            return ENTER_FACT_CARD
    
    async def enter_qr(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Ввод QR выручки"""
        try:
            value = float(update.message.text.strip())
            context.user_data['shift_data']['qr'] = value
            
            await update.message.reply_text(
                "💳 Введите выручку НОВАЯ КАССА (card2):\n"
                "(например: 0)"
            )
            
            return ENTER_CARD2
        except ValueError:
            await update.message.reply_text("❌ Неверный формат! Введите число")
            return ENTER_QR
    
    async def enter_card2(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Ввод card2"""
        try:
            value = float(update.message.text.strip())
            context.user_data['shift_data']['card2'] = value
            
            await update.message.reply_text(
                "🏦 Введите остаток в СЕЙФЕ на конец смены:\n"
                "(например: 927)"
            )
            
            return ENTER_SAFE_CASH
        except ValueError:
            await update.message.reply_text("❌ Неверный формат! Введите число")
            return ENTER_CARD2
    
    async def enter_safe_cash(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Ввод остатка в сейфе"""
        try:
            value = float(update.message.text.strip())
            context.user_data['shift_data']['safe_cash_end'] = value
            
            await update.message.reply_text(
                "📦 Введите остаток в КОРОБКЕ на конец смены:\n"
                "(например: 5124)"
            )
            
            return ENTER_BOX_CASH
        except ValueError:
            await update.message.reply_text("❌ Неверный формат! Введите число")
            return ENTER_SAFE_CASH
    
    async def enter_box_cash(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Ввод остатка в коробке"""
        try:
            value = float(update.message.text.strip())
            context.user_data['shift_data']['box_cash_end'] = value
            
            await update.message.reply_text(
                "🛒 Введите ТОВАРКУ (наличные):\n"
                "(например: 1000)"
            )
            
            return ENTER_GOODS_CASH
        except ValueError:
            await update.message.reply_text("❌ Неверный формат! Введите число")
            return ENTER_BOX_CASH
    
    async def enter_goods_cash(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Ввод товарки"""
        try:
            value = float(update.message.text.strip())
            context.user_data['shift_data']['goods_cash'] = value
            
            await update.message.reply_text(
                "💸 Введите КОМПЕНСАЦИИ:\n"
                "(например: 650 или 0)"
            )
            
            return ENTER_COMPENSATIONS
        except ValueError:
            await update.message.reply_text("❌ Неверный формат! Введите число")
            return ENTER_GOODS_CASH
    
    async def enter_compensations(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Ввод компенсаций"""
        try:
            value = float(update.message.text.strip())
            context.user_data['shift_data']['compensations'] = value
            
            await update.message.reply_text(
                "💰 Введите ВЫПЛАТЫ ЗП:\n"
                "(например: 3000 или 0)"
            )
            
            return ENTER_SALARY
        except ValueError:
            await update.message.reply_text("❌ Неверный формат! Введите число")
            return ENTER_COMPENSATIONS
    
    async def enter_salary(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Ввод зарплаты"""
        try:
            value = float(update.message.text.strip())
            context.user_data['shift_data']['salary_payouts'] = value
            
            await update.message.reply_text(
                "📝 Введите ПРОЧИЕ РАСХОДЫ:\n"
                "(например: 0)"
            )
            
            return ENTER_OTHER_EXPENSES
        except ValueError:
            await update.message.reply_text("❌ Неверный формат! Введите число")
            return ENTER_SALARY
    
    async def enter_other_expenses(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Ввод прочих расходов"""
        try:
            value = float(update.message.text.strip())
            context.user_data['shift_data']['other_expenses'] = value
            
            await update.message.reply_text(
                "🎮 Введите общее количество ГЕЙМПАДОВ:\n"
                "(например: 153)"
            )
            
            return ENTER_JOYSTICKS_TOTAL
        except ValueError:
            await update.message.reply_text("❌ Неверный формат! Введите число")
            return ENTER_OTHER_EXPENSES
    
    async def enter_joysticks_total(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Ввод общего количества геймпадов"""
        try:
            value = int(update.message.text.strip())
            context.user_data['shift_data']['joysticks_total'] = value
            
            await update.message.reply_text(
                "🔧 Введите количество геймпадов В РЕМОНТЕ:\n"
                "(например: 3 или 0)"
            )
            
            return ENTER_JOYSTICKS_REPAIR
        except ValueError:
            await update.message.reply_text("❌ Неверный формат! Введите целое число")
            return ENTER_JOYSTICKS_TOTAL
    
    async def enter_joysticks_repair(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Ввод геймпадов в ремонте"""
        try:
            value = int(update.message.text.strip())
            context.user_data['shift_data']['joysticks_in_repair'] = value
            
            await update.message.reply_text(
                "⚠️ Введите количество геймпадов ТРЕБУЕТСЯ В РЕМОНТ:\n"
                "(например: 3 или 0)"
            )
            
            return ENTER_JOYSTICKS_NEED
        except ValueError:
            await update.message.reply_text("❌ Неверный формат! Введите целое число")
            return ENTER_JOYSTICKS_REPAIR
    
    async def enter_joysticks_need(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Ввод геймпадов требуется в ремонт"""
        try:
            value = int(update.message.text.strip())
            context.user_data['shift_data']['joysticks_need_repair'] = value
            
            await update.message.reply_text(
                "🎯 Введите количество ИГР:\n"
                "(например: 31)"
            )
            
            return ENTER_GAMES
        except ValueError:
            await update.message.reply_text("❌ Неверный формат! Введите целое число")
            return ENTER_JOYSTICKS_NEED
    
    async def enter_games(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Ввод количества игр"""
        try:
            value = int(update.message.text.strip())
            context.user_data['shift_data']['games_count'] = value
            
            # Туалетная бумага
            keyboard = [
                [InlineKeyboardButton("✅ Есть", callback_data="finmon_toilet_yes")],
                [InlineKeyboardButton("❌ Нет", callback_data="finmon_toilet_no")]
            ]
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(
                "🧻 Туалетная бумага в наличии?",
                reply_markup=reply_markup
            )
            
            return SELECT_TOILET_PAPER
        except ValueError:
            await update.message.reply_text("❌ Неверный формат! Введите целое число")
            return ENTER_GAMES
    
    async def select_toilet_paper(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Выбор наличия туалетной бумаги"""
        query = update.callback_query
        await query.answer()
        
        has_toilet = query.data == "finmon_toilet_yes"
        context.user_data['shift_data']['toilet_paper'] = has_toilet
        
        # Бумажные полотенца
        keyboard = [
            [InlineKeyboardButton("✅ Есть", callback_data="finmon_towels_yes")],
            [InlineKeyboardButton("❌ Нет", callback_data="finmon_towels_no")]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            "🧻 Бумажные полотенца в наличии?",
            reply_markup=reply_markup
        )
        
        return SELECT_PAPER_TOWELS
    
    async def select_paper_towels(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Выбор наличия бумажных полотенец"""
        query = update.callback_query
        await query.answer()
        
        has_towels = query.data == "finmon_towels_yes"
        context.user_data['shift_data']['paper_towels'] = has_towels
        
        await query.edit_message_text(
            "📝 Введите ПРИМЕЧАНИЯ к смене:\n"
            "(или напишите 'нет' если примечаний нет)"
        )
        
        return ENTER_NOTES
    
    async def enter_notes(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Ввод примечаний"""
        notes = update.message.text.strip()
        if notes.lower() in ['нет', 'no', '-', '']:
            notes = None
        
        context.user_data['shift_data']['notes'] = notes
        
        # Показать сводку для подтверждения
        shift_data = context.user_data['shift_data']
        summary = self._format_shift_summary(shift_data)
        
        keyboard = [
            [InlineKeyboardButton("✅ Подтвердить и сохранить", callback_data="finmon_confirm")],
            [InlineKeyboardButton("❌ Отменить", callback_data="finmon_cancel")]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            summary,
            reply_markup=reply_markup
        )
        
        return CONFIRM_SHIFT
    
    async def confirm_shift(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Подтверждение и сохранение смены"""
        query = update.callback_query
        await query.answer()
        
        shift_data = context.user_data['shift_data']
        user = update.effective_user
        
        # Создать объект Shift
        shift = Shift(
            club_id=shift_data['club_id'],
            shift_date=shift_data['shift_date'],
            shift_time=shift_data['shift_time'],
            admin_tg_id=user.id,
            admin_username=user.username or user.first_name,
            fact_cash=shift_data.get('fact_cash', 0),
            fact_card=shift_data.get('fact_card', 0),
            qr=shift_data.get('qr', 0),
            card2=shift_data.get('card2', 0),
            safe_cash_end=shift_data.get('safe_cash_end', 0),
            box_cash_end=shift_data.get('box_cash_end', 0),
            goods_cash=shift_data.get('goods_cash', 0),
            compensations=shift_data.get('compensations', 0),
            salary_payouts=shift_data.get('salary_payouts', 0),
            other_expenses=shift_data.get('other_expenses', 0),
            joysticks_total=shift_data.get('joysticks_total', 0),
            joysticks_in_repair=shift_data.get('joysticks_in_repair', 0),
            joysticks_need_repair=shift_data.get('joysticks_need_repair', 0),
            games_count=shift_data.get('games_count', 0),
            toilet_paper=shift_data.get('toilet_paper', False),
            paper_towels=shift_data.get('paper_towels', False),
            notes=shift_data.get('notes')
        )
        
        # Сохранить в базу
        shift_id = self.db.save_shift(shift)
        
        if shift_id:
            # Обновить балансы касс
            # TODO: Implement cash balance logic based on business rules
            
            # Синхронизация с Google Sheets
            club_name = self.db.get_club_display_name(shift_data['club_id'])
            self.sheets.append_shift(shift_data, club_name)
            
            await query.edit_message_text(
                f"✅ Смена сдана успешно!\n\n"
                f"ID: {shift_id}\n"
                f"Клуб: {club_name}\n"
                f"Дата: {shift_data['shift_date']}\n\n"
                f"Данные сохранены в базу и синхронизированы с Google Sheets."
            )
        else:
            await query.edit_message_text(
                "❌ Ошибка при сохранении смены. Попробуйте позже."
            )
        
        # Очистить данные
        context.user_data.clear()
        
        return ConversationHandler.END
    
    async def cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Отмена wizard"""
        query = update.callback_query
        if query:
            await query.answer()
            await query.edit_message_text("❌ Сдача смены отменена")
        else:
            await update.message.reply_text("❌ Сдача смены отменена")
        
        context.user_data.clear()
        return ConversationHandler.END
    
    def _format_shift_summary(self, shift_data: dict) -> str:
        """Форматирование сводки смены"""
        club_name = self.db.get_club_display_name(shift_data['club_id'])
        time_label = "Утро" if shift_data['shift_time'] == 'morning' else "Вечер"
        date_str = shift_data['shift_date'].strftime('%d.%m')
        
        toilet = "есть" if shift_data.get('toilet_paper') else "нет"
        towels = "есть" if shift_data.get('paper_towels') else "нет"
        
        summary = f"[{club_name}] {time_label} {date_str}\n"
        summary += "━━━━━━━━━━━━━━━━━━━━\n"
        summary += f"Факт нал: {shift_data.get('fact_cash', 0):,.0f} ₽ | Сейф: {shift_data.get('safe_cash_end', 0):,.0f} ₽\n"
        summary += f"Факт безнал: {shift_data.get('fact_card', 0):,.0f} ₽ | QR: {shift_data.get('qr', 0):,.0f} ₽ | Новая касса: {shift_data.get('card2', 0):,.0f} ₽\n"
        summary += f"Товарка (нал): {shift_data.get('goods_cash', 0):,.0f} ₽ | Коробка (нал): {shift_data.get('box_cash_end', 0):,.0f} ₽\n"
        summary += f"Комп/зп/прочие: -{shift_data.get('compensations', 0):,.0f} / {shift_data.get('salary_payouts', 0):,.0f} / {shift_data.get('other_expenses', 0):,.0f} ₽\n\n"
        summary += f"Геймпады: {shift_data.get('joysticks_total', 0)} (ремонт: {shift_data.get('joysticks_in_repair', 0)}, требуется: {shift_data.get('joysticks_need_repair', 0)})\n"
        summary += f"Игр: {shift_data.get('games_count', 0)}\n\n"
        summary += f"Туалетка: {toilet} | Полотенца: {towels}\n"
        
        if shift_data.get('notes'):
            summary += f"\nПримечание: {shift_data['notes']}\n"
        
        return summary
    
    async def cmd_balances(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показать текущие балансы - /balances"""
        balances = self.db.get_balances()
        
        if not balances:
            await update.message.reply_text("❌ Нет данных о балансах")
            return
        
        text = "💰 ТЕКУЩИЕ БАЛАНСЫ КАСС\n\n"
        
        current_club = None
        for balance in balances:
            if current_club != balance['club_name']:
                current_club = balance['club_name']
                text += f"\n🏢 {current_club}\n"
            
            cash_type_label = "Официальная" if balance['cash_type'] == 'official' else "Коробка"
            text += f"  {cash_type_label}: {balance['balance']:,.2f} ₽\n"
        
        await update.message.reply_text(text)
    
    async def cmd_shifts(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показать последние смены - /shifts"""
        user_id = update.effective_user.id
        
        # Владельцы видят все смены, админы - только свои
        shifts = self.db.get_shifts(
            limit=10,
            admin_id=user_id,
            owner_ids=self.owner_ids
        )
        
        if not shifts:
            await update.message.reply_text("❌ Нет сданных смен")
            return
        
        text = "📊 ПОСЛЕДНИЕ СМЕНЫ\n\n"
        
        for shift in shifts:
            club_name = self.db.get_club_display_name(shift['club_id'])
            time_label = "Утро" if shift['shift_time'] == 'morning' else "Вечер"
            date_str = datetime.fromisoformat(str(shift['shift_date'])).strftime('%d.%m.%Y')
            
            text += f"[{club_name}] {time_label} {date_str}\n"
            text += f"  Админ: @{shift.get('admin_username', 'Unknown')}\n"
            text += f"  Выручка: {shift['fact_cash']:,.0f} ₽ (нал) + {shift['fact_card']:,.0f} ₽ (б/н)\n"
            text += "━━━━━━━━━━━━━━━━\n"
        
        await update.message.reply_text(text)
