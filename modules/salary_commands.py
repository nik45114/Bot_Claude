#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Salary Commands - Команды для расчета и управления зарплатами
"""

import logging
from datetime import datetime, date, timedelta
from typing import List, Dict, Optional
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)


class SalaryCommands:
    """Commands for salary calculation and management"""
    
    def __init__(self, salary_calculator, admin_db, owner_ids: List[int]):
        self.calc = salary_calculator
        self.admin_db = admin_db
        self.owner_ids = owner_ids
    
    def is_owner(self, user_id: int) -> bool:
        """Check if user is owner"""
        return user_id in self.owner_ids
    
    async def cmd_salary(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        /salary - Main salary menu
        Shows options:
        - View my salary
        - Calculate advance (1-15)
        - Calculate salary (16-end)
        - Custom period
        - Admin reports (owner only)
        - Settings (owner only)
        """
        user_id = update.effective_user.id
        
        # Check if user is admin
        if not self.admin_db.get_admin(user_id):
            await update.message.reply_text("❌ Доступ только для администраторов")
            return
        
        msg = f"💰 Расчет зарплат\n\n"
        msg += f"👤 {update.effective_user.full_name or 'Админ'}\n\n"
        msg += "Выберите действие:"
        
        keyboard = [
            [InlineKeyboardButton("📊 Моя зарплата", callback_data="salary_my_report")],
            [InlineKeyboardButton("📅 Аванс (1-15)", callback_data="salary_advance")],
            [InlineKeyboardButton("📅 Зарплата (16-конец)", callback_data="salary_main")],
            [InlineKeyboardButton("📆 Произвольный период", callback_data="salary_custom")],
            [InlineKeyboardButton("📈 История выплат", callback_data="salary_history")]
        ]
        
        # Owner-only options
        if self.is_owner(user_id):
            keyboard.append([InlineKeyboardButton("⚙️ Настройки админов", callback_data="salary_admin_settings")])
            keyboard.append([InlineKeyboardButton("📋 Отчеты по всем", callback_data="salary_all_reports")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(msg, reply_markup=reply_markup)
    
    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle salary callback queries"""
        query = update.callback_query
        await query.answer()
        
        user_id = query.from_user.id
        
        if query.data == "salary_my_report":
            await self._show_current_period_report(query, context)
        elif query.data == "salary_advance":
            await self._show_advance_report(query, context)
        elif query.data == "salary_main":
            await self._show_salary_report(query, context)
        elif query.data == "salary_custom":
            await self._show_custom_period_menu(query, context)
        elif query.data == "salary_history":
            await self._show_payment_history(query, context)
        elif query.data == "salary_admin_settings":
            if self.is_owner(user_id):
                await self._show_admin_settings_menu(query, context)
            else:
                await query.edit_message_text("❌ Доступ только для владельца")
        elif query.data == "salary_all_reports":
            if self.is_owner(user_id):
                await self._show_all_reports_menu(query, context)
            else:
                await query.edit_message_text("❌ Доступ только для владельца")
        elif query.data.startswith("salary_period_"):
            await self._show_period_report(query, context)
        elif query.data.startswith("salary_admin_"):
            await self._handle_admin_settings(query, context)
        elif query.data.startswith("salary_set_"):
            await self._handle_salary_setting(query, context)
        elif query.data == "salary_back_to_main":
            await self._show_main_menu(query, context)
        elif query.data.startswith("salary_all_"):
            await self._show_all_reports_period(query, context)
    
    async def _show_current_period_report(self, query, context):
        """Show salary report for current month"""
        user_id = query.from_user.id
        now = date.today()
        
        # Determine if we're in advance or salary period
        if now.day <= 15:
            period_start, period_end = self.calc.get_advance_period()
            period_name = "Аванс"
        else:
            period_start, period_end = self.calc.get_salary_period()
            period_name = "Зарплата"
        
        await self._show_salary_report_for_period(query, context, user_id, period_start, period_end, period_name)
    
    async def _show_advance_report(self, query, context):
        """Show advance report (1-15 of current month)"""
        user_id = query.from_user.id
        period_start, period_end = self.calc.get_advance_period()
        await self._show_salary_report_for_period(query, context, user_id, period_start, period_end, "Аванс")
    
    async def _show_salary_report(self, query, context):
        """Show salary report (16-end of current month)"""
        user_id = query.from_user.id
        period_start, period_end = self.calc.get_salary_period()
        await self._show_salary_report_for_period(query, context, user_id, period_start, period_end, "Зарплата")
    
    async def _show_custom_period_menu(self, query, context):
        """Show custom period selection menu"""
        msg = f"📆 Произвольный период\n\n"
        msg += "Выберите период:"
        
        keyboard = [
            [InlineKeyboardButton("📅 Прошлый месяц", callback_data="salary_period_last_month")],
            [InlineKeyboardButton("📅 2 месяца назад", callback_data="salary_period_2_months_ago")],
            [InlineKeyboardButton("📅 Текущий год", callback_data="salary_period_current_year")],
            [InlineKeyboardButton("🔙 Назад", callback_data="salary_back_to_main")]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(msg, reply_markup=reply_markup)
    
    async def _show_period_report(self, query, context):
        """Show report for selected period"""
        user_id = query.from_user.id
        
        if query.data == "salary_period_last_month":
            now = date.today()
            if now.month == 1:
                period_start = date(now.year - 1, 12, 1)
                period_end = date(now.year - 1, 12, 31)
            else:
                period_start = date(now.year, now.month - 1, 1)
                period_end = date(now.year, now.month - 1, 31)
            period_name = "Прошлый месяц"
            
        elif query.data == "salary_period_2_months_ago":
            now = date.today()
            if now.month <= 2:
                month = now.month + 10
                year = now.year - 1
            else:
                month = now.month - 2
                year = now.year
            period_start = date(year, month, 1)
            period_end = date(year, month, 31)
            period_name = "2 месяца назад"
            
        elif query.data == "salary_period_current_year":
            now = date.today()
            period_start = date(now.year, 1, 1)
            period_end = date(now.year, 12, 31)
            period_name = "Текущий год"
            
        else:
            await query.edit_message_text("❌ Неверный период")
            return
        
        await self._show_salary_report_for_period(query, context, user_id, period_start, period_end, period_name)
    
    async def _show_salary_report_for_period(self, query, context, admin_id: int, period_start: date, period_end: date, period_name: str):
        """Show detailed salary report for period"""
        try:
            # Get admin info
            admin = self.admin_db.get_admin(admin_id)
            admin_name = admin.get('full_name') or admin.get('username') or f"ID {admin_id}"
            
            # Calculate salary
            calculation = self.calc.calculate_salary(admin_id, period_start, period_end)
            
            # Format employment type
            emp_type_names = {
                'self_employed': 'Самозанятый',
                'staff': 'Штат',
                'gpc': 'ГПХ'
            }
            emp_type_display = emp_type_names.get(calculation['employment_type'], calculation['employment_type'])
            
            msg = f"📊 {period_name}\n\n"
            msg += f"👤 {admin_name}\n"
            msg += f"📅 {period_start.strftime('%d.%m.%Y')} - {period_end.strftime('%d.%m.%Y')}\n\n"
            
            msg += f"💼 Тип: {emp_type_display}\n"
            msg += f"📋 Смен отработано: {calculation['total_shifts']}\n"
            msg += f"💰 Ставка: {calculation['salary_per_shift']:,.0f}₽/смена\n\n"
            
            msg += f"💵 Начислено: {calculation['gross_amount']:,.0f}₽\n"
            msg += f"📊 Налог ({calculation['tax_rate']:.1f}%): {calculation['tax_amount']:,.0f}₽\n"
            msg += f"✅ К выплате: {calculation['net_amount']:,.0f}₽\n\n"
            
            msg += f"💸 Взято с кассы: {calculation['cash_taken']:,.0f}₽\n"
            msg += f"⚖️ Остаток к выплате: {calculation['amount_due']:,.0f}₽\n"
            
            # Add shifts list if any
            if calculation['shifts']:
                msg += f"\n📋 Смены ({len(calculation['shifts'])}):\n"
                for shift in calculation['shifts'][:5]:  # Show first 5 shifts
                    shift_date = datetime.fromisoformat(shift['opened_at']).strftime('%d.%m')
                    shift_type = "☀️" if shift['shift_type'] == 'morning' else "🌙"
                    msg += f"  • {shift_date} {shift_type} {shift['club']}\n"
                
                if len(calculation['shifts']) > 5:
                    msg += f"  • ... и еще {len(calculation['shifts']) - 5} смен"
            
            keyboard = [
                [InlineKeyboardButton("📈 История выплат", callback_data="salary_history")],
                [InlineKeyboardButton("🔙 Назад", callback_data="salary_back_to_main")]
            ]
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(msg, reply_markup=reply_markup)
            
        except Exception as e:
            logger.error(f"Failed to show salary report: {e}")
            await query.edit_message_text(f"❌ Ошибка при расчете зарплаты: {e}")
    
    async def _show_payment_history(self, query, context):
        """Show payment history for admin"""
        user_id = query.from_user.id
        
        try:
            payments = self.calc.get_payment_history(user_id, limit=10)
            
            if not payments:
                msg = f"📈 История выплат\n\n"
                msg += f"👤 {query.from_user.full_name or 'Админ'}\n\n"
                msg += "История выплат пуста"
            else:
                msg = f"📈 История выплат\n\n"
                msg += f"👤 {query.from_user.full_name or 'Админ'}\n\n"
                
                for payment in payments:
                    period_start = datetime.fromisoformat(payment['period_start']).strftime('%d.%m')
                    period_end = datetime.fromisoformat(payment['period_end']).strftime('%d.%m')
                    payment_type = "Аванс" if payment['payment_type'] == 'advance' else "Зарплата"
                    
                    msg += f"📅 {period_start}-{period_end} ({payment_type})\n"
                    msg += f"   Смен: {payment['total_shifts']} | "
                    msg += f"К выплате: {payment['amount_due']:,.0f}₽\n\n"
            
            keyboard = [
                [InlineKeyboardButton("🔙 Назад", callback_data="salary_back_to_main")]
            ]
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(msg, reply_markup=reply_markup)
            
        except Exception as e:
            logger.error(f"Failed to show payment history: {e}")
            await query.edit_message_text(f"❌ Ошибка при получении истории: {e}")
    
    async def _show_admin_settings_menu(self, query, context):
        """Show admin settings menu (owner only)"""
        msg = f"⚙️ Настройки зарплат\n\n"
        msg += "Выберите администратора:"
        
        try:
            admins = self.admin_db.get_all_admins(active_only=True)
            
            keyboard = []
            for admin in admins[:10]:  # Limit to first 10 admins
                admin_id = admin.get('user_id')
                admin_name = admin.get('full_name') or admin.get('username') or f"ID {admin_id}"
                if len(admin_name) > 20:
                    admin_name = admin_name[:17] + "..."
                
                keyboard.append([
                    InlineKeyboardButton(
                        admin_name,
                        callback_data=f"salary_admin_{admin_id}"
                    )
                ])
            
            keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="salary_back_to_main")])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(msg, reply_markup=reply_markup)
            
        except Exception as e:
            logger.error(f"Failed to show admin settings: {e}")
            await query.edit_message_text(f"❌ Ошибка при получении списка админов: {e}")
    
    async def _handle_admin_settings(self, query, context):
        """Handle admin settings selection"""
        parts = query.data.split('_')
        if len(parts) < 3:
            await query.edit_message_text("❌ Ошибка данных")
            return
        
        admin_id = int(parts[2])
        
        try:
            admin = self.admin_db.get_admin(admin_id)
            if not admin:
                await query.edit_message_text("❌ Администратор не найден")
                return
            
            admin_name = admin.get('full_name') or admin.get('username') or f"ID {admin_id}"
            settings = self.admin_db.get_salary_settings(admin_id)
            
            # Format employment type
            emp_type_names = {
                'self_employed': 'Самозанятый',
                'staff': 'Штат',
                'gpc': 'ГПХ'
            }
            emp_type_display = emp_type_names.get(settings['employment_type'], settings['employment_type'])
            
            msg = f"⚙️ Настройки зарплаты\n\n"
            msg += f"👤 {admin_name}\n\n"
            msg += f"💼 Тип занятости: {emp_type_display}\n"
            msg += f"💵 Ставка за смену: {settings['salary_per_shift']:,.0f}₽\n"
            msg += f"📊 Налог: {settings['tax_rate']:.1f}%\n\n"
            msg += "Выберите что изменить:"
            
            keyboard = [
                [InlineKeyboardButton("💼 Тип занятости", callback_data=f"salary_set_emp_type_{admin_id}")],
                [InlineKeyboardButton("💵 Ставка за смену", callback_data=f"salary_set_rate_{admin_id}")],
                [InlineKeyboardButton("📊 Налог", callback_data=f"salary_set_tax_{admin_id}")],
                [InlineKeyboardButton("🔙 Назад", callback_data="salary_admin_settings")]
            ]
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(msg, reply_markup=reply_markup)
            
        except Exception as e:
            logger.error(f"Failed to handle admin settings: {e}")
            await query.edit_message_text(f"❌ Ошибка при получении настроек: {e}")
    
    async def _handle_salary_setting(self, query, context):
        """Handle salary setting changes"""
        parts = query.data.split('_')
        if len(parts) < 4:
            await query.edit_message_text("❌ Ошибка данных")
            return
        
        setting_type = parts[2]
        admin_id = int(parts[3])
        
        try:
            admin = self.admin_db.get_admin(admin_id)
            admin_name = admin.get('full_name') or admin.get('username') or f"ID {admin_id}"
            
            if setting_type == "emp_type":
                msg = f"💼 Тип занятости\n\n"
                msg += f"👤 {admin_name}\n\n"
                msg += "Выберите тип занятости:"
                
                keyboard = [
                    [InlineKeyboardButton("👤 Самозанятый (6% налог)", callback_data=f"salary_set_emp_self_{admin_id}")],
                    [InlineKeyboardButton("🏢 Штат (30% налог)", callback_data=f"salary_set_emp_staff_{admin_id}")],
                    [InlineKeyboardButton("📋 ГПХ (15% налог)", callback_data=f"salary_set_emp_gpc_{admin_id}")],
                    [InlineKeyboardButton("🔙 Назад", callback_data=f"salary_admin_{admin_id}")]
                ]
                
            elif setting_type == "rate":
                msg = f"💵 Ставка за смену\n\n"
                msg += f"👤 {admin_name}\n\n"
                msg += "Выберите ставку:"
                
                keyboard = [
                    [InlineKeyboardButton("1,000₽", callback_data=f"salary_set_rate_1000_{admin_id}")],
                    [InlineKeyboardButton("1,500₽", callback_data=f"salary_set_rate_1500_{admin_id}")],
                    [InlineKeyboardButton("2,000₽", callback_data=f"salary_set_rate_2000_{admin_id}")],
                    [InlineKeyboardButton("2,500₽", callback_data=f"salary_set_rate_2500_{admin_id}")],
                    [InlineKeyboardButton("3,000₽", callback_data=f"salary_set_rate_3000_{admin_id}")],
                    [InlineKeyboardButton("🔙 Назад", callback_data=f"salary_admin_{admin_id}")]
                ]
                
            elif setting_type == "tax":
                msg = f"📊 Налог\n\n"
                msg += f"👤 {admin_name}\n\n"
                msg += "Выберите налог (0 = по умолчанию):"
                
                keyboard = [
                    [InlineKeyboardButton("0% (по умолчанию)", callback_data=f"salary_set_tax_0_{admin_id}")],
                    [InlineKeyboardButton("6%", callback_data=f"salary_set_tax_6_{admin_id}")],
                    [InlineKeyboardButton("15%", callback_data=f"salary_set_tax_15_{admin_id}")],
                    [InlineKeyboardButton("30%", callback_data=f"salary_set_tax_30_{admin_id}")],
                    [InlineKeyboardButton("🔙 Назад", callback_data=f"salary_admin_{admin_id}")]
                ]
            
            else:
                await query.edit_message_text("❌ Неверный тип настройки")
                return
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(msg, reply_markup=reply_markup)
            
        except Exception as e:
            logger.error(f"Failed to handle salary setting: {e}")
            await query.edit_message_text(f"❌ Ошибка: {e}")
    
    async def _show_all_reports_menu(self, query, context):
        """Show all reports menu (owner only)"""
        msg = f"📋 Отчеты по всем\n\n"
        msg += "Выберите период:"
        
        keyboard = [
            [InlineKeyboardButton("📅 Текущий месяц", callback_data="salary_all_current")],
            [InlineKeyboardButton("📅 Прошлый месяц", callback_data="salary_all_last")],
            [InlineKeyboardButton("📅 Текущий год", callback_data="salary_all_year")],
            [InlineKeyboardButton("🔙 Назад", callback_data="salary_back_to_main")]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(msg, reply_markup=reply_markup)
    
    async def _show_main_menu(self, query, context):
        """Show main salary menu"""
        user_id = query.from_user.id
        
        msg = f"💰 Расчет зарплат\n\n"
        msg += f"👤 {query.from_user.full_name or 'Админ'}\n\n"
        msg += "Выберите действие:"
        
        keyboard = [
            [InlineKeyboardButton("📊 Моя зарплата", callback_data="salary_my_report")],
            [InlineKeyboardButton("📅 Аванс (1-15)", callback_data="salary_advance")],
            [InlineKeyboardButton("📅 Зарплата (16-конец)", callback_data="salary_main")],
            [InlineKeyboardButton("📆 Произвольный период", callback_data="salary_custom")],
            [InlineKeyboardButton("📈 История выплат", callback_data="salary_history")]
        ]
        
        # Owner-only options
        if self.is_owner(user_id):
            keyboard.append([InlineKeyboardButton("⚙️ Настройки админов", callback_data="salary_admin_settings")])
            keyboard.append([InlineKeyboardButton("📋 Отчеты по всем", callback_data="salary_all_reports")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(msg, reply_markup=reply_markup)
    
    async def _show_all_reports_period(self, query, context):
        """Show reports for all admins for selected period"""
        user_id = query.from_user.id
        
        if not self.is_owner(user_id):
            await query.edit_message_text("❌ Доступ только для владельца")
            return
        
        data = query.data
        
        try:
            if data == "salary_all_current":
                now = date.today()
                period_start = date(now.year, now.month, 1)
                period_end = date(now.year, now.month, 31)
                period_name = "Текущий месяц"
                
            elif data == "salary_all_last":
                now = date.today()
                if now.month == 1:
                    period_start = date(now.year - 1, 12, 1)
                    period_end = date(now.year - 1, 12, 31)
                else:
                    period_start = date(now.year, now.month - 1, 1)
                    period_end = date(now.year, now.month - 1, 31)
                period_name = "Прошлый месяц"
                
            elif data == "salary_all_year":
                now = date.today()
                period_start = date(now.year, 1, 1)
                period_end = date(now.year, 12, 31)
                period_name = "Текущий год"
                
            else:
                await query.edit_message_text("❌ Неверный период")
                return
            
            # Get all admins
            admins = self.admin_db.get_all_admins(active_only=True)
            
            msg = f"📋 Отчеты по всем - {period_name}\n\n"
            msg += f"📅 {period_start.strftime('%d.%m.%Y')} - {period_end.strftime('%d.%m.%Y')}\n\n"
            
            total_gross = 0
            total_tax = 0
            total_net = 0
            total_cash_taken = 0
            total_due = 0
            
            for admin in admins:
                admin_id = admin.get('user_id')
                admin_name = admin.get('full_name') or admin.get('username') or f"ID {admin_id}"
                
                calculation = self.calc.calculate_salary(admin_id, period_start, period_end)
                
                if calculation['total_shifts'] > 0:
                    msg += f"👤 {admin_name}\n"
                    msg += f"   Смен: {calculation['total_shifts']} | "
                    msg += f"К выплате: {calculation['amount_due']:,.0f}₽\n\n"
                    
                    total_gross += calculation['gross_amount']
                    total_tax += calculation['tax_amount']
                    total_net += calculation['net_amount']
                    total_cash_taken += calculation['cash_taken']
                    total_due += calculation['amount_due']
            
            msg += f"📊 ИТОГО:\n"
            msg += f"💵 Начислено: {total_gross:,.0f}₽\n"
            msg += f"📊 Налог: {total_tax:,.0f}₽\n"
            msg += f"✅ К выплате: {total_net:,.0f}₽\n"
            msg += f"💸 Взято с кассы: {total_cash_taken:,.0f}₽\n"
            msg += f"⚖️ Остаток: {total_due:,.0f}₽"
            
            keyboard = [
                [InlineKeyboardButton("🔙 Назад", callback_data="salary_back_to_main")]
            ]
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(msg, reply_markup=reply_markup)
            
        except Exception as e:
            logger.error(f"Failed to show all reports: {e}")
            await query.edit_message_text(f"❌ Ошибка при получении отчетов: {e}")
