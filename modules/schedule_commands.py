#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Schedule Commands - Команды управления расписанием смен
"""

import logging
from datetime import datetime, date, timedelta
from typing import Optional

from telegram import Update
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)

# Club name normalization
CLUB_ALIASES = {
    'rio': 'Рио',
    'рио': 'Рио',
    'r': 'Рио',
    'р': 'Рио',
    'sever': 'Север',
    'север': 'Север',
    's': 'Север',
    'с': 'Север',
}

# Shift type normalization
SHIFT_TYPE_ALIASES = {
    'morning': 'morning',
    'утро': 'morning',
    'm': 'morning',
    'у': 'morning',
    'evening': 'evening',
    'вечер': 'evening',
    'e': 'evening',
    'в': 'evening',
}


class ScheduleCommands:
    """Commands for managing duty schedule"""
    
    def __init__(self, shift_manager, owner_ids: list = None, schedule_parser=None, admin_db=None):
        """
        Initialize schedule commands

        Args:
            shift_manager: ShiftManager instance
            owner_ids: List of owner telegram IDs
            schedule_parser: ScheduleParser instance (optional)
            admin_db: AdminDB instance (optional)
        """
        self.shift_manager = shift_manager
        self.owner_ids = owner_ids or []
        self.schedule_parser = schedule_parser
        self.admin_db = admin_db
    
    def is_owner(self, user_id: int) -> bool:
        """Check if user is owner"""
        return user_id in self.owner_ids
    
    def normalize_club(self, club_str: str) -> Optional[str]:
        """Normalize club name"""
        club_lower = club_str.lower().strip()
        return CLUB_ALIASES.get(club_lower)
    
    def normalize_shift_type(self, shift_str: str) -> Optional[str]:
        """Normalize shift type"""
        shift_lower = shift_str.lower().strip()
        return SHIFT_TYPE_ALIASES.get(shift_lower)
    
    def parse_date(self, date_str: str) -> Optional[date]:
        """
        Parse date from string
        
        Supported formats:
        - DD.MM.YYYY
        - DD.MM.YY
        - DD.MM (current year)
        - YYYY-MM-DD
        """
        date_str = date_str.strip()
        
        try:
            # Try DD.MM.YYYY
            if '.' in date_str:
                parts = date_str.split('.')
                if len(parts) == 3:
                    day, month, year = parts
                    if len(year) == 2:
                        year = '20' + year
                    return date(int(year), int(month), int(day))
                elif len(parts) == 2:
                    # DD.MM - use current year
                    day, month = parts
                    year = date.today().year
                    return date(year, int(month), int(day))
            
            # Try YYYY-MM-DD
            if '-' in date_str:
                return date.fromisoformat(date_str)
            
            return None
            
        except Exception as e:
            logger.error(f"❌ Failed to parse date '{date_str}': {e}")
            return None
    
    async def cmd_schedule(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Main schedule command router
        
        Usage:
            /schedule add <date> <club> <shift> <name> [id]
            /schedule week [start_date]
            /schedule today
            /schedule remove <date> <club> <shift>
            /schedule clear [period]
        """
        # Only admins can use schedule commands
        if not self.is_owner(update.effective_user.id):
            await update.message.reply_text("❌ Эта команда доступна только владельцу")
            return
        
        if not context.args:
            gs_status = "✅ Подключено" if self.schedule_parser else "❌ Не настроено"
            await update.message.reply_text(
                "📅 Управление расписанием смен\n\n"
                "Команды:\n"
                "/schedule add <дата> <клуб> <утро/вечер> <имя> [ID]\n"
                "/schedule week [дата_начала]\n"
                "/schedule today\n"
                "/schedule remove <дата> <клуб> <утро/вечер>\n"
                "/schedule clear [old/week/all]\n"
                "/schedule sync [дней] - синхронизация из Google Sheets\n"
                "/schedule test [дата] - тест парсинга Google Sheets\n\n"
                f"Google Sheets: {gs_status}\n\n"
                "Пример:\n"
                "/schedule add 27.10 rio evening Петров 123456"
            )
            return
        
        subcommand = context.args[0].lower()
        
        if subcommand == 'add':
            await self.cmd_schedule_add(update, context)
        elif subcommand == 'week':
            await self.cmd_schedule_week(update, context)
        elif subcommand == 'today':
            await self.cmd_schedule_today(update, context)
        elif subcommand == 'remove':
            await self.cmd_schedule_remove(update, context)
        elif subcommand == 'clear':
            await self.cmd_schedule_clear(update, context)
        elif subcommand == 'sync':
            await self.cmd_schedule_sync(update, context)
        elif subcommand == 'test':
            await self.cmd_schedule_test(update, context)
        else:
            await update.message.reply_text(
                f"❌ Неизвестная подкоманда: {subcommand}\n\n"
                "Доступные: add, week, today, remove, clear, sync, test"
            )
    
    async def cmd_schedule_add(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Add duty to schedule
        
        Usage: /schedule add <date> <club> <shift> <name> [id]
        Example: /schedule add 27.10 rio evening Петров 123456
        """
        args = context.args[1:]  # Skip 'add'
        
        if len(args) < 4:
            await update.message.reply_text(
                "❌ Недостаточно аргументов\n\n"
                "Использование:\n"
                "/schedule add <дата> <клуб> <утро/вечер> <имя> [ID]\n\n"
                "Пример:\n"
                "/schedule add 27.10 rio evening Петров 123456"
            )
            return
        
        # Parse arguments
        date_str = args[0]
        club_str = args[1]
        shift_str = args[2]
        
        # Name can be multiple words
        if len(args) >= 5 and args[-1].isdigit():
            # Last arg is ID
            admin_id = int(args[-1])
            admin_name = ' '.join(args[3:-1])
        else:
            # No ID provided
            admin_id = None
            admin_name = ' '.join(args[3:])
        
        # Normalize and validate
        duty_date = self.parse_date(date_str)
        if not duty_date:
            await update.message.reply_text(f"❌ Неверный формат даты: {date_str}\n\nИспользуйте: DD.MM или DD.MM.YYYY")
            return
        
        club = self.normalize_club(club_str)
        if not club:
            await update.message.reply_text(
                f"❌ Неверный клуб: {club_str}\n\n"
                f"Доступные: rio, рио, sever, север"
            )
            return
        
        shift_type = self.normalize_shift_type(shift_str)
        if not shift_type:
            await update.message.reply_text(
                f"❌ Неверное время смены: {shift_str}\n\n"
                f"Доступные: morning, утро, evening, вечер"
            )
            return
        
        # Add to schedule
        success = self.shift_manager.add_duty_schedule(
            duty_date=duty_date,
            club=club,
            shift_type=shift_type,
            admin_id=admin_id,
            admin_name=admin_name
        )
        
        if success:
            shift_label = "☀️ Утро" if shift_type == "morning" else "🌙 Вечер"
            msg = f"✅ Добавлено в расписание\n\n"
            msg += f"📅 {duty_date.strftime('%d.%m.%Y')}\n"
            msg += f"🏢 {club}\n"
            msg += f"⏰ {shift_label}\n"
            msg += f"👤 {admin_name}"
            if admin_id:
                msg += f" (ID: {admin_id})"
            
            await update.message.reply_text(msg)
        else:
            await update.message.reply_text("❌ Не удалось добавить в расписание")
    
    async def cmd_schedule_week(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Show week schedule
        
        Usage: /schedule week [start_date]
        """
        args = context.args[1:]  # Skip 'week'
        
        # Parse start date
        if args:
            start_date = self.parse_date(args[0])
            if not start_date:
                await update.message.reply_text(f"❌ Неверный формат даты: {args[0]}")
                return
        else:
            start_date = date.today()
        
        # Get schedule
        schedule = self.shift_manager.get_week_schedule(start_date, days=7)
        
        if not schedule:
            await update.message.reply_text(
                f"📅 Расписание пусто\n\n"
                f"Период: {start_date.strftime('%d.%m')} - {(start_date + timedelta(days=6)).strftime('%d.%m.%Y')}\n\n"
                f"Используйте /schedule add для добавления"
            )
            return
        
        # Group by date and club
        by_date = {}
        for entry in schedule:
            entry_date = entry['date']
            if entry_date not in by_date:
                by_date[entry_date] = {'Рио': {}, 'Север': {}}
            
            club = entry['club']
            shift_type = entry['shift_type']
            admin_name = entry.get('admin_name', 'Не назначен')
            
            by_date[entry_date][club][shift_type] = admin_name
        
        # Build message
        end_date = start_date + timedelta(days=6)
        msg = f"📅 Расписание на неделю ({start_date.strftime('%d.%m')} - {end_date.strftime('%d.%m.%Y')})\n\n"
        
        for day_offset in range(7):
            current_date = start_date + timedelta(days=day_offset)
            date_str = current_date.strftime('%Y-%m-%d')
            weekday = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс'][current_date.weekday()]
            
            if date_str in by_date:
                msg += f"📆 {current_date.strftime('%d.%m')} ({weekday}):\n"
                
                for club in ['Рио', 'Север']:
                    if by_date[date_str][club]:
                        morning = by_date[date_str][club].get('morning', '-')
                        evening = by_date[date_str][club].get('evening', '-')
                        msg += f"  🏢 {club}: ☀️ {morning} | 🌙 {evening}\n"
                
                msg += "\n"
        
        if len(msg) > 4000:
            msg = msg[:4000] + "..."
        
        await update.message.reply_text(msg)
    
    async def cmd_schedule_today(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show today's schedule"""
        today = date.today()
        
        msg = f"📅 Дежурства сегодня ({today.strftime('%d.%m.%Y')})\n\n"
        
        has_data = False
        for club in ['Рио', 'Север']:
            club_data = []
            
            for shift_type, shift_label in [('morning', '☀️ Утро'), ('evening', '🌙 Вечер')]:
                duty_info = self.shift_manager.get_expected_duty(club, shift_type, today)
                
                if duty_info:
                    admin_name = duty_info.get('admin_name', 'Не назначен')
                    admin_id = duty_info.get('admin_id')
                    
                    duty_str = f"{shift_label}: {admin_name}"
                    if admin_id:
                        duty_str += f" (ID: {admin_id})"
                    
                    club_data.append(duty_str)
                    has_data = True
            
            if club_data:
                msg += f"🏢 {club}:\n"
                for duty_str in club_data:
                    msg += f"  {duty_str}\n"
                msg += "\n"
        
        if not has_data:
            msg += "Нет данных\n\nИспользуйте /schedule add для добавления"
        
        await update.message.reply_text(msg)
    
    async def cmd_schedule_remove(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Remove duty from schedule
        
        Usage: /schedule remove <date> <club> <shift>
        """
        args = context.args[1:]  # Skip 'remove'
        
        if len(args) < 3:
            await update.message.reply_text(
                "❌ Недостаточно аргументов\n\n"
                "Использование:\n"
                "/schedule remove <дата> <клуб> <утро/вечер>\n\n"
                "Пример:\n"
                "/schedule remove 27.10 rio evening"
            )
            return
        
        # Parse arguments
        date_str = args[0]
        club_str = args[1]
        shift_str = args[2]
        
        # Normalize and validate
        duty_date = self.parse_date(date_str)
        if not duty_date:
            await update.message.reply_text(f"❌ Неверный формат даты: {date_str}")
            return
        
        club = self.normalize_club(club_str)
        if not club:
            await update.message.reply_text(f"❌ Неверный клуб: {club_str}")
            return
        
        shift_type = self.normalize_shift_type(shift_str)
        if not shift_type:
            await update.message.reply_text(f"❌ Неверное время смены: {shift_str}")
            return
        
        # Remove from schedule
        success = self.shift_manager.remove_duty_schedule(duty_date, club, shift_type)
        
        if success:
            shift_label = "☀️ Утро" if shift_type == "morning" else "🌙 Вечер"
            await update.message.reply_text(
                f"✅ Удалено из расписания\n\n"
                f"📅 {duty_date.strftime('%d.%m.%Y')}\n"
                f"🏢 {club}\n"
                f"⏰ {shift_label}"
            )
        else:
            await update.message.reply_text("❌ Запись не найдена")
    
    async def cmd_schedule_clear(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Clear schedule
        
        Usage: /schedule clear [old/week/all]
        """
        args = context.args[1:]  # Skip 'clear'
        
        period = args[0].lower() if args else 'all'
        
        if period not in ['old', 'week', 'all']:
            await update.message.reply_text(
                "❌ Неверный период\n\n"
                "Доступные: old, week, all"
            )
            return
        
        if period == 'all':
            # Clear everything
            success = self.shift_manager.clear_duty_schedule()
            
            if success:
                await update.message.reply_text("✅ Расписание полностью очищено")
            else:
                await update.message.reply_text("❌ Ошибка при очистке")
        else:
            await update.message.reply_text("⚠️ Частичная очистка пока не реализована")
    
    async def cmd_schedule_sync(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Sync schedule from Google Sheets
        
        Usage: /schedule sync [days]
        """
        if not self.is_owner(update.effective_user.id):
            await update.message.reply_text("❌ Только для владельца")
            return
        
        if not self.schedule_parser:
            await update.message.reply_text(
                "❌ Google Sheets парсер не настроен\n\n"
                "Проверьте переменные окружения:\n"
                "• GOOGLE_SA_JSON\n"
                "• GOOGLE_SHEET_ID"
            )
            return
        
        # Get number of days (default 30)
        args = context.args[1:] if len(context.args) > 1 else []
        days = 30
        if args:
            try:
                days = int(args[0])
                days = max(1, min(days, 90))  # Limit 1-90 days
            except ValueError:
                pass
        
        await update.message.reply_text(
            f"📊 Синхронизация расписания на {days} дней...\n"
            f"Это может занять некоторое время..."
        )
        
        try:
            synced = 0
            errors = 0
            
            for days_offset in range(days):
                check_date = date.today() + timedelta(days=days_offset)
                
                try:
                    # Parse schedule from Google Sheets
                    schedule_data = self.schedule_parser.parse_for_date(check_date, use_cache=False)
                    
                    # Update DB
                    for (club, shift_type), duty in schedule_data.items():
                        success = self.shift_manager.add_duty_schedule(
                            duty_date=check_date,
                            club=club,
                            shift_type=shift_type,
                            admin_id=duty.get('admin_id'),
                            admin_name=duty['admin_name']
                        )
                        if success:
                            synced += 1
                
                except Exception as e:
                    errors += 1
                    logger.error(f"❌ Failed to sync {check_date}: {e}")
            
            # Clear cache after sync
            self.schedule_parser.clear_cache()
            
            msg = f"✅ Синхронизация завершена!\n\n"
            msg += f"📊 Записей синхронизировано: {synced}\n"
            if errors > 0:
                msg += f"⚠️ Ошибок: {errors}\n"
            msg += f"📅 Период: {days} дней"
            
            await update.message.reply_text(msg)
            
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка синхронизации: {e}")
            logger.error(f"❌ Sync error: {e}")
            import traceback
            traceback.print_exc()
    
    async def cmd_schedule_test(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Test Google Sheets connection and parsing
        
        Usage: /schedule test [date]
        """
        if not self.is_owner(update.effective_user.id):
            await update.message.reply_text("❌ Только для владельца")
            return
        
        if not self.schedule_parser:
            await update.message.reply_text("❌ Google Sheets парсер не настроен")
            return
        
        # Parse target date
        args = context.args[1:] if len(context.args) > 1 else []
        if args:
            target_date = self.parse_date(args[0])
            if not target_date:
                await update.message.reply_text(f"❌ Неверный формат даты: {args[0]}")
                return
        else:
            target_date = date.today()
        
        await update.message.reply_text(
            f"🔍 Тестирование парсинга для {target_date.strftime('%d.%m.%Y')}..."
        )
        
        try:
            # Test connection
            if not self.schedule_parser.test_connection():
                await update.message.reply_text("❌ Не удалось подключиться к Google Sheets")
                return
            
            # Get available sheets
            available_sheets = self.schedule_parser.get_available_months()
            
            # Parse schedule
            schedule_data = self.schedule_parser.parse_for_date(target_date, use_cache=False)
            
            # Build result message
            msg = f"✅ Тест успешен!\n\n"
            msg += f"📅 Дата: {target_date.strftime('%d.%m.%Y')}\n"
            msg += f"📊 Листы: {', '.join(available_sheets[:5])}\n"
            if len(available_sheets) > 5:
                msg += f"... и еще {len(available_sheets) - 5}\n"
            msg += f"\n📋 Дежурства на {target_date.strftime('%d.%m')}:\n\n"
            
            if schedule_data:
                for (club, shift_type), duty in schedule_data.items():
                    shift_label = "☀️ Утро" if shift_type == "morning" else "🌙 Вечер"
                    admin_name = duty['admin_name']
                    admin_id = duty.get('admin_id')
                    
                    msg += f"🏢 {club} | {shift_label}\n"
                    msg += f"👤 {admin_name}"
                    if admin_id:
                        msg += f" (ID: {admin_id})"
                    else:
                        msg += " (ID не найден в базе)"
                    msg += "\n\n"
            else:
                msg += "Нет данных\n"
            
            await update.message.reply_text(msg)
            
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка теста: {e}")
            logger.error(f"❌ Test error: {e}")
            import traceback
            traceback.print_exc()

    async def cmd_my_shifts(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Show user's shifts for current and next month

        Usage: /my_shifts or button "Мои смены"
        """
        user_id = update.effective_user.id

        try:
            # Get admin info from admin_db if available
            if hasattr(self, 'admin_db') and self.admin_db:
                admin_info = self.admin_db.get_admin(user_id)
                if not admin_info:
                    await update.message.reply_text(
                        "❌ Вы не найдены в списке админов.\n\n"
                        "Эта функция доступна только для админов с полным ФИО в базе."
                    )
                    return

                admin_name = admin_info.get('full_name')
                if not admin_name:
                    await update.message.reply_text(
                        "❌ У вас не указано полное ФИО в базе админов.\n\n"
                        "Обратитесь к владельцу для добавления."
                    )
                    return
            else:
                # Fallback - use telegram name
                admin_name = update.effective_user.full_name
                if not admin_name:
                    await update.message.reply_text("❌ Не удалось определить ваше имя")
                    return

            if not self.schedule_parser:
                await update.message.reply_text(
                    "❌ Парсер расписания не настроен.\n\n"
                    "Обратитесь к администратору."
                )
                return

            # Get current and next month
            today = date.today()
            current_month = today.replace(day=1)
            next_month = (current_month + timedelta(days=32)).replace(day=1)

            # Get shifts for both months
            current_shifts = self.schedule_parser.get_admin_shifts_for_month(admin_name, current_month)
            next_shifts = self.schedule_parser.get_admin_shifts_for_month(admin_name, next_month)

            # Format message
            msg = f"📅 *Ваши смены*\n\n"
            msg += f"👤 {admin_name}\n\n"

            # Current month
            month_names_ru = {
                1: 'Января', 2: 'Февраля', 3: 'Марта', 4: 'Апреля',
                5: 'Мая', 6: 'Июня', 7: 'Июля', 8: 'Августа',
                9: 'Сентября', 10: 'Октября', 11: 'Ноября', 12: 'Декабря'
            }

            if current_shifts:
                msg += f"🗓 *{month_names_ru[current_month.month]} {current_month.year}:*\n"
                for shift in sorted(current_shifts, key=lambda x: x['date']):
                    day = shift['date'].day
                    weekday = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс'][shift['date'].weekday()]
                    club_emoji = '🔴' if shift['club'] == 'Рио' else '🔵'
                    time_emoji = '☀️' if shift['shift_type'] == 'morning' else '🌙'

                    # Mark past/today/future
                    if shift['date'] < today:
                        status = '✅'  # Past
                    elif shift['date'] == today:
                        status = '▶️'  # Today
                    else:
                        status = '📌'  # Future

                    msg += f"{status} {day:2d} {weekday} - {club_emoji} {shift['club']} {time_emoji}\n"
                msg += "\n"
            else:
                msg += f"🗓 *{month_names_ru[current_month.month]} {current_month.year}:*\n"
                msg += "Смен нет\n\n"

            # Next month
            if next_shifts:
                msg += f"🗓 *{month_names_ru[next_month.month]} {next_month.year}:*\n"
                for shift in sorted(next_shifts, key=lambda x: x['date']):
                    day = shift['date'].day
                    weekday = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс'][shift['date'].weekday()]
                    club_emoji = '🔴' if shift['club'] == 'Рио' else '🔵'
                    time_emoji = '☀️' if shift['shift_type'] == 'morning' else '🌙'
                    msg += f"📌 {day:2d} {weekday} - {club_emoji} {shift['club']} {time_emoji}\n"
                msg += "\n"
            else:
                msg += f"🗓 *{month_names_ru[next_month.month]} {next_month.year}:*\n"
                msg += "Смен нет\n\n"

            # Summary
            total = len(current_shifts) + len(next_shifts)
            msg += f"📊 *Итого:* {total} смен"

            # Add back button if called from callback query
            from telegram import InlineKeyboardButton, InlineKeyboardMarkup
            keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data="shifts_menu")]]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await update.message.reply_text(msg, parse_mode='Markdown', reply_markup=reply_markup)

        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка получения смен: {e}")
            logger.error(f"❌ Error in cmd_my_shifts: {e}")
            import traceback
            traceback.print_exc()

