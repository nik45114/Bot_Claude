#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FinMon Shift Wizard - Button-based shift submission
Handles /shift command with step-by-step wizard
"""

import logging
import json
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
from telegram.error import BadRequest

# Try to import analytics module
try:
    from modules.finmon_analytics import FinMonAnalytics
    ANALYTICS_AVAILABLE = True
except ImportError:
    ANALYTICS_AVAILABLE = False
    FinMonAnalytics = None

logger = logging.getLogger(__name__)

# Conversation states for CLOSING shift
(SELECT_CLUB, CONFIRM_IDENTITY, SELECT_ADMIN_FOR_SHIFT, ENTER_FACT_CASH, ENTER_FACT_CARD,
 ENTER_QR, ENTER_CARD2, ENTER_SAFE, ENTER_ACTUAL_CASH, ENTER_BOX, ENTER_TOVARKA, ENTER_GAMEPADS, ENTER_REPAIR,
 ENTER_NEED_REPAIR, ENTER_GAMES,
 UPLOAD_Z_CASH, UPLOAD_Z_CARD, UPLOAD_Z_QR, UPLOAD_Z_CARD2,
 CONFIRM_SHIFT) = range(20)

# Conversation states for EXPENSE tracking (separate conversation)
(EXPENSE_SELECT_CASH_SOURCE, EXPENSE_ENTER_AMOUNT, EXPENSE_ENTER_REASON, EXPENSE_CONFIRM) = range(14, 18)

# Conversation states for CASH WITHDRAWAL (separate conversation)
(WITHDRAWAL_SELECT_CASH_SOURCE, WITHDRAWAL_ENTER_AMOUNT, WITHDRAWAL_CONFIRM) = range(18, 21)

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


def get_shift_type_for_opening() -> tuple[str, date]:
    """
    Auto-detect which shift type to open based on current MSK time
    Можно открывать смену за 1 час до начала

    Returns:
        Tuple[shift_type, shift_date]:
            - shift_type: 'morning' or 'evening'
            - shift_date: date object для этой смены
    """
    now = now_msk()
    current_hour = now.hour
    current_date = now.date()

    # 10:00-22:00 = morning shift (дневная смена, открывается утром, закроется вечером)
    # 22:00-10:00 = evening shift (ночная смена, открывается вечером, закроется утром следующего дня)

    # Утреннее окно (10:00-22:00) - дневная смена
    if 10 <= current_hour < 22:
        return 'morning', current_date

    # Вечернее окно (22:00-23:59) - ночная смена с сегодняшней датой
    elif current_hour >= 22:
        return 'evening', current_date

    # Утреннее окно (00:00-10:00) - ночная смена ВЧЕРАШНЕГО дня!
    # Если сейчас 9:00 01.11, то это смена 31.10→01.11
    else:  # 0 <= current_hour < 10
        yesterday = current_date - timedelta(days=1)
        return 'evening', yesterday


class ShiftWizard:
    """Wizard for button-based shift submission"""
    
    def __init__(self, finmon_simple, schedule, shift_manager=None, schedule_parser=None, owner_ids: list = None, bot_instance=None, admin_db=None, db_path=None, openai_key=None, controller_id=None):
        """
        Initialize wizard

        Args:
            finmon_simple: FinMonSimple instance
            schedule: FinMonSchedule instance
            shift_manager: ShiftManager instance (optional)
            schedule_parser: ScheduleParser instance (optional)
            owner_ids: List of owner telegram IDs
            bot_instance: ClubAssistantBot instance (for dynamic keyboard updates)
            admin_db: AdminDB instance (for admin list)
            db_path: Path to database
            openai_key: OpenAI API key
            controller_id: Controller Telegram ID
        """
        self.finmon = finmon_simple
        self.schedule = schedule
        self.shift_manager = shift_manager
        self.schedule_parser = schedule_parser
        self.owner_ids = owner_ids or []
        self.bot_instance = bot_instance
        self.admin_db = admin_db
        self.controller_id = controller_id
        self.admin_manager = admin_db  # Alias для совместимости

        # Initialize improvements module
        if db_path and openai_key and controller_id:
            from modules.finmon_shift_improvements import FinMonShiftImprovements
            self.improvements = FinMonShiftImprovements(db_path, openai_key, controller_id)
        else:
            self.improvements = None
            logger.warning("⚠️ FinMonShiftImprovements not initialized - missing parameters")
    
    def is_owner(self, user_id: int) -> bool:
        """Check if user is owner"""
        return user_id in self.owner_ids
    
    async def start_close_shift(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start close shift from inline button callback"""
        query = update.callback_query
        if query:
            await query.answer()
            # Create a fake update with message for cmd_shift
            fake_update = Update(
                update_id=update.update_id,
                message=query.message
            )
            fake_update._effective_user = update.effective_user
            fake_update._effective_chat = update.effective_chat
            return await self.cmd_shift(fake_update, context)
        else:
            return await self.cmd_shift(update, context)

    async def cmd_shift(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start shift submission process (CLOSE shift)"""
        user_id = update.effective_user.id

        # Check if shift manager is available
        if not self.shift_manager:
            await update.message.reply_text("❌ Модуль управления сменами недоступен")
            return ConversationHandler.END

        # Check for active shift
        active_shift = self.shift_manager.get_active_shift(user_id)
        
        if not active_shift:
            await update.message.reply_text(
                "❌ У вас нет открытой смены\n\n"
                "Сначала откройте смену через кнопку:\n"
                "🔓 Открыть смену"
            )
            return ConversationHandler.END
        
        # Get shift data
        club = active_shift['club']
        shift_type = active_shift['shift_type']
        shift_id = active_shift['id']

        # Get previous shift cash остаток
        previous_cash = None
        if self.improvements:
            previous_cash = self.improvements.get_previous_shift_cash(club, shift_type)

        # Get previous shift balances separately for safe and box
        prev_safe, prev_box = (0, 0)
        if self.improvements:
            prev_safe, prev_box = self.improvements.get_previous_shift_balances(club, shift_type)

        # Get previous shift revenue
        previous_revenue = None
        if self.finmon:
            previous_revenue = self.finmon.get_previous_shift_revenue(club, shift_type)

        # Initialize shift data in context
        context.user_data['shift_data'] = {
            'admin_id': user_id,
            'club': club,
            'shift_type': shift_type,
            'active_shift_id': shift_id,
            'fact_cash': 0.0,
            'fact_card': 0.0,
            'qr': 0.0,
            'card2': 0.0,
            'safe_cash_start': previous_cash or 0.0,
            'safe_cash_end': 0.0,
            'box_cash_start': prev_box or 0.0,
            'box_cash_end': 0.0,
            'tovarka': 0.0,
            'gamepads': 0,
            'repair': 0,
            'need_repair': 0,
            'games': 0,
            'cash_disabled': False,
            'card_disabled': False,
            'qr_disabled': False,
            'card2_disabled': False,
        }

        context.user_data['shift_club'] = club
        context.user_data['shift_time'] = shift_type
        context.user_data['active_shift_id'] = shift_id
        context.user_data['previous_revenue'] = previous_revenue
        context.user_data['prev_official'] = prev_safe
        context.user_data['prev_box'] = prev_box

        # Get expenses from this shift
        expenses = self.shift_manager.get_shift_expenses(shift_id)
        context.user_data['shift_expenses'] = expenses
        context.user_data['shift_data']['expenses'] = expenses

        # Start from cash input
        shift_label = "☀️ Утро (дневная смена)" if shift_type == "morning" else "🌙 Вечер (ночная смена)"

        msg = f"📋 Закрытие смены\n\n"
        msg += f"🏢 Клуб: {club}\n"
        msg += f"⏰ {shift_label}\n\n"

        if previous_cash is not None:
            msg += f"📊 Остаток предыдущей смены: {previous_cash:,.0f} ₽\n\n"

        if expenses:
            expenses_total = sum(exp['amount'] for exp in expenses)
            msg += f"💸 Списаний в смене: {expenses_total:,.0f} ₽\n\n"

        msg += "💰 Введите наличку факт:\n\nПример: 3440"

        # Add inline buttons
        keyboard = [
            [InlineKeyboardButton("Без изменений (0)", callback_data="cash_no_change")],
            [InlineKeyboardButton("❌ Касса не работала", callback_data="cash_disabled")],
            [InlineKeyboardButton("🚫 Отмена", callback_data="shift_cancel")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(msg, reply_markup=reply_markup)
        return ENTER_FACT_CASH
    
    # ===== Open Shift Methods =====
    
    async def cmd_open_shift(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Open a new shift"""
        user_id = update.effective_user.id

        # Определяем откуда вызов - callback или обычное сообщение
        is_callback = update.callback_query is not None

        # Check if user is a club account (only club accounts can open shifts)
        club_accounts = {
            5329834944: "Рио",   # Клуб Рио
            5992731922: "Север"  # Клуб Север
        }

        if user_id not in club_accounts:
            text = "❌ Открывать смены могут только клубные аккаунты\n\n" \
                   "Используйте аккаунт клуба для открытия смен."
            if is_callback:
                await update.callback_query.answer(text, show_alert=True)
            else:
                await update.message.reply_text(text)
            return

        # Check if shift manager is available
        if not self.shift_manager:
            text = "❌ Модуль управления сменами недоступен"
            if is_callback:
                await update.callback_query.answer(text, show_alert=True)
            else:
                await update.message.reply_text(text)
            return

        # Check if user already has an open shift
        active_shift = self.shift_manager.get_active_shift(user_id)
        if active_shift:
            text = (
                f"❌ У вас уже открыта смена\n\n"
                f"🏢 Клуб: {active_shift['club']}\n"
                f"⏰ Тип: {'☀️ Утро' if active_shift['shift_type'] == 'morning' else '🌙 Вечер'}\n\n"
                f"Сначала закройте её через:\n🔒 Закрыть смену"
            )
            if is_callback:
                await update.callback_query.answer(text, show_alert=True)
            else:
                await update.message.reply_text(text)
            return

        # Auto-detect club from chat ID
        chat_id = update.effective_chat.id
        club = self.finmon.get_club_from_chat(chat_id)

        if club:
            # Club auto-detected
            return await self._open_shift_for_club(update, context, club, is_callback=is_callback)
        else:
            # Ask user to select club
            msg = "🔓 Открытие смены\n\n⚠️ Клуб не определён автоматически\n\nВыберите клуб:"
            
            keyboard = [
                [InlineKeyboardButton("🏢 Рио", callback_data="open_rio")],
                [InlineKeyboardButton("🏢 Север", callback_data="open_sever")],
                [InlineKeyboardButton("❌ Отменить", callback_data="open_cancel")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(msg, reply_markup=reply_markup)
    
    async def handle_open_club_selection(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle club selection for opening shift"""
        query = update.callback_query
        await query.answer()
        
        if query.data == "open_cancel":
            await query.edit_message_text("❌ Открытие смены отменено")
            return
        
        if query.data == "open_rio":
            club = "Рио"
        elif query.data == "open_sever":
            club = "Север"
        else:
            await query.edit_message_text("❌ Неверный выбор")
            return
        
        return await self._open_shift_for_club(update, context, club, is_callback=True)
    
    async def _open_shift_for_club(self, update, context, club, is_callback=False):
        """Open shift for selected club"""
        user_id = update.effective_user.id if not is_callback else update.callback_query.from_user.id
        user = update.effective_user if not is_callback else update.callback_query.from_user
        
        # Auto-detect shift type and date based on time
        shift_type, shift_date = get_shift_type_for_opening()
        shift_label = "☀️ Утро (дневная смена)" if shift_type == "morning" else "🌙 Вечер (ночная смена)"
        close_time = "22:00" if shift_type == "morning" else "10:00"

        # Parse schedule from Google Sheets if available
        if self.schedule_parser:
            try:
                logger.info(f"📊 Parsing Google Sheets for {shift_date}, club={club}, shift={shift_type}")
                schedule_data = self.schedule_parser.parse_for_date(shift_date)

                # Get duty for this club and shift type
                duty_key = (club, shift_type)
                if duty_key in schedule_data:
                    parsed_duty = schedule_data[duty_key]
                    logger.info(f"✅ Found duty in Google Sheets: {parsed_duty}")

                    # Update database with fresh data from Google Sheets
                    if parsed_duty.get('admin_name'):
                        self.shift_manager.add_duty_schedule(
                            duty_date=shift_date,
                            club=club,
                            shift_type=shift_type,
                            admin_id=parsed_duty.get('admin_id'),
                            admin_name=parsed_duty['admin_name']
                        )
                        logger.info(f"💾 Updated DB with Google Sheets data")
                else:
                    logger.info(f"📋 No duty found in Google Sheets for {duty_key}")

            except Exception as e:
                logger.error(f"❌ Failed to parse Google Sheets: {e}")
                import traceback
                traceback.print_exc()
                # Continue with DB fallback

        # Check if there's an expected duty person (from DB, potentially updated from Sheets)
        duty_info = None
        if self.shift_manager:
            duty_info = self.shift_manager.get_expected_duty(club, shift_type, shift_date)
        
        # Build confirmation message
        username = f"@{user.username}" if user.username else "Без username"
        full_name = user.full_name or "Без имени"
        
        msg = f"🔓 Открытие смены\n\n"
        msg += f"🏢 Клуб: {club}\n"
        msg += f"⏰ Смена: {shift_label}\n"
        msg += f"🕐 Закрытие в: {close_time} МСК\n\n"
        msg += f"👤 Открывает:\n"
        msg += f"  • {full_name}\n"
        msg += f"  • {username}\n"
        msg += f"  • ID: {user_id}\n\n"
        
        # Show who is scheduled and ask for confirmation
        keyboard = []
        
        if duty_info and duty_info.get('admin_name'):
            expected_name = duty_info['admin_name']
            expected_id = duty_info.get('admin_id')
            
            msg += f"📋 По расписанию: {expected_name}"
            if expected_id:
                msg += f" (ID: {expected_id})"
            msg += "\n\n"
            msg += "Кто работает на смене?"
            
            # Store expected duty info
            context.user_data['expected_duty_id'] = expected_id
            context.user_data['expected_duty_name'] = expected_name
            context.user_data['shift_club'] = club
            context.user_data['shift_type'] = shift_type
            context.user_data['shift_date'] = shift_date
            
            # Two options: confirm it's the scheduled person, or select replacement
            keyboard = [
                [InlineKeyboardButton(f"✅ Да, это {expected_name}", 
                                    callback_data=f"confirm_scheduled_{club}_{shift_type}_{expected_id}")],
                [InlineKeyboardButton("🔄 Замена - выбрать другого", 
                                    callback_data=f"select_replacement_{club}_{shift_type}")],
                [InlineKeyboardButton("❌ Отменить", callback_data="open_cancel")]
            ]
        else:
            msg += f"📋 По расписанию: нет данных\n\n"
            msg += "Выберите кто работает на смене:"
            
            # No schedule data - just select admin
            context.user_data['shift_club'] = club
            context.user_data['shift_type'] = shift_type
            context.user_data['shift_date'] = shift_date
            
            keyboard = [
                [InlineKeyboardButton("👤 Выбрать администратора", 
                                    callback_data=f"select_replacement_{club}_{shift_type}")],
                [InlineKeyboardButton("❌ Отменить", callback_data="open_cancel")]
            ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)

        if is_callback:
            try:
                await update.callback_query.edit_message_text(msg, reply_markup=reply_markup)
            except BadRequest as e:
                if "message is not modified" in str(e).lower():
                    # Ignore error if message content is the same
                    logger.info("ℹ️ Message not modified (content is the same)")
                else:
                    raise
        else:
            await update.message.reply_text(msg, reply_markup=reply_markup)
    
    async def handle_confirm_scheduled(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle confirmation that scheduled person is working"""
        query = update.callback_query
        await query.answer()

        # Parse: confirm_scheduled_club_shift_type_admin_id
        parts = query.data.split('_')
        if len(parts) < 5:
            await query.edit_message_text("❌ Ошибка данных")
            return

        club = parts[2]
        shift_type = parts[3]
        admin_id = int(parts[4])
        opener_id = query.from_user.id

        shift_label = "☀️ Утро" if shift_type == "morning" else "🌙 Вечер"

        # Если админ подтверждает сам за себя - сразу открываем смену
        if opener_id == admin_id:
            # Открываем смену сразу
            shift_date = context.user_data.get('shift_date')
            shift_id = self.shift_manager.open_shift(admin_id, club, shift_type, shift_date, admin_id)

            if shift_id:
                # Save shift_id in context for checklist
                context.user_data['current_shift_id'] = shift_id

                # Добавляем кнопки НОВЫХ чек-листов приема смены
                from telegram import InlineKeyboardButton, InlineKeyboardMarkup
                keyboard = [
                    [InlineKeyboardButton("⭐️ Рейтинг уборки", callback_data="rating_start")],
                    [InlineKeyboardButton("📦 Чек-лист инвентаря", callback_data="inventory_start")]
                ]

                # Отзыв об уборщице только для ночной смены
                if shift_type == 'evening':
                    keyboard.insert(1, [InlineKeyboardButton("🧹 Отзыв об уборщице", callback_data="review_start")])

                keyboard.append([InlineKeyboardButton("« Главное меню", callback_data="main_menu")])
                reply_markup = InlineKeyboardMarkup(keyboard)

                await query.edit_message_text(
                    f"✅ Смена открыта!\n\n"
                    f"🏢 {club} | {shift_label}\n"
                    f"🆔 ID смены: {shift_id}\n\n"
                    f"📋 Обязательные чек-листы:\n"
                    f"• ⭐️ Рейтинг уборки (30 мин)\n"
                    f"• 📦 Инвентарь (4 часа)\n"
                    + (f"• 🧹 Отзыв об уборщице\n" if shift_type == 'evening' else ""),
                    reply_markup=reply_markup
                )

                # Send notification to controller
                if self.improvements:
                    admin_name = query.from_user.full_name or query.from_user.username or "Unknown"
                    shift_data = {
                        'club': club,
                        'shift_type': shift_type,
                        'admin_id': admin_id
                    }
                    # Removed controller notification for shift opening
                    # Controller will only be notified when shift is closed
            else:
                await query.edit_message_text("❌ Ошибка при открытии смены")
        else:
            # Если открывает другой человек - отправляем запрос подтверждения
            context.user_data['working_admin_id'] = admin_id
            context.user_data['opener_id'] = opener_id

            # Send confirmation request to the admin
            await self._send_confirmation_request(
                context=context,
                admin_id=admin_id,
                club=club,
                shift_type=shift_type,
                opener_id=opener_id,
                opener_name=query.from_user.full_name
            )

            # Get admin name
            admin_name = context.user_data.get('expected_duty_name', 'Админ')

            # Save message info for later update in bot_data
            if not context.bot_data.get('pending_shift_messages'):
                context.bot_data['pending_shift_messages'] = {}

            context.bot_data['pending_shift_messages'][opener_id] = {
                'chat_id': query.message.chat_id,
                'message_id': query.message.message_id,
                'club': club,
                'shift_type': shift_type
            }

            await query.edit_message_text(
                f"⏳ Ожидание подтверждения\n\n"
                f"Запрос отправлен: {admin_name}\n"
                f"Ожидайте подтверждения в Telegram..."
            )
    
    async def handle_select_replacement(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show admin list for replacement selection"""
        query = update.callback_query
        await query.answer()
        
        # Parse: select_replacement_club_shift_type
        parts = query.data.split('_')
        if len(parts) < 4:
            await query.edit_message_text("❌ Ошибка данных")
            return
        
        club = parts[2]
        shift_type = parts[3]
        
        # Get list of admins
        if not self.admin_db:
            await query.edit_message_text("❌ База админов недоступна")
            return
        
        try:
            admins = self.admin_db.get_all_admins(active_only=True)

            # Filter admins: only those with full_name (minimum 3 words: Фамилия Имя Отчество)
            # Исключаем технические аккаунты клубов и служебные аккаунты
            excluded_keywords = ['клуб', 'рио', 'север', 'главный', 'администратор', 'око', 'саурона']

            def has_full_name(admin):
                full_name = admin.get('full_name')
                if not full_name:
                    return False
                # Check if name has at least 3 words (surname, name, patronymic)
                words = full_name.strip().split()
                if len(words) < 3:
                    return False
                # Проверяем, что это не технический аккаунт
                full_name_lower = full_name.lower()
                is_technical = any(keyword in full_name_lower for keyword in excluded_keywords)
                return not is_technical

            admins = [admin for admin in admins if has_full_name(admin)]

            if not admins:
                await query.edit_message_text("❌ Нет доступных администраторов для работы на сменах\n\n"
                                             "Админы должны иметь полное ФИО (Фамилия Имя Отчество) для работы на сменах.")
                return

            msg = f"🔄 Замена\n\n"
            msg += f"🏢 Клуб: {club}\n"
            msg += f"⏰ Смена: {'☀️ Утро' if shift_type == 'morning' else '🌙 Вечер'}\n\n"
            msg += "Выберите кто работает:"

            # Build admin buttons (max 2 per row)
            keyboard = []
            for i in range(0, len(admins), 2):
                row = []
                for admin in admins[i:i+2]:
                    admin_id = admin.get('user_id')
                    admin_name = admin.get('full_name') or admin.get('username') or f"ID {admin_id}"
                    # Truncate long names
                    if len(admin_name) > 20:
                        admin_name = admin_name[:17] + "..."
                    row.append(InlineKeyboardButton(
                        admin_name,
                        callback_data=f"admin_selected_{club}_{shift_type}_{admin_id}"
                    ))
                keyboard.append(row)
            
            keyboard.append([InlineKeyboardButton("❌ Отменить", callback_data="open_cancel")])
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(msg, reply_markup=reply_markup)
            
        except Exception as e:
            logger.error(f"Failed to get admin list: {e}")
            await query.edit_message_text(f"❌ Ошибка получения списка админов: {e}")
    
    async def handle_admin_selected(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle admin selection from list"""
        query = update.callback_query
        await query.answer()
        
        # Parse: admin_selected_club_shift_type_admin_id
        parts = query.data.split('_')
        if len(parts) < 5:
            await query.edit_message_text("❌ Ошибка данных")
            return
        
        club = parts[2]
        shift_type = parts[3]
        admin_id = int(parts[4])
        opener_id = query.from_user.id
        
        # Store info for confirmation
        context.user_data['working_admin_id'] = admin_id
        context.user_data['opener_id'] = opener_id
        
        # Send confirmation request to selected admin
        await self._send_confirmation_request(
            context=context,
            admin_id=admin_id,
            club=club,
            shift_type=shift_type,
            opener_id=opener_id,
            opener_name=query.from_user.full_name
        )
        
        # Get admin name for display
        admin_name = "Админ"
        if self.admin_db:
            try:
                admin = self.admin_db.get_admin(admin_id)
                if admin:
                    admin_name = admin.get('full_name') or admin.get('username') or f"ID {admin_id}"
            except:
                pass

        # Save message info for later update in bot_data (shared across users)
        # Use opener_id as key to find this message later
        if not context.bot_data.get('pending_shift_messages'):
            context.bot_data['pending_shift_messages'] = {}

        context.bot_data['pending_shift_messages'][opener_id] = {
            'chat_id': query.message.chat_id,
            'message_id': query.message.message_id,
            'club': club,
            'shift_type': shift_type
        }

        await query.edit_message_text(
            f"⏳ Ожидание подтверждения\n\n"
            f"Запрос отправлен: {admin_name}\n"
            f"Ожидайте подтверждения в Telegram..."
        )
    
    async def _send_confirmation_request(self, context, admin_id, club, shift_type, opener_id, opener_name):
        """Send confirmation request to admin's personal Telegram"""
        msg = f"⚠️ Запрос подтверждения смены\n\n"
        msg += f"🏢 Клуб: {club}\n"
        msg += f"⏰ Смена: {'☀️ Утро' if shift_type == 'morning' else '🌙 Вечер'}\n"
        msg += f"📅 Дата: {date.today().strftime('%d.%m.%Y')}\n\n"
        msg += f"👤 Открывает с клубного аккаунта:\n"
        msg += f"   {opener_name or 'Неизвестно'}\n\n"
        msg += "Это вы работаете на смене?\n"
        msg += "Подтвердите в своем личном Telegram:"

        keyboard = [
            [InlineKeyboardButton("✅ Да, подтверждаю",
                                callback_data=f"duty_confirm_{opener_id}_{club}_{shift_type}")],
            [InlineKeyboardButton("❌ Нет, это ошибка",
                                callback_data=f"duty_reject_{opener_id}_{club}_{shift_type}")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        try:
            sent_message = await context.bot.send_message(
                chat_id=admin_id,
                text=msg,
                reply_markup=reply_markup
            )

            # Save message_id to delete later if needed (store as list since multiple admins can receive)
            if 'pending_confirmation_messages' not in context.bot_data:
                context.bot_data['pending_confirmation_messages'] = {}

            confirmation_key = f"{opener_id}_{club}_{shift_type}"
            if confirmation_key not in context.bot_data['pending_confirmation_messages']:
                context.bot_data['pending_confirmation_messages'][confirmation_key] = []

            context.bot_data['pending_confirmation_messages'][confirmation_key].append({
                'chat_id': admin_id,
                'message_id': sent_message.message_id
            })

            logger.info(f"✅ Confirmation request sent to admin {admin_id} (msg_id: {sent_message.message_id})")
        except Exception as e:
            logger.error(f"❌ Failed to send confirmation to admin {admin_id}: {e}")
    
    # ===== Close Shift Methods (Revenue Input) =====
    
    async def handle_cash_no_change(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle 'no change' button for cash"""
        query = update.callback_query
        await query.answer()

        # Use previous shift revenue if available
        previous_revenue = context.user_data.get('previous_revenue')
        if previous_revenue and previous_revenue.get('fact_cash'):
            cash_value = previous_revenue['fact_cash']
            context.user_data['shift_data']['fact_cash'] = cash_value
            msg = f"✅ Наличка факт: {cash_value:,.0f} ₽ (как в прошлой смене)\n\n"
        else:
            context.user_data['shift_data']['fact_cash'] = 0.0
            msg = f"✅ Наличка факт: 0 ₽ (без изменений)\n\n"

        msg += "💳 Введите карту факт:\n\nПример: 12345"

        keyboard = [
            [InlineKeyboardButton("Без изменений (0)", callback_data="card_no_change")],
            [InlineKeyboardButton("❌ Касса не работала", callback_data="card_disabled")],
            [InlineKeyboardButton("🚫 Отмена", callback_data="shift_cancel")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(msg, reply_markup=reply_markup)
        return ENTER_FACT_CARD

    async def handle_cash_disabled(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle 'cash register disabled' button"""
        query = update.callback_query
        await query.answer()
        context.user_data['shift_data']['fact_cash'] = 0.0
        context.user_data['shift_data']['cash_disabled'] = True

        msg = f"❌ Касса наличных не работала\n\n"
        msg += "💳 Введите карту факт:\n\nПример: 12345"

        keyboard = [
            [InlineKeyboardButton("Без изменений (0)", callback_data="card_no_change")],
            [InlineKeyboardButton("❌ Касса не работала", callback_data="card_disabled")],
            [InlineKeyboardButton("🚫 Отмена", callback_data="shift_cancel")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(msg, reply_markup=reply_markup)
        return ENTER_FACT_CARD

    async def receive_fact_cash(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Receive cash revenue"""
        try:
            value = float(update.message.text.replace(' ', '').replace(',', '.'))
            context.user_data['shift_data']['fact_cash'] = value

            msg = f"✅ Наличка факт: {value:,.0f} ₽\n\n"
            msg += "💳 Введите карту факт:\n\nПример: 12345"

            keyboard = [
                [InlineKeyboardButton("Без изменений (0)", callback_data="card_no_change")],
                [InlineKeyboardButton("❌ Касса не работала", callback_data="card_disabled")],
                [InlineKeyboardButton("🚫 Отмена", callback_data="shift_cancel")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await update.message.reply_text(msg, reply_markup=reply_markup)
            return ENTER_FACT_CARD
        except ValueError:
            await update.message.reply_text("❌ Неверный формат. Введите число:")
            return ENTER_FACT_CASH
    
    async def handle_card_no_change(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle 'no change' button for card"""
        query = update.callback_query
        await query.answer()

        # Use previous shift revenue if available
        previous_revenue = context.user_data.get('previous_revenue')
        if previous_revenue and previous_revenue.get('fact_card'):
            card_value = previous_revenue['fact_card']
            context.user_data['shift_data']['fact_card'] = card_value
            msg = f"✅ Карта факт: {card_value:,.0f} ₽ (как в прошлой смене)\n\n"
        else:
            context.user_data['shift_data']['fact_card'] = 0.0
            msg = "✅ Карта факт: 0 ₽ (без изменений)\n\n"

        msg += "📱 Введите QR:\n\nПример: 500 (или 0 если нет)"
        keyboard = [
            [InlineKeyboardButton("Без изменений (0)", callback_data="qr_no_change")],
            [InlineKeyboardButton("❌ Касса не работала", callback_data="qr_disabled")],
            [InlineKeyboardButton("🚫 Отмена", callback_data="shift_cancel")]
        ]
        await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard))
        return ENTER_QR

    async def handle_card_disabled(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle 'card register disabled' button"""
        query = update.callback_query
        await query.answer()
        context.user_data['shift_data']['fact_card'] = 0.0
        context.user_data['shift_data']['card_disabled'] = True

        msg = "❌ Касса карт не работала\n\n📱 Введите QR:\n\nПример: 500 (или 0 если нет)"
        keyboard = [
            [InlineKeyboardButton("Без изменений (0)", callback_data="qr_no_change")],
            [InlineKeyboardButton("❌ Касса не работала", callback_data="qr_disabled")],
            [InlineKeyboardButton("🚫 Отмена", callback_data="shift_cancel")]
        ]
        await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard))
        return ENTER_QR

    async def receive_fact_card(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Receive card revenue"""
        try:
            value = float(update.message.text.replace(' ', '').replace(',', '.'))
            context.user_data['shift_data']['fact_card'] = value

            msg = f"✅ Карта факт: {value:,.0f} ₽\n\n"
            msg += "📱 Введите QR:\n\nПример: 500 (или 0 если нет)"

            keyboard = [
                [InlineKeyboardButton("Без изменений (0)", callback_data="qr_no_change")],
                [InlineKeyboardButton("❌ Касса не работала", callback_data="qr_disabled")],
                [InlineKeyboardButton("🚫 Отмена", callback_data="shift_cancel")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await update.message.reply_text(msg, reply_markup=reply_markup)
            return ENTER_QR
        except ValueError:
            await update.message.reply_text("❌ Неверный формат. Введите число:")
            return ENTER_FACT_CARD
    
    async def handle_qr_no_change(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle 'no change' button for QR"""
        query = update.callback_query
        await query.answer()

        # Use previous shift revenue if available
        previous_revenue = context.user_data.get('previous_revenue')
        if previous_revenue and previous_revenue.get('qr'):
            qr_value = previous_revenue['qr']
            context.user_data['shift_data']['qr'] = qr_value
            msg = f"✅ QR: {qr_value:,.0f} ₽ (как в прошлой смене)\n\n"
        else:
            context.user_data['shift_data']['qr'] = 0.0
            msg = "✅ QR: 0 ₽ (без изменений)\n\n"

        msg += "💳 Введите безнал/карту (касса 2):\n\nПример: 1000 (или 0 если нет)"
        keyboard = [
            [InlineKeyboardButton("Без изменений (0)", callback_data="card2_no_change")],
            [InlineKeyboardButton("❌ Касса не работала", callback_data="card2_disabled")],
            [InlineKeyboardButton("🚫 Отмена", callback_data="shift_cancel")]
        ]
        await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard))
        return ENTER_CARD2

    async def handle_qr_disabled(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle 'QR disabled' button"""
        query = update.callback_query
        await query.answer()
        context.user_data['shift_data']['qr'] = 0.0
        context.user_data['shift_data']['qr_disabled'] = True

        msg = "❌ QR не работал\n\n💳 Введите безнал/карту (касса 2):\n\nПример: 1000 (или 0 если нет)"
        keyboard = [
            [InlineKeyboardButton("Без изменений (0)", callback_data="card2_no_change")],
            [InlineKeyboardButton("❌ Касса не работала", callback_data="card2_disabled")],
            [InlineKeyboardButton("🚫 Отмена", callback_data="shift_cancel")]
        ]
        await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard))
        return ENTER_CARD2

    async def receive_qr(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Receive QR revenue"""
        try:
            value = float(update.message.text.replace(' ', '').replace(',', '.'))
            context.user_data['shift_data']['qr'] = value

            msg = f"✅ QR: {value:,.0f} ₽\n\n"
            msg += "💳 Введите безнал/карту (касса 2):\n\nПример: 1000 (или 0 если нет)"

            keyboard = [
                [InlineKeyboardButton("Без изменений (0)", callback_data="card2_no_change")],
                [InlineKeyboardButton("❌ Касса не работала", callback_data="card2_disabled")],
                [InlineKeyboardButton("🚫 Отмена", callback_data="shift_cancel")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await update.message.reply_text(msg, reply_markup=reply_markup)
            return ENTER_CARD2
        except ValueError:
            await update.message.reply_text("❌ Неверный формат. Введите число:")
            return ENTER_QR
    
    async def handle_card2_no_change(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle 'no change' button for card2"""
        query = update.callback_query
        await query.answer()

        # Use previous shift revenue if available
        previous_revenue = context.user_data.get('previous_revenue')
        if previous_revenue and previous_revenue.get('card2'):
            card2_value = previous_revenue['card2']
            context.user_data['shift_data']['card2'] = card2_value
            msg = f"✅ Безнал вторая касса: {card2_value:,.0f} ₽ (как в прошлой смене)\n\n"
        else:
            context.user_data['shift_data']['card2'] = 0.0
            msg = "✅ Безнал вторая касса: 0 ₽ (без изменений)\n\n"

        # Move to z-report upload
        msg += "📸 Загрузите сверку итогов (касса 1)\n\n"
        msg += "Отправьте фото чека или нажмите 'Пропустить' если нет чека"

        keyboard = [
            [InlineKeyboardButton("⏭️ Пропустить", callback_data="skip_z_cash")],
            [InlineKeyboardButton("🚫 Отмена", callback_data="shift_cancel")]
        ]
        await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard))
        return UPLOAD_Z_CASH

    async def handle_card2_disabled(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle 'card2 disabled' button"""
        query = update.callback_query
        await query.answer()
        context.user_data['shift_data']['card2'] = 0.0
        context.user_data['shift_data']['card2_disabled'] = True

        # Move to z-report upload
        msg = "❌ Безнал вторая касса не работала\n\n"
        msg += "📸 Загрузите сверку итогов (касса 1)\n\n"
        msg += "Отправьте фото чека или нажмите 'Пропустить' если нет чека"

        keyboard = [
            [InlineKeyboardButton("⏭️ Пропустить", callback_data="skip_z_cash")],
            [InlineKeyboardButton("🚫 Отмена", callback_data="shift_cancel")]
        ]
        await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard))
        return UPLOAD_Z_CASH

    async def receive_card2(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Receive card2 (box) revenue"""
        try:
            value = float(update.message.text.replace(' ', '').replace(',', '.'))
            context.user_data['shift_data']['card2'] = value

            # Move to z-report upload
            msg = f"✅ Безнал вторая касса: {value:,.0f} ₽\n\n"
            msg += "📸 Загрузите сверку итогов (касса 1)\n\n"
            msg += "Отправьте фото чека или нажмите 'Пропустить' если нет чека"

            keyboard = [
                [InlineKeyboardButton("⏭️ Пропустить", callback_data="skip_z_cash")],
                [InlineKeyboardButton("🚫 Отмена", callback_data="shift_cancel")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await update.message.reply_text(msg, reply_markup=reply_markup)
            return UPLOAD_Z_CASH
        except ValueError:
            await update.message.reply_text("❌ Неверный формат. Введите число:")
            return ENTER_CARD2
    
    # ===== Z-Report Upload Methods =====

    async def handle_skip_z_cash(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Skip z-report for cash"""
        query = update.callback_query
        await query.answer()

        msg = "⏭️ Итоговый отчет пропущен\n\n"
        msg += "📸 Загрузите СВЕРКУ ИТОГОВ\n\n"
        msg += "Отправьте фото чека или нажмите 'Пропустить'"

        keyboard = [
            [InlineKeyboardButton("⏭️ Пропустить", callback_data="skip_z_card")],
            [InlineKeyboardButton("🚫 Отмена", callback_data="shift_cancel")]
        ]
        await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard))
        return UPLOAD_Z_CARD

    async def upload_z_cash(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle z-report photo upload for cash register"""
        if not update.message.photo:
            await update.message.reply_text("❌ Пожалуйста, отправьте фото")
            return UPLOAD_Z_CASH

        # Get the largest photo
        photo = update.message.photo[-1]
        context.user_data['shift_data']['z_cash_photo'] = photo.file_id

        # Process OCR if improvements module available
        ocr_result = None
        if self.improvements:
            await update.message.reply_text("⏳ Обрабатываю чек через OCR...")
            ocr_result = await self.improvements.process_z_report_ocr(photo, context.bot)
            if ocr_result:
                context.user_data['shift_data']['z_cash_ocr'] = json.dumps(ocr_result, ensure_ascii=False)
                logger.info(f"✅ OCR для наличных: {ocr_result}")

        msg = "✅ Итоговый отчет загружен\n\n"
        if ocr_result and 'total' in ocr_result:
            msg += f"📊 Распознано: {ocr_result.get('total', 'N/A')} ₽\n\n"

        msg += "📸 Загрузите СВЕРКУ ИТОГОВ\n\n"
        msg += "Отправьте фото чека или нажмите 'Пропустить'"

        keyboard = [
            [InlineKeyboardButton("⏭️ Пропустить", callback_data="skip_z_card")],
            [InlineKeyboardButton("🚫 Отмена", callback_data="shift_cancel")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(msg, reply_markup=reply_markup)
        return UPLOAD_Z_CARD

    async def handle_skip_z_card(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Skip z-report for card and go to safe"""
        query = update.callback_query
        await query.answer()
        # Пропускаем QR и карту 2, сразу к сейфу
        return await self._continue_to_safe(query, context)

    async def upload_z_card(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle z-report photo upload for card register"""
        if not update.message.photo:
            await update.message.reply_text("❌ Пожалуйста, отправьте фото")
            return UPLOAD_Z_CARD

        photo = update.message.photo[-1]
        context.user_data['shift_data']['z_card_photo'] = photo.file_id

        ocr_result = None
        if self.improvements:
            await update.message.reply_text("⏳ Обрабатываю чек через OCR...")
            ocr_result = await self.improvements.process_z_report_ocr(photo, context.bot)
            if ocr_result:
                context.user_data['shift_data']['z_card_ocr'] = json.dumps(ocr_result, ensure_ascii=False)
                logger.info(f"✅ OCR для карты: {ocr_result}")

        msg = "✅ X-отчет карты загружен\n\n"
        if ocr_result and 'total' in ocr_result:
            msg += f"📊 Распознано: {ocr_result.get('total', 'N/A')} ₽\n\n"

        await update.message.reply_text(msg)

        # Пропускаем QR и карту 2, сразу к сейфу
        # Передаём message напрямую - у него есть reply_text
        return await self._continue_to_safe(update.message, context)

    async def handle_skip_z_qr(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Skip z-report for QR"""
        query = update.callback_query
        await query.answer()

        msg = "⏭️ X-отчет QR пропущен\n\n"
        msg += "📸 Загрузите X-отчет (касса 2)\n\n"
        msg += "Отправьте фото чека или нажмите 'Пропустить'"

        keyboard = [
            [InlineKeyboardButton("⏭️ Пропустить", callback_data="skip_z_card2")],
            [InlineKeyboardButton("🚫 Отмена", callback_data="shift_cancel")]
        ]
        await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard))
        return UPLOAD_Z_CARD2

    async def upload_z_qr(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle z-report photo upload for QR"""
        if not update.message.photo:
            await update.message.reply_text("❌ Пожалуйста, отправьте фото")
            return UPLOAD_Z_QR

        photo = update.message.photo[-1]
        context.user_data['shift_data']['z_qr_photo'] = photo.file_id

        ocr_result = None
        if self.improvements:
            await update.message.reply_text("⏳ Обрабатываю чек через OCR...")
            ocr_result = await self.improvements.process_z_report_ocr(photo, context.bot)
            if ocr_result:
                context.user_data['shift_data']['z_qr_ocr'] = json.dumps(ocr_result, ensure_ascii=False)
                logger.info(f"✅ OCR для QR: {ocr_result}")

        msg = "✅ X-отчет QR загружен\n\n"
        if ocr_result and 'total' in ocr_result:
            msg += f"📊 Распознано: {ocr_result.get('total', 'N/A')} ₽\n\n"

        msg += "📸 Загрузите X-отчет (касса 2)\n\n"
        msg += "Отправьте фото чека или нажмите 'Пропустить'"

        keyboard = [
            [InlineKeyboardButton("⏭️ Пропустить", callback_data="skip_z_card2")],
            [InlineKeyboardButton("🚫 Отмена", callback_data="shift_cancel")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(msg, reply_markup=reply_markup)
        return UPLOAD_Z_CARD2

    async def handle_skip_z_card2(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Skip z-report for card2 and continue to safe input"""
        query = update.callback_query
        await query.answer()
        return await self._continue_to_safe(query, context)

    async def upload_z_card2(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle z-report photo upload for card2"""
        if not update.message.photo:
            await update.message.reply_text("❌ Пожалуйста, отправьте фото")
            return UPLOAD_Z_CARD2

        photo = update.message.photo[-1]
        context.user_data['shift_data']['z_card2_photo'] = photo.file_id

        ocr_result = None
        if self.improvements:
            await update.message.reply_text("⏳ Обрабатываю чек через OCR...")
            ocr_result = await self.improvements.process_z_report_ocr(photo, context.bot)
            if ocr_result:
                context.user_data['shift_data']['z_card2_ocr'] = json.dumps(ocr_result, ensure_ascii=False)
                logger.info(f"✅ OCR для карты 2: {ocr_result}")

        msg = "✅ X-отчет карты 2 загружен\n\n"
        if ocr_result and 'total' in ocr_result:
            msg += f"📊 Распознано: {ocr_result.get('total', 'N/A')} ₽\n\n"

        await update.message.reply_text(msg)

        # Continue to safe input
        return await self._continue_to_safe(update.message, context)

    # ===== Safe and Box Input =====

    async def _continue_to_safe(self, message_or_query, context: ContextTypes.DEFAULT_TYPE):
        """Continue to safe input"""
        prev_official = context.user_data.get('prev_official', 0)
        
        msg = f"✅ Выручка введена\n\n"
        msg += "🔐 Введите общее количество наличных (касса 1):\n\n"
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

        return await self._continue_to_actual_cash(query, context)
    
    async def receive_safe(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Receive safe balance"""
        try:
            value = float(update.message.text.replace(' ', '').replace(',', '.'))
            context.user_data['shift_data']['safe_cash_end'] = value

            return await self._continue_to_actual_cash(update.message, context)
        except ValueError:
            await update.message.reply_text("❌ Неверный формат. Введите число:")
            return ENTER_SAFE

    async def _continue_to_actual_cash(self, message_or_query, context: ContextTypes.DEFAULT_TYPE):
        """Continue to actual cash verification"""
        try:
            prev_official = context.user_data.get('prev_official', 0)
            cash_revenue = context.user_data['shift_data'].get('fact_cash', 0)
            safe_cash_end = context.user_data['shift_data'].get('safe_cash_end', 0)

            # Get expenses
            expenses = context.user_data.get('expenses', [])
            total_expenses = sum(exp['amount'] for exp in expenses if exp.get('cash_source') == 'main')

            # Expected = what's in the safe (already counted and put there)
            expected_cash = safe_cash_end

            # What it should be based on calculation
            calculated_cash = prev_official + cash_revenue - total_expenses

            msg = f"💵 Проверим фактические наличные\n\n"
            msg += f"📊 Должно быть: {calculated_cash:,.0f} ₽\n"
            msg += f"(Было {prev_official:,.0f} + выручка {cash_revenue:,.0f}"
            if total_expenses > 0:
                msg += f" - расходы {total_expenses:,.0f}"
            msg += f")\n\n"
            msg += f"🔐 В сейфе (касса 1): {safe_cash_end:,.0f} ₽\n\n"
            msg += f"💰 Посчитайте и введите фактическую сумму наличных на руках:"

            keyboard = [
                [InlineKeyboardButton("✅ Совпадает", callback_data="actual_cash_matches")],
                [InlineKeyboardButton("❌ Отменить", callback_data="shift_cancel")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            # Store expected cash for comparison
            context.user_data['expected_cash'] = expected_cash

            if hasattr(message_or_query, 'reply_text'):
                await message_or_query.reply_text(msg, reply_markup=reply_markup)
            else:
                await message_or_query.edit_message_text(msg, reply_markup=reply_markup)

            return ENTER_ACTUAL_CASH
        except Exception as e:
            logger.error(f"❌ Error in _continue_to_actual_cash: {e}")
            # Skip cash verification on error, go directly to box
            return await self._continue_to_box(message_or_query, context)

    async def handle_actual_cash_matches(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle 'actual cash matches' button"""
        query = update.callback_query
        await query.answer()

        # Actual cash matches expected, so store expected value
        expected_cash = context.user_data.get('expected_cash', 0)
        context.user_data['shift_data']['actual_cash'] = expected_cash
        context.user_data['cash_verified'] = True

        msg = f"✅ Наличные совпадают: {expected_cash:,.0f} ₽\n\n"
        await query.edit_message_text(msg)

        return await self._continue_to_box(query, context)

    async def receive_actual_cash(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Receive actual cash amount and verify against expected"""
        try:
            actual_cash = float(update.message.text.replace(' ', '').replace(',', '.'))
            expected_cash = context.user_data.get('expected_cash', 0)

            context.user_data['shift_data']['actual_cash'] = actual_cash

            discrepancy = actual_cash - expected_cash

            if abs(discrepancy) < 1:  # Allow 1 ruble tolerance
                # Cash matches!
                context.user_data['cash_verified'] = True
                msg = f"✅ Отлично! Наличные совпадают: {actual_cash:,.0f} ₽\n"
                await update.message.reply_text(msg)
            elif discrepancy > 0:
                # More cash than expected - SURPLUS
                context.user_data['cash_verified'] = False
                context.user_data['cash_discrepancy'] = discrepancy
                context.user_data['cash_discrepancy_type'] = 'surplus'

                msg = f"⚠️ ВНИМАНИЕ! Излишек наличных!\n\n"
                msg += f"💰 Ожидалось: {expected_cash:,.0f} ₽\n"
                msg += f"💵 Фактически: {actual_cash:,.0f} ₽\n"
                msg += f"📈 Излишек: +{discrepancy:,.0f} ₽\n\n"
                msg += f"ℹ️ Информация отправлена контроллеру.\n"
                msg += f"Продолжайте закрытие смены."
                await update.message.reply_text(msg)

                # Notify controller about surplus
                await self._notify_controller_cash_discrepancy(update, context, 'surplus', discrepancy, expected_cash, actual_cash)
            else:
                # Less cash than expected - SHORTAGE
                context.user_data['cash_verified'] = False
                context.user_data['cash_discrepancy'] = abs(discrepancy)
                context.user_data['cash_discrepancy_type'] = 'shortage'

                msg = f"❌ ВНИМАНИЕ! Недостача наличных!\n\n"
                msg += f"💰 Ожидалось: {expected_cash:,.0f} ₽\n"
                msg += f"💵 Фактически: {actual_cash:,.0f} ₽\n"
                msg += f"📉 Недостача: {discrepancy:,.0f} ₽\n\n"
                msg += f"ℹ️ Информация отправлена контроллеру.\n"
                msg += f"Продолжайте закрытие смены."
                await update.message.reply_text(msg)

                # Notify controller about shortage
                await self._notify_controller_cash_discrepancy(update, context, 'shortage', abs(discrepancy), expected_cash, actual_cash)

            return await self._continue_to_box(update.message, context)
        except ValueError:
            await update.message.reply_text("❌ Неверный формат. Введите число:")
            return ENTER_ACTUAL_CASH

    async def _notify_controller_cash_discrepancy(self, update: Update, context: ContextTypes.DEFAULT_TYPE,
                                                   discrepancy_type: str, discrepancy: float,
                                                   expected: float, actual: float):
        """Send notification to controller about cash discrepancy"""
        if not self.controller_id:
            return

        try:
            user = update.effective_user
            admin_name = user.full_name or user.username or f"ID {user.id}"
            club = context.user_data.get('shift_club', 'N/A')
            shift_time = context.user_data.get('shift_time', 'N/A')
            shift_label = "☀️ Утро" if shift_time == "morning" else "🌙 Вечер"

            if discrepancy_type == 'surplus':
                icon = "⚠️"
                title = "ИЗЛИШЕК НАЛИЧНЫХ"
                diff_text = f"📈 Излишек: +{discrepancy:,.0f} ₽"
            else:
                icon = "❌"
                title = "НЕДОСТАЧА НАЛИЧНЫХ"
                diff_text = f"📉 Недостача: -{discrepancy:,.0f} ₽"

            notification = (
                f"{icon} {title}\n\n"
                f"👤 Администратор: {admin_name}\n"
                f"🏢 Клуб: {club}\n"
                f"⏰ Смена: {shift_label}\n\n"
                f"💰 Ожидалось: {expected:,.0f} ₽\n"
                f"💵 Фактически: {actual:,.0f} ₽\n"
                f"{diff_text}\n\n"
                f"⚠️ Требуется проверка!"
            )

            await context.bot.send_message(
                chat_id=self.controller_id,
                text=notification
            )
            logger.info(f"📨 Sent cash discrepancy notification to controller: {discrepancy_type} {discrepancy:,.0f} ₽")
        except Exception as e:
            logger.error(f"❌ Failed to send controller notification: {e}")

    async def _continue_to_box(self, message_or_query, context: ContextTypes.DEFAULT_TYPE):
        """Continue to box input"""
        prev_box = context.user_data.get('prev_box', 0)
        safe_value = context.user_data['shift_data']['safe_cash_end']
        
        msg = f"✅ Основная касса: {safe_value:,.0f} ₽\n\n"
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
        shift_label = "☀️ Утро (дневная смена)" if shift_time == "morning" else "🌙 Вечер (ночная смена)"
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
        msg += f"  • Коробка: {data['card2']:,.0f} ₽\n"
        
        if expenses:
            msg += f"\n💸 Расходы (списано):\n"
            for exp in expenses:
                msg += f"  • {exp['amount']:,.0f} ₽ - {exp['reason']}\n"
            msg += f"  ИТОГО: {total_expenses:,.0f} ₽\n"
        
        msg += "\n🔐 Остатки:\n"
        msg += f"  • Основная касса (офиц): {new_official:,.0f} ₽\n"
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
            # Close shift in database
            shift_id = context.user_data.get('active_shift_id')
            if shift_id and self.shift_manager:
                # ПРОВЕРКА: Для ночной смены требуется отметить присутствие уборщицы
                if shift_time == 'evening':
                    try:
                        import sqlite3
                        conn = sqlite3.connect(self.shift_manager.db_path)
                        cursor = conn.cursor()

                        # Проверяем, была ли отмечена уборщица
                        cursor.execute("""
                            SELECT cleaner_was_present FROM cleaning_service_reviews
                            WHERE shift_id = ?
                        """, (shift_id,))

                        result = cursor.fetchone()
                        conn.close()

                        # Если cleaner_was_present = NULL, то отметка не была сделана
                        if not result or result[0] is None:
                            await query.edit_message_text(
                                "⚠️ <b>Внимание!</b>\n\n"
                                "Перед закрытием ночной смены необходимо отметить, была ли уборщица.\n\n"
                                "Пожалуйста, заполните чек-лист 'Отзыв об уборщице' через меню дежурного.",
                                parse_mode='HTML'
                            )
                            # Не очищаем context.user_data, чтобы можно было вернуться
                            return ConversationHandler.END

                    except Exception as check_error:
                        logger.error(f"❌ Error checking cleaner presence: {check_error}")
                        # Не блокируем закрытие смены из-за ошибки проверки

                self.shift_manager.close_shift(shift_id)

            # Save to finmon_shifts table
            if self.improvements:
                saved_shift_id = self.improvements.save_shift_to_db(data)
                if saved_shift_id:
                    logger.info(f"✅ Shift saved to finmon_shifts with ID: {saved_shift_id}")
                else:
                    logger.error("❌ Failed to save shift to finmon_shifts")

            # Send notification to controller
            if self.improvements:
                # Use duty_name from schedule (full name) instead of Telegram username
                admin_name = duty_name if duty_name else (update.effective_user.first_name or update.effective_user.username or "Unknown")
                await self.improvements.send_shift_notification_to_controller(
                    bot=context.bot,
                    shift_data=data,
                    admin_name=admin_name,
                    is_opening=False
                )

            # Get updated balances
            balances = self.finmon.get_club_balances(club)

            # Get shift expenses from DB
            shift_expenses = []
            if shift_id and self.shift_manager:
                shift_expenses = self.shift_manager.get_shift_expenses(shift_id)

            total_expenses = sum(exp['amount'] for exp in shift_expenses)

            msg = "✅ Смена успешно сдана!\n\n"
            msg += f"🏢 {club}\n"
            if shift_expenses:
                msg += f"💸 Списано расходов: {total_expenses:,.0f} ₽\n"
            msg += f"💰 Остатки:\n"
            msg += f"  • Основная касса (офиц): {balances['official']:,.0f} ₽\n"
            msg += f"  • Коробка: {data.get('box_cash_end', 0):,.0f} ₽\n"

            await query.edit_message_text(msg)

            # AUTO-TRIGGER /start IN CLUB CHAT AFTER SHIFT CLOSE
            # Автоматически отправляем /start в чат клуба после закрытия смены
            try:
                club_accounts = context.bot_data.get('club_accounts', {})
                club_lower = club.lower().replace('рио', 'rio').replace('север', 'sever')
                club_chat_id = club_accounts.get(club_lower)

                if club_chat_id:
                    reminder_text = "🔓 *Смена закрыта!*\n\n"
                    reminder_text += "Пожалуйста, откройте новую смену через /start"

                    await context.bot.send_message(
                        chat_id=club_chat_id,
                        text=reminder_text,
                        parse_mode='Markdown'
                    )
                    logger.info(f"✅ Sent /start reminder to {club} club chat ({club_chat_id})")
                else:
                    logger.warning(f"⚠️ Club chat ID not found for {club}")

            except Exception as auto_start_error:
                logger.error(f"❌ Failed to send auto /start reminder: {auto_start_error}")
                # Не прерываем процесс закрытия смены из-за ошибки

            # Успешное сохранение смены
            # (Inline кнопки для управления сменами доступны в главном меню /start)
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
        shift_time = context.user_data.get('shift_time')
        shift_label = "☀️ Утро (дневная смена)" if shift_time == "morning" else "🌙 Вечер (ночная смена)"

        # Save important values that should not be cleared
        prev_official = context.user_data.get('prev_official', 0)
        prev_box = context.user_data.get('prev_box', 0)
        previous_revenue = context.user_data.get('previous_revenue')
        active_shift_id = context.user_data.get('active_shift_id')
        shift_expenses = context.user_data.get('shift_expenses', [])
        previous_cash = context.user_data.get('shift_data', {}).get('safe_cash_start', 0)

        # Clear shift data but keep club and shift_time
        context.user_data['shift_data'] = {
            'admin_id': update.effective_user.id,
            'club': club,
            'shift_type': shift_time,
            'active_shift_id': active_shift_id,
            'fact_cash': 0.0,
            'fact_card': 0.0,
            'qr': 0.0,
            'card2': 0.0,
            'safe_cash_start': previous_cash,
            'safe_cash_end': 0.0,
            'box_cash_start': prev_box,
            'box_cash_end': 0.0,
            'tovarka': 0.0,
            'gamepads': 0,
            'repair': 0,
            'need_repair': 0,
            'games': 0,
            'cash_disabled': False,
            'card_disabled': False,
            'qr_disabled': False,
            'card2_disabled': False,
            'expenses': shift_expenses
        }

        # Restore important values
        context.user_data['prev_official'] = prev_official
        context.user_data['prev_box'] = prev_box
        context.user_data['previous_revenue'] = previous_revenue
        context.user_data['active_shift_id'] = active_shift_id
        context.user_data['shift_expenses'] = shift_expenses
        
        msg = f"📋 Закрытие смены\n\n"
        msg += f"🏢 Клуб: {club}\n"
        msg += f"⏰ {shift_label}\n\n"
        msg += "💰 Введите наличку факт:\n\nПример: 3440"
        
        await query.edit_message_text(msg)
        return ENTER_FACT_CASH
    
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
    
    # ===== Expense Tracking (During Active Shift) =====
    
    async def start_expense(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start expense from inline button callback"""
        query = update.callback_query
        if query:
            await query.answer()

        user_id = update.effective_user.id

        # Check if shift manager is available
        if not self.shift_manager:
            if query:
                await query.edit_message_text("❌ Модуль управления сменами недоступен")
            else:
                await update.message.reply_text("❌ Модуль управления сменами недоступен")
            return ConversationHandler.END

        # Check for active shift
        active_shift = self.shift_manager.get_active_shift(user_id)

        if not active_shift:
            error_msg = (
                "❌ У вас нет открытой смены\n\n"
                "Сначала откройте смену через:\n"
                "🔓 Открыть смену"
            )
            if query:
                await query.edit_message_text(error_msg)
            else:
                await update.message.reply_text(error_msg)
            return ConversationHandler.END

        # Store shift ID for this conversation
        context.user_data['expense_shift_id'] = active_shift['id']
        context.user_data['expense_club'] = active_shift['club']

        # Ask to select cash source
        shift_label = "☀️ Утро" if active_shift['shift_type'] == 'morning' else "🌙 Вечер"

        msg = f"💸 Списание с кассы\n\n"
        msg += f"🏢 Клуб: {active_shift['club']}\n"
        msg += f"⏰ Смена: {shift_label}\n\n"
        msg += "Выберите откуда списать деньги:"

        keyboard = [
            [InlineKeyboardButton("💰 Основная касса", callback_data="expense_main")],
            [InlineKeyboardButton("📦 Коробка", callback_data="expense_box")],
            [InlineKeyboardButton("❌ Отменить", callback_data="expense_cancel")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        if query:
            await query.edit_message_text(msg, reply_markup=reply_markup)
        else:
            await update.message.reply_text(msg, reply_markup=reply_markup)

        return EXPENSE_SELECT_CASH_SOURCE

    async def cmd_expense(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start expense tracking conversation (wrapper for start_expense)"""
        return await self.start_expense(update, context)
    
    async def expense_select_cash_source(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle cash source selection"""
        query = update.callback_query
        await query.answer()
        
        if query.data == "expense_cancel":
            await query.edit_message_text("❌ Списание отменено")
            context.user_data.pop('expense_shift_id', None)
            context.user_data.pop('expense_club', None)
            return ConversationHandler.END
        
        if query.data == "expense_main":
            cash_source = "main"
            source_label = "💰 Основная касса"
        elif query.data == "expense_box":
            cash_source = "box"
            source_label = "📦 Коробка"
        else:
            await query.edit_message_text("❌ Неверный выбор")
            return ConversationHandler.END
        
        context.user_data['expense_cash_source'] = cash_source
        context.user_data['expense_source_label'] = source_label
        
        msg = f"💸 Списание с кассы\n\n"
        msg += f"Касса: {source_label}\n\n"
        msg += "Введите сумму списания:\n\n"
        msg += "Пример: 1500"
        
        await query.edit_message_text(msg)
        return EXPENSE_ENTER_AMOUNT
    
    async def expense_receive_amount(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Receive expense amount"""
        try:
            amount = float(update.message.text.replace(' ', '').replace(',', '.'))
            
            if amount <= 0:
                await update.message.reply_text(
                    "❌ Сумма должна быть больше 0\n\n"
                    "Введите сумму заново:"
                )
                return EXPENSE_ENTER_AMOUNT
            
            context.user_data['expense_amount'] = amount
            
            msg = f"✅ Сумма: {amount:,.0f} ₽\n\n"
            msg += "Введите причину списания:\n\n"
            msg += "Примеры:\n"
            msg += "• Выдано игроку\n"
            msg += "• Оплата поставщику\n"
            msg += "• Сдача клиенту\n"
            msg += "• Расходы на закупку"
            
            await update.message.reply_text(msg)
            return EXPENSE_ENTER_REASON
            
        except ValueError:
            await update.message.reply_text(
                "❌ Неверный формат\n\n"
                "Введите число:"
            )
            return EXPENSE_ENTER_AMOUNT
    
    async def expense_receive_reason(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Receive expense reason"""
        reason = update.message.text.strip()
        
        if not reason or len(reason) > 200:
            await update.message.reply_text(
                "❌ Причина должна быть от 1 до 200 символов\n\n"
                "Попробуйте снова:"
            )
            return EXPENSE_ENTER_REASON
        
        context.user_data['expense_reason'] = reason
        
        # Show confirmation
        amount = context.user_data['expense_amount']
        source_label = context.user_data['expense_source_label']
        club = context.user_data['expense_club']
        
        msg = f"💸 Подтверждение списания\n\n"
        msg += f"🏢 Клуб: {club}\n"
        msg += f"Касса: {source_label}\n"
        msg += f"💰 Сумма: {amount:,.0f} ₽\n"
        msg += f"📝 Причина: {reason}\n\n"
        msg += "Подтвердите списание:"
        
        keyboard = [
            [InlineKeyboardButton("✅ Подтвердить", callback_data="expense_confirm")],
            [InlineKeyboardButton("❌ Отменить", callback_data="expense_cancel")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(msg, reply_markup=reply_markup)
        return EXPENSE_CONFIRM
    
    async def expense_confirm(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Confirm and save expense"""
        query = update.callback_query
        await query.answer()
        
        if query.data == "expense_cancel":
            await query.edit_message_text("❌ Списание отменено")
            # Clear expense data
            for key in list(context.user_data.keys()):
                if key.startswith('expense_'):
                    context.user_data.pop(key)
            return ConversationHandler.END
        
        # Get expense data
        shift_id = context.user_data.get('expense_shift_id')
        cash_source = context.user_data.get('expense_cash_source')
        amount = context.user_data.get('expense_amount')
        reason = context.user_data.get('expense_reason')
        source_label = context.user_data.get('expense_source_label')
        
        # Save to database
        success = self.shift_manager.add_expense(shift_id, cash_source, amount, reason)
        
        if success:
            await query.edit_message_text(
                f"✅ Списание сохранено!\n\n"
                f"Касса: {source_label}\n"
                f"💰 Сумма: {amount:,.0f} ₽\n"
                f"📝 {reason}"
            )
            
            # Notify owner
            if self.owner_ids:
                for owner_id in self.owner_ids:
                    try:
                        club = context.user_data.get('expense_club')
                        user = query.from_user
                        notify_msg = f"💸 Списание в смене #{shift_id}\n\n"
                        notify_msg += f"🏢 {club} | {source_label}\n"
                        notify_msg += f"💰 {amount:,.0f} ₽\n"
                        notify_msg += f"📝 {reason}\n\n"
                        notify_msg += f"👤 {user.full_name or 'Неизвестно'}"
                        if user.username:
                            notify_msg += f" (@{user.username})"
                        
                        await context.bot.send_message(chat_id=owner_id, text=notify_msg)
                    except:
                        pass
        else:
            await query.edit_message_text("❌ Не удалось сохранить списание. Попробуйте позже.")
        
        # Clear expense data
        for key in list(context.user_data.keys()):
            if key.startswith('expense_'):
                context.user_data.pop(key)
        
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
    
    # ===== Schedule Integration Handlers =====
    
    async def handle_duty_replacement_response(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle response from scheduled duty person about replacement"""
        query = update.callback_query
        await query.answer()
        
        # Parse callback data: duty_confirm/duty_reject_opener_id_club_shift_type
        parts = query.data.split('_')
        if len(parts) < 5:
            await query.edit_message_text("❌ Ошибка данных")
            return
        
        action = parts[1]  # confirm or reject
        opener_id = int(parts[2])
        club = parts[3]
        shift_type = parts[4]
        
        shift_label = "☀️ Утро" if shift_type == "morning" else "🌙 Вечер"
        
        if action == "confirm":
            # Duty person confirms - open shift immediately
            confirmed_by = query.from_user.id

            # Log the replacement for tracking
            confirmer_name = query.from_user.full_name or query.from_user.username or f"ID {confirmed_by}"
            logger.info(f"🔄 REPLACEMENT: Shift {club}/{shift_type} confirmed by {confirmer_name} (ID: {confirmed_by})")

            # Get full name from admin database for Google Sheets update
            confirmer_full_name = None
            if self.admin_db:
                admin_info = self.admin_db.get_admin(confirmed_by)
                if admin_info:
                    confirmer_full_name = admin_info.get('full_name')
                    logger.info(f"📋 Got full name from admin DB: {confirmer_full_name}")

            # Determine shift_date based on shift_type
            _, shift_date = get_shift_type_for_opening()

            shift_id = self.shift_manager.open_shift(opener_id, club, shift_type, shift_date, confirmed_by)

            if shift_id:
                # Save shift_id in context for checklist
                context.user_data['current_shift_id'] = shift_id

                # Get scheduled duty name to show if it was a replacement
                scheduled_duty_name = None
                if self.schedule_parser:
                    try:
                        scheduled_duty_name = self.schedule_parser.get_duty_name(club, shift_date, shift_type)
                        logger.info(f"🔍 Got scheduled duty name: {scheduled_duty_name} for {club}/{shift_type}")
                    except Exception as e:
                        logger.error(f"❌ Failed to get scheduled duty name: {e}")

                replacement_info = ""
                if scheduled_duty_name and scheduled_duty_name != confirmer_name:
                    replacement_info = f"\n\n🔄 Замена: {scheduled_duty_name} → {confirmer_name}"
                    logger.info(f"📋 REPLACEMENT DETECTED: {scheduled_duty_name} → {confirmer_name}")

                    # Update Google Sheets with replacement (use full name if available)
                    if self.schedule_parser and confirmer_full_name:
                        try:
                            success = self.schedule_parser.update_duty_assignment(
                                duty_date=date.today(),
                                club=club,
                                shift_type=shift_type,
                                old_admin_name=scheduled_duty_name,
                                new_admin_name=confirmer_full_name
                            )
                            if success:
                                logger.info(f"✅ Google Sheets updated with replacement")
                            else:
                                logger.warning(f"⚠️ Failed to update Google Sheets")
                        except Exception as e:
                            logger.error(f"❌ Error updating Google Sheets: {e}")

                # Delete ALL pending confirmation messages for this shift
                confirmation_key = f"{opener_id}_{club}_{shift_type}"
                if 'pending_confirmation_messages' in context.bot_data:
                    messages_to_delete = context.bot_data['pending_confirmation_messages'].get(confirmation_key, [])
                    for msg_info in messages_to_delete:
                        try:
                            # Skip the current message (it will be edited below)
                            if msg_info['chat_id'] == query.message.chat_id and msg_info['message_id'] == query.message.message_id:
                                continue
                            await context.bot.delete_message(
                                chat_id=msg_info['chat_id'],
                                message_id=msg_info['message_id']
                            )
                            logger.info(f"✅ Deleted confirmation message from chat {msg_info['chat_id']}")
                        except Exception as e:
                            logger.warning(f"⚠️ Could not delete message {msg_info['message_id']} from {msg_info['chat_id']}: {e}")

                    # Clear the list
                    context.bot_data['pending_confirmation_messages'].pop(confirmation_key, None)

                # Добавляем кнопки НОВЫХ чек-листов приема смены
                keyboard = [
                    [InlineKeyboardButton("⭐️ Рейтинг уборки", callback_data="rating_start")],
                    [InlineKeyboardButton("📦 Чек-лист инвентаря", callback_data="inventory_start")]
                ]

                # Отзыв об уборщице только для ночной смены
                if shift_type == 'evening':
                    keyboard.insert(1, [InlineKeyboardButton("🧹 Отзыв об уборщице", callback_data="review_start")])

                keyboard.append([InlineKeyboardButton("« Главное меню", callback_data="main_menu")])
                reply_markup = InlineKeyboardMarkup(keyboard)

                await query.edit_message_text(
                    f"✅ Смена подтверждена и открыта!\n\n"
                    f"🏢 {club} | {shift_label}\n"
                    f"🆔 ID смены: {shift_id}\n"
                    f"✅ Подтверждено: {query.from_user.full_name or 'Вы'}"
                    f"{replacement_info}\n\n"
                    f"📋 Обязательные чек-листы:\n"
                    f"• ⭐️ Рейтинг уборки (30 мин)\n"
                    f"• 📦 Инвентарь (4 часа)\n"
                    + (f"• 🧹 Отзыв об уборщице\n" if shift_type == 'evening' else ""),
                    reply_markup=reply_markup
                )

                # Update the pending message in club account if exists
                pending_msg = None
                if context.bot_data.get('pending_shift_messages'):
                    pending_msg = context.bot_data['pending_shift_messages'].get(opener_id)

                if pending_msg:
                    try:
                        await context.bot.edit_message_text(
                            chat_id=pending_msg['chat_id'],
                            message_id=pending_msg['message_id'],
                            text=f"✅ Смена открыта!\n\n"
                                 f"🏢 {club} | {shift_label}\n"
                                 f"🆔 ID смены: {shift_id}\n\n"
                                 f"Смена подтверждена дежурным.\n"
                                 f"Используйте кнопки в главном меню для работы."
                        )
                        # Clear pending message data
                        context.bot_data['pending_shift_messages'].pop(opener_id, None)
                    except Exception as e:
                        logger.error(f"Failed to update pending message: {e}")

                # Notify the opener with dynamic keyboard (only if different from club account)
                # If opener opened from club account, the message above already updated
                if not pending_msg:
                    try:
                        # Update dynamic keyboard for opener
                        reply_keyboard = self.bot_instance._build_reply_keyboard(opener_id) if hasattr(self, 'bot_instance') else None

                        await context.bot.send_message(
                            chat_id=opener_id,
                            text=f"✅ Смена открыта!\n\n"
                                 f"🏢 {club} | {shift_label}\n"
                                 f"🆔 ID смены: {shift_id}\n\n"
                                 f"Смена подтверждена дежурным.\n"
                                 f"Для списания денег используйте:\n"
                                 f"💸 Списать с кассы",
                            reply_markup=reply_keyboard
                        )
                    except Exception as e:
                        logger.error(f"Failed to notify opener: {e}")

                # Send notification to controller
                if self.improvements:
                    admin_name = query.from_user.full_name or query.from_user.username or "Unknown"
                    shift_data = {
                        'club': club,
                        'shift_type': shift_type,
                        'admin_id': confirmed_by
                    }
                    # Removed controller notification for shift opening
                    # Controller will only be notified when shift is closed

                # Уведомления владельцу отключены - теперь только контролирующему при закрытии
            else:
                await query.edit_message_text("❌ Ошибка при открытии смены")
            
        elif action == "reject":
            # Duty person says it's an error - delete the message
            try:
                await query.message.delete()
                logger.info(f"✅ Deleted confirmation message from admin {query.from_user.id}")
            except Exception as e:
                logger.error(f"❌ Failed to delete confirmation message: {e}")
                # Fallback - edit message instead
                await query.edit_message_text(
                    f"❌ Замена отклонена\n\n"
                    f"Вы отметили это как ошибку"
                )

            # Delete ALL pending confirmation messages for this shift
            confirmation_key = f"{opener_id}_{club}_{shift_type}"
            if 'pending_confirmation_messages' in context.bot_data:
                messages_to_delete = context.bot_data['pending_confirmation_messages'].get(confirmation_key, [])
                for msg_info in messages_to_delete:
                    try:
                        await context.bot.delete_message(
                            chat_id=msg_info['chat_id'],
                            message_id=msg_info['message_id']
                        )
                        logger.info(f"✅ Deleted confirmation message from chat {msg_info['chat_id']}")
                    except Exception as e:
                        # Message might already be deleted
                        logger.warning(f"⚠️ Could not delete message {msg_info['message_id']} from {msg_info['chat_id']}: {e}")

                # Clear the list
                context.bot_data['pending_confirmation_messages'].pop(confirmation_key, None)

            # Notify the opener
            try:
                await context.bot.send_message(
                    chat_id=opener_id,
                    text=f"⚠️ Дежурный по расписанию отклонил замену\n\n"
                    f"Возможно произошла ошибка.\n"
                    f"Свяжитесь с администрацией."
                )
            except:
                pass

            # Notify only controller, not owner
            if self.controller_id:
                try:
                    await context.bot.send_message(
                        chat_id=self.controller_id,
                        text=f"⚠️ ОТКЛОНЕНА ЗАМЕНА\n\n"
                        f"🏢 {club} | {shift_label}\n"
                        f"Дежурный по расписанию отклонил открытие смены пользователем {opener_id}\n\n"
                        f"Проверьте ситуацию!"
                    )
                except:
                    pass
    
    async def handle_owner_schedule_update(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle owner's decision to update schedule after replacement"""
        query = update.callback_query
        await query.answer()
        
        # Parse callback data
        if query.data.startswith("owner_schedule_yes_"):
            # owner_schedule_yes_shift_id_club_shift_type_user_id
            parts = query.data.split('_')
            if len(parts) < 7:
                await query.edit_message_text("❌ Ошибка данных")
                return
            
            shift_id = int(parts[3])
            club = parts[4]
            shift_type = parts[5]
            new_admin_id = int(parts[6])
            
            # Get admin info
            admin_name = query.message.text.split("👤 ")[1].split("\n")[0] if "👤 " in query.message.text else "Неизвестно"
            
            # Update schedule
            if self.shift_manager:
                success = self.shift_manager.update_duty_schedule(
                    duty_date=date.today(),
                    club=club,
                    shift_type=shift_type,
                    admin_id=new_admin_id,
                    admin_name=admin_name
                )
                
                if success:
                    await query.edit_message_text(
                        query.message.text + "\n\n✅ Расписание обновлено"
                    )
                else:
                    await query.edit_message_text(
                        query.message.text + "\n\n❌ Не удалось обновить расписание"
                    )
            else:
                await query.edit_message_text(
                    query.message.text + "\n\n❌ Модуль расписания недоступен"
                )
        
        elif query.data.startswith("owner_schedule_no_"):
            # owner_schedule_no_shift_id
            await query.edit_message_text(
                query.message.text + "\n\n✅ Разовая замена (расписание не изменено)"
            )
    
    # ===== Cash Withdrawal Methods =====
    
    async def start_cash_withdrawal(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start cash withdrawal process during shift"""
        # Handle both message and callback query
        if update.callback_query:
            query = update.callback_query
            await query.answer()
            user_id = query.from_user.id
            send_method = query.edit_message_text
        else:
            user_id = update.effective_user.id
            send_method = update.message.reply_text

        # Check if user has active shift
        active_shift = None
        if self.shift_manager:
            active_shift = self.shift_manager.get_active_shift(user_id)

        if not active_shift:
            await send_method(
                "❌ У вас нет активной смены\n\n"
                "Сначала откройте смену, чтобы взять зарплату с кассы"
            )
            return ConversationHandler.END

        # Store shift info in context
        context.user_data['withdrawal_shift_id'] = active_shift['id']
        context.user_data['withdrawal_club'] = active_shift['club']

        # Get admin name for display
        if update.callback_query:
            admin_name = query.from_user.full_name or "Админ"
        else:
            admin_name = update.effective_user.full_name or "Админ"

        msg = f"💰 Взять зарплату с кассы\n\n"
        msg += f"👤 {admin_name}\n"
        msg += f"🏢 Клуб: {active_shift['club']}\n"
        msg += f"🆔 Смена: #{active_shift['id']}\n\n"
        msg += "Выберите кассу:"

        keyboard = [
            [InlineKeyboardButton("🔐 Основная касса", callback_data="withdrawal_main")],
            [InlineKeyboardButton("📦 Бокс", callback_data="withdrawal_box")],
            [InlineKeyboardButton("❌ Отменить", callback_data="withdrawal_cancel")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await send_method(msg, reply_markup=reply_markup)
        return WITHDRAWAL_SELECT_CASH_SOURCE

    async def withdrawal_select_cash_source(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle cash source selection for withdrawal"""
        query = update.callback_query
        await query.answer()

        if query.data == "withdrawal_cancel":
            await query.edit_message_text("❌ Снятие отменено")
            return ConversationHandler.END

        # Parse cash source
        if query.data == "withdrawal_main":
            cash_source = "main"
            source_label = "🔐 Основная касса"
        elif query.data == "withdrawal_box":
            cash_source = "box"
            source_label = "📦 Бокс"
        else:
            await query.edit_message_text("❌ Неверный выбор кассы")
            return ConversationHandler.END

        # Store cash source in context
        context.user_data['withdrawal_cash_source'] = cash_source
        context.user_data['withdrawal_source_label'] = source_label

        # Ask for amount
        club = context.user_data.get('withdrawal_club', 'Неизвестно')
        shift_id = context.user_data.get('withdrawal_shift_id', 0)

        msg = f"💰 Взять зарплату с кассы\n\n"
        msg += f"🏢 Клуб: {club}\n"
        msg += f"🆔 Смена: #{shift_id}\n"
        msg += f"💼 Касса: {source_label}\n\n"
        msg += "Введите сумму для снятия:\n\n"
        msg += "Пример: 5000"

        await query.edit_message_text(msg)
        return WITHDRAWAL_ENTER_AMOUNT

    async def receive_withdrawal_amount(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Receive withdrawal amount"""
        try:
            amount = float(update.message.text.replace(' ', '').replace(',', '.'))
            
            if amount <= 0:
                await update.message.reply_text(
                    "❌ Сумма должна быть больше 0\n\n"
                    "Введите сумму заново:"
                )
                return WITHDRAWAL_ENTER_AMOUNT
            
            # Store amount for confirmation
            context.user_data['withdrawal_amount'] = amount
            
            # Get active shift info
            user_id = update.effective_user.id
            active_shift = self.shift_manager.get_active_shift(user_id) if self.shift_manager else None
            
            if not active_shift:
                await update.message.reply_text("❌ Активная смена не найдена")
                return
            
            admin_name = update.effective_user.full_name or "Админ"
            source_label = context.user_data.get('withdrawal_source_label', '🔐 Основная касса')

            msg = f"💰 Подтверждение снятия\n\n"
            msg += f"👤 {admin_name}\n"
            msg += f"🏢 Клуб: {active_shift['club']}\n"
            msg += f"🆔 Смена: #{active_shift['id']}\n"
            msg += f"💼 Касса: {source_label}\n\n"
            msg += f"💵 Сумма: {amount:,.0f} ₽\n\n"
            msg += "Подтвердите снятие зарплаты с кассы:"
            
            keyboard = [
                [InlineKeyboardButton("✅ Да, снять", callback_data="withdrawal_confirm")],
                [InlineKeyboardButton("❌ Отменить", callback_data="withdrawal_cancel")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(msg, reply_markup=reply_markup)
            return WITHDRAWAL_CONFIRM
            
        except ValueError:
            await update.message.reply_text(
                "❌ Неверный формат\n\n"
                "Введите число:"
            )
            return WITHDRAWAL_ENTER_AMOUNT
    
    async def handle_withdrawal_confirmation(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle withdrawal confirmation"""
        query = update.callback_query
        await query.answer()
        
        if query.data == "withdrawal_cancel":
            await query.edit_message_text("❌ Снятие отменено")
            return
        
        if query.data == "withdrawal_confirm":
            user_id = query.from_user.id
            amount = context.user_data.get('withdrawal_amount', 0)
            cash_source = context.user_data.get('withdrawal_cash_source', 'main')
            source_label = context.user_data.get('withdrawal_source_label', '🔐 Основная касса')

            if amount <= 0:
                await query.edit_message_text("❌ Неверная сумма")
                return

            # Get active shift
            active_shift = self.shift_manager.get_active_shift(user_id) if self.shift_manager else None
            if not active_shift:
                await query.edit_message_text("❌ Активная смена не найдена")
                return

            # Record withdrawal in database
            try:
                # Import salary calculator to record withdrawal
                from modules.salary_calculator import SalaryCalculator
                salary_calc = SalaryCalculator(self.shift_manager.db_path if hasattr(self.shift_manager, 'db_path') else 'club_assistant.db')

                withdrawal_id = salary_calc.record_cash_withdrawal(
                    shift_id=active_shift['id'],
                    admin_id=user_id,
                    amount=amount,
                    reason='salary',
                    cash_source=cash_source
                )

                if withdrawal_id:
                    admin_name = query.from_user.full_name or "Админ"

                    await query.edit_message_text(
                        f"✅ Зарплата снята с кассы\n\n"
                        f"👤 {admin_name}\n"
                        f"🏢 Клуб: {active_shift['club']}\n"
                        f"🆔 Смена: #{active_shift['id']}\n"
                        f"💼 Касса: {source_label}\n\n"
                        f"💵 Сумма: {amount:,.0f} ₽\n"
                        f"📝 Запись: #{withdrawal_id}\n\n"
                        f"Сумма будет учтена при расчете зарплаты"
                    )

                    # Notify owner about cash withdrawal with revert button
                    if self.owner_ids:
                        for owner_id in self.owner_ids:
                            try:
                                notify_msg = f"💰 Снятие зарплаты с кассы\n\n"
                                notify_msg += f"👤 {admin_name} (ID: {user_id})\n"
                                notify_msg += f"🏢 Клуб: {active_shift['club']}\n"
                                notify_msg += f"🆔 Смена: #{active_shift['id']}\n"
                                notify_msg += f"💼 Касса: {source_label}\n"
                                notify_msg += f"💵 Сумма: {amount:,.0f} ₽\n"
                                notify_msg += f"📅 {now_msk().strftime('%d.%m.%Y %H:%M')} МСК"

                                # Add revert button only for controller
                                keyboard = []
                                if owner_id == self.controller_id:
                                    keyboard.append([
                                        InlineKeyboardButton(
                                            "🔄 Вернуть деньги",
                                            callback_data=f"revert_withdrawal_{withdrawal_id}"
                                        )
                                    ])

                                reply_markup = InlineKeyboardMarkup(keyboard) if keyboard else None
                                await context.bot.send_message(
                                    chat_id=owner_id,
                                    text=notify_msg,
                                    reply_markup=reply_markup
                                )
                            except Exception as e:
                                logger.error(f"Failed to send withdrawal notification: {e}")
                else:
                    await query.edit_message_text("❌ Не удалось записать снятие")
                    
            except Exception as e:
                logger.error(f"Failed to record cash withdrawal: {e}")
                await query.edit_message_text("❌ Ошибка при записи снятия")

    async def cmd_shift_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показать статус смен и остатки в кассах"""
        try:
            user_id = update.effective_user.id

            # Проверка прав доступа - только владелец и контролирующий
            allowed_ids = []
            if self.owner_ids:
                allowed_ids.extend(self.owner_ids)
            if self.controller_id:
                allowed_ids.append(self.controller_id)

            if user_id not in allowed_ids:
                await update.message.reply_text("❌ Команда доступна только владельцу и контролирующему")
                return

            # Получаем активные смены
            if not self.shift_manager:
                await update.message.reply_text("❌ Модуль управления сменами недоступен")
                return

            active_shifts = self.shift_manager.get_all_active_shifts()

            # Получаем остатки из финмона
            balances = {}
            if self.finmon:
                try:
                    balances = self.finmon.get_balances()
                except Exception as e:
                    logger.error(f"Failed to get balances: {e}")

            # Формируем сообщение
            msg = "📊 <b>Статус смен</b>\n\n"

            if active_shifts:
                for shift in active_shifts:
                    try:
                        shift_type_label = "☀️ Утро" if shift.get('shift_type') == "morning" else "🌙 Вечер"
                        opened_at = datetime.fromisoformat(shift['opened_at'])

                        # Получаем имя админа
                        admin_name = f"ID {shift.get('admin_id', 'Unknown')}"
                        if self.admin_db:
                            try:
                                admin = self.admin_db.get_admin(shift['admin_id'])
                                if admin:
                                    admin_name = admin.get('full_name') or admin.get('username') or admin_name
                            except Exception as e:
                                logger.error(f"Failed to get admin info: {e}")

                        msg += f"🏢 <b>{shift.get('club', 'N/A')}</b> {shift_type_label}\n"
                        msg += f"👤 {admin_name}\n"
                        msg += f"🕐 Открыта: {opened_at.strftime('%d.%m.%Y %H:%M')}\n"
                        msg += f"🆔 Смена: #{shift.get('id', 'N/A')}\n\n"
                    except Exception as e:
                        logger.error(f"Error formatting shift: {e}")
                        continue
            else:
                msg += "❌ Нет открытых смен\n\n"

            # Показываем остатки в кассах
            msg += "💰 <b>Остатки в кассах</b>\n\n"

            if balances:
                for club, amounts in balances.items():
                    try:
                        msg += f"🏢 <b>{club}</b>\n"
                        msg += f"🔐 Основная касса: {amounts.get('official', 0):,.0f} ₽\n"
                        msg += f"📦 Бокс: {amounts.get('box', 0):,.0f} ₽\n"
                        total = amounts.get('official', 0) + amounts.get('box', 0)
                        msg += f"💵 Всего: {total:,.0f} ₽\n\n"
                    except Exception as e:
                        logger.error(f"Error formatting balance for {club}: {e}")
                        continue
            else:
                msg += "Данные отсутствуют (касса пуста)\n"

            await update.message.reply_text(msg, parse_mode='HTML')
        except Exception as e:
            logger.error(f"Error in cmd_shift_status: {e}")
            await update.message.reply_text(f"❌ Ошибка при получении статуса: {str(e)}")

    async def handle_revert_withdrawal(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle withdrawal revert button press (only for controller)"""
        query = update.callback_query
        await query.answer()

        user_id = query.from_user.id

        # Check if user is controller
        if user_id != self.controller_id:
            await query.answer("❌ Только контролирующий может возвращать деньги", show_alert=True)
            return

        # Parse callback data: revert_withdrawal_{withdrawal_id}
        try:
            parts = query.data.split('_')
            withdrawal_id = int(parts[2])
        except (IndexError, ValueError):
            await query.answer("❌ Ошибка: неверный формат данных", show_alert=True)
            return

        # Get controller info
        controller_name = query.from_user.full_name or query.from_user.username or f"ID {user_id}"

        # Revert withdrawal
        try:
            from modules.salary_calculator import SalaryCalculator
            salary_calc = SalaryCalculator(self.shift_manager.db_path if hasattr(self.shift_manager, 'db_path') else 'club_assistant.db')

            withdrawal_info = salary_calc.revert_withdrawal(withdrawal_id, user_id, controller_name)

            if withdrawal_info:
                # Update the message to show it's reverted
                original_text = query.message.text
                reverted_text = f"🔄 ДЕНЬГИ ВОЗВРАЩЕНЫ\n\n{original_text}\n\n"
                reverted_text += f"✅ Возврат выполнен: {controller_name}\n"
                reverted_text += f"⏰ {now_msk().strftime('%d.%m.%Y %H:%M')} МСК"

                await query.edit_message_text(reverted_text)

                # Notify all owners about the revert
                if self.owner_ids:
                    for owner_id in self.owner_ids:
                        try:
                            cash_source_label = "🔐 Основная касса" if withdrawal_info.get('cash_source') == 'main' else "📦 Бокс"
                            notify_msg = f"🔄 Возврат снятия зарплаты\n\n"
                            notify_msg += f"🆔 Снятие #{withdrawal_id}\n"
                            notify_msg += f"🏢 {withdrawal_info['club']}\n"
                            notify_msg += f"💼 Касса: {cash_source_label}\n"
                            notify_msg += f"💰 {withdrawal_info['amount']:,.0f} ₽ возвращено в кассу\n\n"
                            notify_msg += f"👤 Возврат выполнен: {controller_name}"

                            await context.bot.send_message(chat_id=owner_id, text=notify_msg)
                        except Exception as e:
                            logger.error(f"Failed to send revert notification: {e}")

                await query.answer("✅ Деньги возвращены в кассу", show_alert=True)
            else:
                await query.answer("❌ Ошибка при возврате. Возможно, снятие уже было отменено.", show_alert=True)
        except Exception as e:
            logger.error(f"Failed to revert withdrawal: {e}")
            await query.answer(f"❌ Ошибка при возврате: {str(e)}", show_alert=True)