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
    
    def __init__(self, shift_manager, owner_ids: list = None):
        """
        Initialize schedule commands
        
        Args:
            shift_manager: ShiftManager instance
            owner_ids: List of owner telegram IDs
        """
        self.shift_manager = shift_manager
        self.owner_ids = owner_ids or []
    
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
            await update.message.reply_text(
                "📅 Управление расписанием смен\n\n"
                "Команды:\n"
                "/schedule add <дата> <клуб> <утро/вечер> <имя> [ID]\n"
                "/schedule week [дата_начала]\n"
                "/schedule today\n"
                "/schedule remove <дата> <клуб> <утро/вечер>\n"
                "/schedule clear [old/week/all]\n\n"
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
        else:
            await update.message.reply_text(
                f"❌ Неизвестная подкоманда: {subcommand}\n\n"
                "Доступные: add, week, today, remove, clear"
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

