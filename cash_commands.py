#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Cash Commands - Команды финансового мониторинга
Только для владельца
"""

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

# Состояния conversation handler
CASH_SELECT_CLUB, CASH_SELECT_TYPE, CASH_SELECT_OPERATION = range(3)
CASH_ENTER_AMOUNT, CASH_ENTER_DESCRIPTION, CASH_ENTER_CATEGORY = range(3, 6)


class CashCommands:
    """Обработчик команд финансового мониторинга"""
    
    def __init__(self, cash_manager, owner_id: int):
        self.cash_manager = cash_manager
        self.owner_id = owner_id
    
    def is_owner(self, user_id: int) -> bool:
        """Проверка что пользователь - владелец"""
        return user_id == self.owner_id
    
    async def show_cash_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Главное меню финансов"""
        query = update.callback_query
        
        if query:
            user_id = query.from_user.id
            await query.answer()
        else:
            user_id = update.effective_user.id
        
        if not self.is_owner(user_id):
            text = "❌ Доступно только владельцу"
            if query:
                await query.edit_message_text(text)
            else:
                await update.message.reply_text(text)
            return
        
        keyboard = [
            [InlineKeyboardButton("💰 Текущие балансы", callback_data="cash_balances")],
            [InlineKeyboardButton("➕ Добавить приход", callback_data="cash_add_income")],
            [InlineKeyboardButton("➖ Добавить расход", callback_data="cash_add_expense")],
            [InlineKeyboardButton("📊 История движений", callback_data="cash_movements")],
            [InlineKeyboardButton("📈 Итоги за месяц", callback_data="cash_monthly")],
            [InlineKeyboardButton("◀️ Назад", callback_data="main_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        text = "💰 ФИНАНСОВЫЙ МОНИТОРИНГ\n\n"
        text += "Управление 4 кассами:\n"
        text += "• Рио (официальная)\n"
        text += "• Рио (коробка)\n"
        text += "• Мичуринская (официальная)\n"
        text += "• Мичуринская (коробка)"
        
        if query:
            await query.edit_message_text(text, reply_markup=reply_markup)
        else:
            await update.message.reply_text(text, reply_markup=reply_markup)
    
    async def show_balances(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показать текущие балансы"""
        query = update.callback_query
        await query.answer()
        
        if not self.is_owner(query.from_user.id):
            await query.edit_message_text("❌ Доступно только владельцу")
            return
        
        text = self.cash_manager.format_balance_report()
        
        keyboard = [
            [InlineKeyboardButton("🔄 Обновить", callback_data="cash_balances")],
            [InlineKeyboardButton("◀️ Назад", callback_data="cash_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(text, reply_markup=reply_markup)
    
    async def show_movements(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показать историю движений"""
        query = update.callback_query
        await query.answer()
        
        if not self.is_owner(query.from_user.id):
            await query.edit_message_text("❌ Доступно только владельцу")
            return
        
        movements = self.cash_manager.get_movements(limit=20)
        text = self.cash_manager.format_movements_report(movements)
        
        keyboard = [
            [InlineKeyboardButton("🏢 Рио", callback_data="cash_movements_rio"),
             InlineKeyboardButton("🏢 Мичуринская", callback_data="cash_movements_mich")],
            [InlineKeyboardButton("◀️ Назад", callback_data="cash_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(text, reply_markup=reply_markup)
    
    async def show_movements_club(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показать историю по конкретному клубу"""
        query = update.callback_query
        await query.answer()
        
        if not self.is_owner(query.from_user.id):
            await query.edit_message_text("❌ Доступно только владельцу")
            return
        
        # Извлекаем клуб из callback_data
        club = 'rio' if 'rio' in query.data else 'michurinskaya'
        
        movements = self.cash_manager.get_movements(club=club, limit=20)
        text = self.cash_manager.format_movements_report(movements)
        
        keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data="cash_movements")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(text, reply_markup=reply_markup)
    
    async def start_add_movement(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Начать добавление движения денег"""
        query = update.callback_query
        await query.answer()
        
        if not self.is_owner(query.from_user.id):
            await query.edit_message_text("❌ Доступно только владельцу")
            return ConversationHandler.END
        
        # Сохраняем тип операции
        operation = 'income' if 'income' in query.data else 'expense'
        context.user_data['cash_operation'] = operation
        
        operation_text = "ПРИХОД" if operation == 'income' else "РАСХОД"
        
        keyboard = [
            [InlineKeyboardButton("🏢 Рио", callback_data="cash_club_rio")],
            [InlineKeyboardButton("🏢 Мичуринская/Север", callback_data="cash_club_mich")],
            [InlineKeyboardButton("❌ Отмена", callback_data="cash_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            f"➕ {operation_text}\n\nВыберите клуб:",
            reply_markup=reply_markup
        )
        
        return CASH_SELECT_CLUB
    
    async def select_club(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Выбор клуба"""
        query = update.callback_query
        await query.answer()
        
        club = 'rio' if 'rio' in query.data else 'michurinskaya'
        context.user_data['cash_club'] = club
        
        club_name = "Рио" if club == 'rio' else "Мичуринская/Север"
        
        keyboard = [
            [InlineKeyboardButton("✅ Официальная касса", callback_data="cash_type_official")],
            [InlineKeyboardButton("📦 Коробка", callback_data="cash_type_box")],
            [InlineKeyboardButton("❌ Отмена", callback_data="cash_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            f"Клуб: {club_name}\n\nВыберите кассу:",
            reply_markup=reply_markup
        )
        
        return CASH_SELECT_TYPE
    
    async def select_type(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Выбор типа кассы"""
        query = update.callback_query
        await query.answer()
        
        cash_type = 'official' if 'official' in query.data else 'box'
        context.user_data['cash_type'] = cash_type
        
        operation = context.user_data['cash_operation']
        operation_text = "приход" if operation == 'income' else "расход"
        
        await query.edit_message_text(
            f"Введите сумму ({operation_text}):\n\n"
            "Например: 5000 или 1500.50"
        )
        
        return CASH_ENTER_AMOUNT
    
    async def enter_amount(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Ввод суммы"""
        try:
            amount = float(update.message.text.replace(',', '.').replace(' ', ''))
            context.user_data['cash_amount'] = amount
            
            await update.message.reply_text(
                "Введите описание операции:\n\n"
                "Например: инкассация, зарплата, закупка товара"
            )
            
            return CASH_ENTER_DESCRIPTION
            
        except ValueError:
            await update.message.reply_text(
                "❌ Неверный формат суммы. Введите число, например: 5000"
            )
            return CASH_ENTER_AMOUNT
    
    async def enter_description(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Ввод описания"""
        description = update.message.text
        context.user_data['cash_description'] = description
        
        # Предлагаем категории для расходов
        operation = context.user_data['cash_operation']
        
        if operation == 'expense':
            keyboard = [
                [InlineKeyboardButton("👤 Зарплата", callback_data="cash_cat_salary")],
                [InlineKeyboardButton("🛒 Закупка", callback_data="cash_cat_purchase")],
                [InlineKeyboardButton("🏦 Инкассация", callback_data="cash_cat_collection")],
                [InlineKeyboardButton("💰 Другое", callback_data="cash_cat_other")],
                [InlineKeyboardButton("⏭ Пропустить", callback_data="cash_cat_skip")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                "Выберите категорию расхода:",
                reply_markup=reply_markup
            )
            
            return CASH_ENTER_CATEGORY
        else:
            # Для прихода категория не обязательна
            return await self.save_movement(update, context, category="")
    
    async def select_category(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Выбор категории"""
        query = update.callback_query
        await query.answer()
        
        category_map = {
            'salary': 'Зарплата',
            'purchase': 'Закупка',
            'collection': 'Инкассация',
            'other': 'Другое',
            'skip': ''
        }
        
        # Извлекаем категорию из callback_data
        for key in category_map:
            if key in query.data:
                category = category_map[key]
                break
        else:
            category = ''
        
        return await self.save_movement(update, context, category)
    
    async def save_movement(self, update: Update, context: ContextTypes.DEFAULT_TYPE, category: str = ""):
        """Сохранение движения денег"""
        club = context.user_data['cash_club']
        cash_type = context.user_data['cash_type']
        operation = context.user_data['cash_operation']
        amount = context.user_data['cash_amount']
        description = context.user_data['cash_description']
        
        user_id = update.effective_user.id
        
        success = self.cash_manager.add_movement(
            club=club,
            cash_type=cash_type,
            amount=amount,
            operation=operation,
            description=description,
            category=category,
            created_by=user_id
        )
        
        if success:
            operation_text = "➕ Приход" if operation == 'income' else "➖ Расход"
            club_names = {'rio': 'Рио', 'michurinskaya': 'Мичуринская'}
            type_names = {'official': 'Официальная', 'box': 'Коробка'}
            
            new_balance = self.cash_manager.get_balance(club, cash_type)
            
            text = f"✅ {operation_text} добавлен\n\n"
            text += f"🏢 {club_names[club]}\n"
            text += f"💼 {type_names[cash_type]}\n"
            text += f"💰 Сумма: {amount:,.0f} ₽\n"
            if description:
                text += f"📝 {description}\n"
            if category:
                text += f"🏷 {category}\n"
            text += f"\n💵 Новый баланс: {new_balance:,.0f} ₽"
        else:
            text = "❌ Ошибка сохранения"
        
        keyboard = [[InlineKeyboardButton("◀️ В меню финансов", callback_data="cash_menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        if update.callback_query:
            await update.callback_query.edit_message_text(text, reply_markup=reply_markup)
        else:
            await update.message.reply_text(text, reply_markup=reply_markup)
        
        # Очищаем данные
        context.user_data.clear()
        
        return ConversationHandler.END
    
    async def show_monthly_summary(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показать итоги за месяц"""
        query = update.callback_query
        await query.answer()
        
        if not self.is_owner(query.from_user.id):
            await query.edit_message_text("❌ Доступно только владельцу")
            return
        
        keyboard = [
            [InlineKeyboardButton("🏢 Рио", callback_data="cash_month_rio")],
            [InlineKeyboardButton("🏢 Мичуринская", callback_data="cash_month_mich")],
            [InlineKeyboardButton("◀️ Назад", callback_data="cash_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "Выберите клуб для итогов за месяц:",
            reply_markup=reply_markup
        )
    
    async def show_monthly_club(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показать итоги по клубу"""
        query = update.callback_query
        await query.answer()
        
        if not self.is_owner(query.from_user.id):
            await query.edit_message_text("❌ Доступно только владельцу")
            return
        
        club = 'rio' if 'rio' in query.data else 'michurinskaya'
        
        # Текущий месяц
        now = datetime.now()
        year = now.year
        month = now.month
        
        text = self.cash_manager.format_monthly_summary(club, year, month)
        
        keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data="cash_monthly")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(text, reply_markup=reply_markup)
    
    async def cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Отмена операции"""
        context.user_data.clear()
        await self.show_cash_menu(update, context)
        return ConversationHandler.END
